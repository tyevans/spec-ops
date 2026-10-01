"""Property-based generative tests for dynamic fleet pool controller (ADR-0009)."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.worker.fleet_pool import (
    FleetPoolController,
    PoolConcurrencyConfig,
    SystemMetrics,
)


@given(
    cpu_pct=st.floats(allow_nan=True, allow_infinity=True),
    mem_pct=st.floats(allow_nan=True, allow_infinity=True),
    disk_free=st.integers(min_value=-5_000_000, max_value=1_000_000_000_000),
    disk_total=st.integers(min_value=-5_000_000, max_value=2_000_000_000_000),
    min_w=st.integers(min_value=1, max_value=8),
    max_w=st.integers(min_value=1, max_value=20),
    cpu_thresh=st.floats(min_value=10.0, max_value=99.0),
    mem_thresh=st.floats(min_value=10.0, max_value=99.0),
    disk_min_free=st.integers(min_value=0, max_value=10_000_000_000),
    active_workers=st.integers(min_value=-5, max_value=30),
)
def test_property_concurrency_bounds_and_invariants(
    cpu_pct: float,
    mem_pct: float,
    disk_free: int,
    disk_total: int,
    min_w: int,
    max_w: int,
    cpu_thresh: float,
    mem_thresh: float,
    disk_min_free: int,
    active_workers: int,
) -> None:
    """Invariant: Concurrency slot count is bounded strictly within [min_workers, max_workers]

    without division-by-zero, negative results, or unhandled exceptions on arbitrary inputs.
    """
    config = PoolConcurrencyConfig(
        min_workers=min_w,
        max_workers=max_w,
        cpu_threshold_pct=cpu_thresh,
        mem_threshold_pct=mem_thresh,
        disk_min_free_bytes=disk_min_free,
    )
    controller = FleetPoolController(config=config)
    metrics = SystemMetrics(
        cpu_utilization_pct=cpu_pct,
        memory_utilization_pct=mem_pct,
        disk_free_bytes=disk_free,
        disk_total_bytes=disk_total,
    )

    concurrency = controller.calculate_concurrency(metrics)
    effective_min = max(1, min_w)
    effective_max = max(effective_min, max_w)

    assert isinstance(concurrency, int)
    assert effective_min <= concurrency <= effective_max

    # Invariant: If any threshold is breached, concurrency MUST throttle to effective_min
    is_breached = (
        math.isnan(cpu_pct)
        or math.isinf(cpu_pct)
        or math.isnan(mem_pct)
        or math.isinf(mem_pct)
        or cpu_pct > cpu_thresh
        or mem_pct > mem_thresh
        or disk_free < disk_min_free
    )
    if is_breached:
        assert concurrency == effective_min

    # Capacity evaluation invariants
    evaluation = controller.evaluate_capacity(metrics=metrics, active_workers=active_workers)
    assert evaluation.concurrency_limit == concurrency
    assert 0 <= evaluation.available_slots <= concurrency
    assert evaluation.active_workers == max(0, active_workers)
    if is_breached:
        assert evaluation.is_throttled is True
        assert len(evaluation.throttle_reason) > 0


@given(
    cpu_a=st.floats(min_value=0.0, max_value=85.0),
    cpu_b=st.floats(min_value=0.0, max_value=85.0),
    min_w=st.integers(min_value=1, max_value=3),
    max_w=st.integers(min_value=4, max_value=10),
)
def test_property_monotonic_load_scaling(
    cpu_a: float,
    cpu_b: float,
    min_w: int,
    max_w: int,
) -> None:
    """Invariant: Higher load pressure never increases concurrency capacity."""
    config = PoolConcurrencyConfig(min_workers=min_w, max_workers=max_w, cpu_threshold_pct=85.0)
    controller = FleetPoolController(config=config)

    low_cpu = min(cpu_a, cpu_b)
    high_cpu = max(cpu_a, cpu_b)

    metrics_low = SystemMetrics(
        cpu_utilization_pct=low_cpu,
        memory_utilization_pct=10.0,
        disk_free_bytes=50_000_000_000,
        disk_total_bytes=100_000_000_000,
    )
    metrics_high = SystemMetrics(
        cpu_utilization_pct=high_cpu,
        memory_utilization_pct=10.0,
        disk_free_bytes=50_000_000_000,
        disk_total_bytes=100_000_000_000,
    )

    concurrency_low = controller.calculate_concurrency(metrics_low)
    concurrency_high = controller.calculate_concurrency(metrics_high)

    assert concurrency_low >= concurrency_high


@given(
    min_w=st.integers(min_value=1, max_value=4),
    max_w=st.integers(min_value=5, max_value=12),
)
def test_property_quiescent_reaches_maximum(min_w: int, max_w: int) -> None:
    """Invariant: On an idle quiescent host, concurrency scales to the maximum configured ceiling."""
    config = PoolConcurrencyConfig(min_workers=min_w, max_workers=max_w)
    controller = FleetPoolController(config=config)

    quiescent = SystemMetrics(
        cpu_utilization_pct=5.0,
        memory_utilization_pct=8.0,
        disk_free_bytes=80_000_000_000,
        disk_total_bytes=100_000_000_000,
    )
    assert controller.calculate_concurrency(quiescent) == max_w
