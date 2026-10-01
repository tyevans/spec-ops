"""Comprehensive unit tests for FleetPoolController and dynamic pool sizing."""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from spec_ops.worker.fleet_pool import (
    FleetPoolController,
    PoolConcurrencyConfig,
    PoolEvaluation,
    SystemMetrics,
    sample_host_metrics,
)


def test_system_metrics_properties() -> None:
    metrics = SystemMetrics(
        cpu_utilization_pct=45.2,
        memory_utilization_pct=60.8,
        disk_free_bytes=5_242_880_000,
        disk_total_bytes=52_428_800_000,
    )
    assert metrics.cpu_utilization_pct == 45.2
    assert metrics.memory_utilization_pct == 60.8
    assert "CPU: 45.2%" in metrics.summary
    assert "Memory: 60.8%" in metrics.summary
    assert "5000MB" in metrics.summary


def test_pool_concurrency_config_post_init() -> None:
    # Test normalization of invalid bounds
    cfg = PoolConcurrencyConfig(min_workers=0, max_workers=-5, cpu_threshold_pct=-10.0)
    assert cfg.min_workers == 1
    assert cfg.max_workers == 1
    assert cfg.cpu_threshold_pct == 1.0


def test_sample_host_metrics_execution() -> None:
    # Exercises real stdlib metric sampling without throwing
    metrics = sample_host_metrics()
    assert isinstance(metrics, SystemMetrics)
    assert metrics.cpu_utilization_pct >= 0.0
    assert metrics.memory_utilization_pct >= 0.0
    assert metrics.disk_free_bytes >= 0
    assert metrics.disk_total_bytes >= 0


def test_calculate_concurrency_cpu_breach() -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5, cpu_threshold_pct=85.0)
    controller = FleetPoolController(config=cfg)
    metrics = SystemMetrics(
        cpu_utilization_pct=86.0,
        memory_utilization_pct=30.0,
        disk_free_bytes=10_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    assert controller.calculate_concurrency(metrics) == 1


def test_calculate_concurrency_memory_breach() -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5, mem_threshold_pct=90.0)
    controller = FleetPoolController(config=cfg)
    metrics = SystemMetrics(
        cpu_utilization_pct=20.0,
        memory_utilization_pct=91.5,
        disk_free_bytes=10_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    assert controller.calculate_concurrency(metrics) == 1


def test_calculate_concurrency_disk_breach() -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5, disk_min_free_bytes=500_000_000)
    controller = FleetPoolController(config=cfg)
    metrics = SystemMetrics(
        cpu_utilization_pct=20.0,
        memory_utilization_pct=30.0,
        disk_free_bytes=400_000_000,
        disk_total_bytes=50_000_000_000,
    )
    assert controller.calculate_concurrency(metrics) == 1


def test_calculate_concurrency_quiescent_scales_to_max() -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5)
    controller = FleetPoolController(config=cfg)
    metrics = SystemMetrics(
        cpu_utilization_pct=5.0,
        memory_utilization_pct=10.0,
        disk_free_bytes=40_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    assert controller.calculate_concurrency(metrics) == 5


def test_calculate_concurrency_proportional_intermediate_load() -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5)
    controller = FleetPoolController(config=cfg)
    # Moderate load: ~50% CPU, 40% memory -> should result in intermediate slot allocation (2-4)
    metrics = SystemMetrics(
        cpu_utilization_pct=50.0,
        memory_utilization_pct=40.0,
        disk_free_bytes=20_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    slots = controller.calculate_concurrency(metrics)
    assert 1 < slots <= 5


def test_calculate_concurrency_equal_bounds() -> None:
    cfg = PoolConcurrencyConfig(min_workers=3, max_workers=3)
    controller = FleetPoolController(config=cfg)
    metrics = SystemMetrics(
        cpu_utilization_pct=10.0,
        memory_utilization_pct=10.0,
        disk_free_bytes=10_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    assert controller.calculate_concurrency(metrics) == 3


def test_calculate_concurrency_nan_inf_handling() -> None:
    cfg = PoolConcurrencyConfig(min_workers=2, max_workers=6)
    controller = FleetPoolController(config=cfg)
    metrics_nan = SystemMetrics(
        cpu_utilization_pct=float("nan"),
        memory_utilization_pct=10.0,
        disk_free_bytes=10_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    assert controller.calculate_concurrency(metrics_nan) == 2

    metrics_inf = SystemMetrics(
        cpu_utilization_pct=float("inf"),
        memory_utilization_pct=10.0,
        disk_free_bytes=10_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    assert controller.calculate_concurrency(metrics_inf) == 2


def test_evaluate_capacity_throttling_and_slots() -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5, cpu_threshold_pct=85.0)
    controller = FleetPoolController(config=cfg)
    metrics_breached = SystemMetrics(
        cpu_utilization_pct=95.0,
        memory_utilization_pct=95.0,
        disk_free_bytes=100_000_000,
        disk_total_bytes=50_000_000_000,
    )
    # Active workers = 3, throttled limit = 1 -> available slots = 0, running workers untouched
    eval_res = controller.evaluate_capacity(metrics=metrics_breached, active_workers=3)
    assert eval_res.concurrency_limit == 1
    assert eval_res.available_slots == 0
    assert eval_res.is_throttled is True
    assert eval_res.active_workers == 3
    assert "CPU utilization" in eval_res.throttle_reason
    assert "Memory utilization" in eval_res.throttle_reason
    assert "Worktree disk free" in eval_res.throttle_reason


def test_evaluate_capacity_healthy_available_slots() -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5)
    controller = FleetPoolController(config=cfg)
    metrics_healthy = SystemMetrics(
        cpu_utilization_pct=10.0,
        memory_utilization_pct=15.0,
        disk_free_bytes=40_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    eval_res = controller.evaluate_capacity(metrics=metrics_healthy, active_workers=2)
    assert eval_res.concurrency_limit == 5
    assert eval_res.available_slots == 3
    assert eval_res.is_throttled is False
    assert eval_res.active_workers == 2
    assert eval_res.throttle_reason == ""


def test_get_current_concurrency() -> None:
    sample_metrics = SystemMetrics(
        cpu_utilization_pct=10.0,
        memory_utilization_pct=10.0,
        disk_free_bytes=40_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    controller = FleetPoolController(
        config=PoolConcurrencyConfig(min_workers=1, max_workers=4),
        metrics_sampler=lambda _: sample_metrics,
    )
    assert controller.get_current_concurrency() == 4
