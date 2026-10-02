"""Unit tests for spec_ops.tui.live_monitor and monitor_handler to maximize mutant kill rate."""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import pytest
from rich.console import Console

from spec_ops.cli.monitor_handler import handle_monitor_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.event_streamer import EventEnvelope, get_event_streamer
from spec_ops.tui.live_monitor import LiveMonitor, _read_keypress
from spec_ops.worker.lease_manager import WorkerLeaseManager


def test_read_keypress_non_tty():
    assert _read_keypress(timeout=0.01) is None


def test_live_monitor_tabs_and_polling(tmp_path: Path):
    config = SpecOpsConfig(root_dir=tmp_path)
    monitor = LiveMonitor(config=config, interval=0.1, initial_tab="unknown")
    assert monitor.active_tab == "workers"

    # Publish events
    streamer = get_event_streamer(project_root=tmp_path)
    for i in range(110):
        streamer.publish(
            EventEnvelope(
                event_id=f"evt-{i}",
                event_type="test.event",
                aggregate_id="TEST-1",
                sequence_number=i,
                timestamp="2026-10-01T12:00:00+00:00",
                payload={"index": i},
            )
        )

    monitor.poll_events()
    # Invariant: buffer trimmed to last 100 events
    assert len(monitor.events) == 100
    assert monitor.events[-1].event_id == "evt-109"


def test_render_all_tabs(tmp_path: Path):
    config = SpecOpsConfig(root_dir=tmp_path)
    monitor = LiveMonitor(config=config, interval=0.1)

    console = Console(record=True, width=120)

    # 1. Workers tab empty
    console.print(monitor.render_workers_tab())
    assert "Active Worker Fleet" in console.export_text()

    # 2. Workers tab with lease
    mgr = WorkerLeaseManager(tmp_path)
    mgr.create_lease("TASK-0010", worker_id="worker-x", pid=os.getpid())
    console = Console(record=True, width=120)
    console.print(monitor.render_workers_tab())
    assert "TASK-0010" in console.export_text()

    # 3. Events tab empty vs populated
    console = Console(record=True, width=120)
    console.print(monitor.render_events_tab())
    assert "Live Event Stream" in console.export_text()

    monitor.events.append(
        EventEnvelope(
            event_id="evt-abc",
            event_type="pipeline.passed",
            aggregate_id="TASK-0010",
            sequence_number=1,
            timestamp="2026-10-01T12:00:00+00:00",
            payload={"ok": True},
        )
    )
    console = Console(record=True, width=120)
    console.print(monitor.render_events_tab())
    assert "pipeline.passed" in console.export_text()

    # 4. Health tab
    backlog_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "0010-test.md").write_text("---\nid: TASK-0010\ntitle: Ten\nstatus: Refined\n---\n# Ten\n", encoding="utf-8")
    console = Console(record=True, width=120)
    console.print(monitor.render_health_tab())
    assert "System & Backlog Health" in console.export_text()

    # 5. Header and Footer
    console = Console(record=True, width=120)
    console.print(monitor.render_header())
    console.print(monitor.render_footer())
    header_footer_text = console.export_text()
    assert "SpecOps Live Monitor" in header_footer_text
    assert "Quit" in header_footer_text

    # 6. Layout rendering across all tabs
    for tab in ["workers", "events", "health"]:
        monitor.active_tab = tab
        layout = monitor.render_layout()
        assert layout is not None

    # 7. Snapshot rendering
    console = Console(record=True, width=100)
    monitor.render_snapshot(console=console)
    text = console.export_text()
    assert "SpecOps Live Monitor" in text


def test_monitor_run_loop(tmp_path: Path):
    config = SpecOpsConfig(root_dir=tmp_path)
    monitor = LiveMonitor(config=config, interval=0.01)
    console = Console(record=True, width=100)
    ret = monitor.run(console=console, max_iterations=2)
    assert ret == 0


def test_cli_monitor_handler(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config = SpecOpsConfig(root_dir=tmp_path)

    # JSON snapshot
    args_json = argparse.Namespace(interval=1.0, headless=False, tab="events", json=True)
    ret_json = handle_monitor_command(args_json, config)
    assert ret_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tab"] == "events"
    assert "health" in data

    # Headless snapshot
    args_headless = argparse.Namespace(interval=1.0, headless=True, tab="workers", json=False)
    ret_hl = handle_monitor_command(args_headless, config)
    assert ret_hl == 0
    out_hl = capsys.readouterr().out
    assert "SpecOps Live Monitor" in out_hl
