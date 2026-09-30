"""Unit tests and mutation coverage for interactive terminal flow monitor (ADR-0009)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.tui.flow_monitor import (
    FlowAction,
    FlowMonitor,
    FlowState,
    format_elapsed_time,
    get_buffer_waterline,
    handle_flow_key,
)


def test_buffer_waterline_calculations():
    """Tests buffer waterline boundaries: Green (>=8), Yellow (5..7), Red (<5)."""
    # Green threshold
    ratio, color, badge = get_buffer_waterline(10, 10)
    assert ratio == "10/10"
    assert color == "Green"
    assert badge == "Buffer: 10/10 [Green]"

    ratio, color, badge = get_buffer_waterline(8, 10)
    assert ratio == "8/10"
    assert color == "Green"
    assert badge == "Buffer: 8/10 [Green]"

    # Yellow threshold
    ratio, color, badge = get_buffer_waterline(7, 10)
    assert ratio == "7/10"
    assert color == "Yellow"
    assert badge == "Buffer: 7/10 [Yellow]"

    ratio, color, badge = get_buffer_waterline(5, 10)
    assert ratio == "5/10"
    assert color == "Yellow"
    assert badge == "Buffer: 5/10 [Yellow]"

    # Red threshold
    ratio, color, badge = get_buffer_waterline(4, 10)
    assert ratio == "4/10"
    assert color == "Red"
    assert badge == "Buffer: 4/10 [Red]"

    ratio, color, badge = get_buffer_waterline(0, 10)
    assert ratio == "0/10"
    assert color == "Red"
    assert badge == "Buffer: 0/10 [Red]"


def test_format_elapsed_time():
    """Tests elapsed time formatting for seconds and minutes."""
    assert format_elapsed_time(-5) == "0s"
    assert format_elapsed_time(0) == "0s"
    assert format_elapsed_time(45) == "45s"
    assert format_elapsed_time(59) == "59s"
    assert format_elapsed_time(60) == "1m 0s"
    assert format_elapsed_time(135) == "2m 15s"


def test_handle_flow_key_quit():
    """Tests quit keybindings."""
    state = FlowState()
    assert handle_flow_key("q", state).action == "QUIT"
    assert handle_flow_key("Q", state).action == "QUIT"
    assert handle_flow_key("\x03", state).action == "QUIT"
    assert handle_flow_key("", state).action == "NONE"


def test_handle_flow_key_column_switching():
    """Tests horizontal column switching."""
    state = FlowState(active_column="proposed")

    act = handle_flow_key("\t", state)
    assert act.action == "SWITCH_COLUMN"
    assert act.column == "refined"

    act = handle_flow_key("l", state)
    assert act.action == "SWITCH_COLUMN"
    assert act.column == "refined"

    state.active_column = "refined"
    act = handle_flow_key("l", state)
    assert act.column == "worktrees"

    state.active_column = "worktrees"
    act = handle_flow_key("l", state)
    assert act.column == "proposed"

    state.active_column = "proposed"
    act = handle_flow_key("h", state)
    assert act.action == "SWITCH_COLUMN"
    assert act.column == "worktrees"


def test_handle_flow_key_vertical_navigation():
    """Tests j/k navigation and boundary clamping."""
    tasks = [
        Task(id="0001", title="T1", status="Proposed", file_path=Path("0001.md")),
        Task(id="0002", title="T2", status="Proposed", file_path=Path("0002.md")),
    ]
    state = FlowState(active_column="proposed", proposed_tasks=tasks, selected_index={"proposed": 0})

    act = handle_flow_key("j", state)
    assert act.action == "NAVIGATE"
    assert act.index == 1

    state.selected_index["proposed"] = 1
    act = handle_flow_key("j", state)
    assert act.action == "NAVIGATE"
    assert act.index == 1  # Clamped at bottom

    act = handle_flow_key("k", state)
    assert act.action == "NAVIGATE"
    assert act.index == 0

    state.selected_index["proposed"] = 0
    act = handle_flow_key("k", state)
    assert act.action == "NAVIGATE"
    assert act.index == 0  # Clamped at top


def test_handle_flow_key_actions():
    """Tests refine ('r') and claim ('c') actions."""
    prop_task = Task(id="0021", title="P1", status="Proposed", file_path=Path("0021.md"))
    ref_task = Task(id="0022", title="R1", status="Refined", file_path=Path("0022.md"))

    state = FlowState(
        active_column="proposed",
        proposed_tasks=[prop_task],
        refined_tasks=[ref_task],
        selected_index={"proposed": 0, "refined": 0},
    )

    act = handle_flow_key("r", state)
    assert act.action == "REFINE"
    assert act.target == "TASK-0021"

    # 'c' on proposed column does nothing
    assert handle_flow_key("c", state).action == "NONE"

    state.active_column = "refined"
    act = handle_flow_key("c", state)
    assert act.action == "CLAIM"
    assert act.target == "TASK-0022"

    # 'r' on refined column does nothing
    assert handle_flow_key("r", state).action == "NONE"


def test_flow_monitor_lifecycle(tmp_path: Path):
    """Tests FlowMonitor initial state and snapshot rendering."""
    repo = tmp_path / "monitor_repo"
    init_project(repo, name="MonitorTest")
    config = load_config(root_dir=repo)

    monitor = FlowMonitor(config)
    assert monitor.state.active_column == "proposed"
    assert monitor.state.completed_count >= 0
    assert "Buffer:" in monitor.state.buffer_badge

    # Non-interactive snapshot
    monitor.render_snapshot()
    layout = monitor.render_layout()
    assert layout is not None
