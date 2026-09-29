"""Unit and integration tests for the SpecOps TUI Dashboard."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.tui import TUIDashboard
from spec_ops.tui.views import (
    render_backlog_panel,
    render_entity_tree,
    render_footer,
    render_header,
    render_health_panel,
    render_task_detail,
)


def test_tui_views_rendering(tmp_path: Path):
    init_project(tmp_path, name="TuiTest")
    dashboard = TUIDashboard()
    # Test individual view renders
    header = render_header("TuiTest", "overview")
    assert header is not None

    footer = render_footer("Status OK")
    assert footer is not None

    assert dashboard.report is not None
    assert dashboard.queue is not None
    assert dashboard.data is not None

    b_panel = render_backlog_panel(dashboard.report, dashboard.queue)
    assert b_panel is not None

    tree_panel = render_entity_tree(dashboard.data)
    assert tree_panel is not None

    health_panel = render_health_panel(dashboard.report)
    assert health_panel is not None

    task = Task(
        file_path=tmp_path / "0001.md",
        id="0001",
        title="Test Task",
        status="Complete",
        target_bc="core",
        body="Detailed body",
        dependencies=[],
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0001"],
    )
    task_panel = render_task_detail(task)
    assert task_panel is not None


def test_tui_dashboard_snapshots(tmp_path: Path):
    init_project(tmp_path, name="TuiSnapTest")
    dashboard = TUIDashboard()

    console = Console(file=io.StringIO(), record=True, width=100)
    for view in ["overview", "backlog", "tree", "health"]:
        layout = dashboard.render_layout(view=view)
        assert layout is not None
        dashboard.render_snapshot(view=view, console=console)
        out = console.export_text()
        assert "SpecOps TUI" in out


def test_tui_dashboard_curate(tmp_path: Path):
    init_project(tmp_path, name="TuiCurateTest")
    dashboard = TUIDashboard()
    msg = dashboard.curate_backlog()
    assert "Curated" in msg


def test_tui_dashboard_run_non_tty():
    dashboard = TUIDashboard()
    # With non-tty stdin, run() should render a snapshot and return 0
    with patch("sys.stdin.isatty", return_value=False):
        ret = dashboard.run("overview")
        assert ret == 0
