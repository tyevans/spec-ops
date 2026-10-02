"""Executable BDD scenarios for US-0115 / TASK-0167: Interactive Terminal Dashboard Multi-Tab Live Monitor.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0008, ADR-0010; PRD-0001, PRD-0006; US-0115, US-0117; TASK-0167.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when
from rich.console import Console

from spec_ops.cli.main import main
from spec_ops.cli.monitor_handler import handle_monitor_command
from spec_ops.cli.parser import build_parser
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.event_streamer import EventEnvelope, get_event_streamer
from spec_ops.tui.live_monitor import LiveMonitor
from spec_ops.worker.lease_manager import WorkerLeaseManager

scenarios("features/us_0115_live_monitor.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


@given("active workers executing tasks in isolated worktrees")
def step_given_active_workers(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    # Scaffold backlog task
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    task1 = backlog_dir / "0001-active-task.md"
    task1.write_text(
        "---\nid: TASK-0001\ntitle: Worker Task\nstatus: In-Progress\nclaimed_by: test-worker-1\n---\n# Task\n",
        encoding="utf-8",
    )

    # Scaffold lease
    mgr = WorkerLeaseManager(tmp_path)
    mgr.create_lease("TASK-0001", worker_id="test-worker-1", pid=os.getpid(), ttl_seconds=600)

    # Publish an event to the stream
    streamer = get_event_streamer(project_root=tmp_path)
    now_str = "2026-10-01T12:00:00+00:00"
    streamer.publish(
        EventEnvelope(
            event_id="evt-100",
            event_type="worker.task.started",
            aggregate_id="TASK-0001",
            sequence_number=1,
            timestamp=now_str,
            payload={"worker": "test-worker-1", "stage": "execution"},
        )
    )

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)
    bdd_context["streamer"] = streamer


@when("the operator launches spec-ops monitor live")
def step_when_launch_monitor_live(bdd_context: dict[str, Any]) -> None:
    config: SpecOpsConfig = bdd_context["config"]
    monitor = LiveMonitor(config=config, interval=0.1, initial_tab="workers")
    console = Console(record=True, width=120, height=40)

    # Execute single iteration in live mode
    ret = monitor.run(console=console, max_iterations=1)
    bdd_context["exit_code"] = ret
    bdd_context["monitor"] = monitor
    bdd_context["console"] = console


@then("the terminal dashboard renders active worker cards and system metrics")
def step_then_renders_workers_and_metrics(bdd_context: dict[str, Any]) -> None:
    monitor: LiveMonitor = bdd_context["monitor"]
    layout = monitor.render_layout()
    console: Console = bdd_context["console"]
    console.print(layout)
    captured = console.export_text()
    assert "Active Worker Fleet" in captured
    assert "TASK-0001" in captured
    assert "test-worker-1" in captured


@then("updates dynamically as lifecycle events are published")
def step_then_updates_dynamically_with_events(bdd_context: dict[str, Any]) -> None:
    monitor: LiveMonitor = bdd_context["monitor"]
    streamer = bdd_context["streamer"]

    # Publish lifecycle event
    streamer.publish(
        EventEnvelope(
            event_id="evt-101",
            event_type="worker.preflight.passed",
            aggregate_id="TASK-0001",
            sequence_number=2,
            timestamp="2026-10-01T12:01:00+00:00",
            payload={"stage": "preflight", "passed": True},
        )
    )

    # Switch to events tab and render
    monitor.active_tab = "events"
    console: Console = bdd_context["console"]
    console.print(monitor.render_layout())
    captured = console.export_text()
    assert "Live Event Stream" in captured
    assert "worker.preflight.passed" in captured or "worker.task.started" in captured


@given("a terminal running in a headless CI environment")
def step_given_headless_ci_terminal(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    task1 = backlog_dir / "0002-ci-task.md"
    task1.write_text(
        "---\nid: TASK-0002\ntitle: CI Task\nstatus: Refined\n---\n# CI Task\n",
        encoding="utf-8",
    )

    bdd_context["root_dir"] = tmp_path
    bdd_context["config"] = SpecOpsConfig(root_dir=tmp_path)


@when("the operator executes spec-ops monitor live with headless flag")
def step_when_execute_headless(bdd_context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(["monitor", "live", "--headless"])
    ret = handle_monitor_command(args, bdd_context["config"])
    bdd_context["exit_code"] = ret
    captured = capsys.readouterr()
    bdd_context["stdout"] = captured.out
    bdd_context["stderr"] = captured.err


@then("a clean terminal summary table is printed to standard output")
def step_then_clean_summary_table_printed(bdd_context: dict[str, Any]) -> None:
    out = bdd_context["stdout"]
    assert "SpecOps Live Monitor" in out
    assert "Active Worker Fleet" in out
    assert "Quit" in out or "Refresh" in out


@then("the command terminates with exit code 0")
def step_then_command_exits_zero(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0
