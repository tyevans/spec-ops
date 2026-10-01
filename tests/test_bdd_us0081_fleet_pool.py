"""BDD step definitions for US-0081: Dynamic Multi-Worker Fleet Concurrency and Adaptive Sizing."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker import (
    BatchCycleOrchestrator,
    FleetPoolController,
    PoolConcurrencyConfig,
    SystemMetrics,
)

scenarios("features/us_0081_fleet_pool.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


@given("a system running with CPU utilization exceeding 85%")
def system_running_high_cpu(bdd_context: dict[str, Any]) -> None:
    cfg = PoolConcurrencyConfig(min_workers=1, max_workers=5, cpu_threshold_pct=85.0)
    controller = FleetPoolController(config=cfg)
    metrics = SystemMetrics(
        cpu_utilization_pct=91.4,
        memory_utilization_pct=42.0,
        disk_free_bytes=20_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    bdd_context["controller"] = controller
    bdd_context["metrics"] = metrics
    bdd_context["active_workers"] = 2


@when("the fleet pool controller evaluates concurrency capacity")
def controller_evaluates_capacity(bdd_context: dict[str, Any]) -> None:
    controller: FleetPoolController = bdd_context["controller"]
    metrics: SystemMetrics = bdd_context["metrics"]
    active = bdd_context.get("active_workers", 0)
    evaluation = controller.evaluate_capacity(metrics=metrics, active_workers=active)
    bdd_context["evaluation"] = evaluation


@then("available worker slots are throttled down to prevent resource exhaustion")
def slots_throttled_down(bdd_context: dict[str, Any]) -> None:
    evaluation = bdd_context["evaluation"]
    controller = bdd_context["controller"]
    assert evaluation.is_throttled is True
    assert evaluation.concurrency_limit == controller.config.min_workers
    assert evaluation.available_slots == 0


@then("active running worktrees continue execution unimpeded")
def active_worktrees_continue_unimpeded(bdd_context: dict[str, Any]) -> None:
    evaluation = bdd_context["evaluation"]
    assert evaluation.active_workers == 2


@given("a quiescent system with low CPU and memory utilization")
def quiescent_system(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="RepoApp", target_dir=repo, profiles=["core", "bdd", "ddd"])
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    config = load_config(repo)
    config.quality.preflight = []
    config.execution.agent_command = ""

    quiescent_metrics = SystemMetrics(
        cpu_utilization_pct=12.0,
        memory_utilization_pct=18.0,
        disk_free_bytes=30_000_000_000,
        disk_total_bytes=50_000_000_000,
    )
    pool_cfg = PoolConcurrencyConfig(min_workers=1, max_workers=4)
    controller = FleetPoolController(config=pool_cfg, metrics_sampler=lambda _: quiescent_metrics)

    bdd_context["repo"] = repo
    bdd_context["config"] = config
    bdd_context["pool_controller"] = controller
    bdd_context["quiescent_metrics"] = quiescent_metrics


@when("the cycle command runs with adaptive pooling enabled")
def cycle_runs_with_adaptive(bdd_context: dict[str, Any]) -> None:
    repo = bdd_context["repo"]
    config = bdd_context["config"]
    controller = bdd_context["pool_controller"]

    refined_dir = repo / "docs" / "project" / "backlog" / "refined"
    t1 = Task(id="0101", title="Task Alpha", status="Refined", file_path=refined_dir / "0101-task-alpha.md")
    t2 = Task(id="0102", title="Task Beta", status="Refined", file_path=refined_dir / "0102-task-beta.md")
    write_task_file(t1)
    write_task_file(t2)

    orchestrator = BatchCycleOrchestrator(
        config=config,
        max_concurrency=4,
        max_tasks=2,
        dry_run=True,
        no_merge=True,
        adaptive=True,
        pool_controller=controller,
    )
    report = orchestrator.run()
    bdd_context["report"] = report
    bdd_context["computed_concurrency"] = controller.calculate_concurrency(bdd_context["quiescent_metrics"])


@then("concurrency scales up to the configured maximum limit")
def concurrency_scales_up(bdd_context: dict[str, Any]) -> None:
    controller = bdd_context["pool_controller"]
    concurrency = bdd_context["computed_concurrency"]
    assert concurrency == controller.config.max_workers
    assert concurrency == 4


@then("multiple parallel worktrees execute concurrently")
def multiple_worktrees_execute(bdd_context: dict[str, Any]) -> None:
    report = bdd_context["report"]
    assert report.tasks_executed == 2
    assert len(report.tasks_succeeded) == 2
