"""Unit tests for task blocker management, 'Big Unknown' resolution, and spike creation."""

from __future__ import annotations

from pathlib import Path

from spec_ops.backlog.blockers import block_task, list_project_blockers, unblock_task
from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project


def setup_test_backlog(tmp_path: Path) -> Path:
    """Sets up a minimal test backlog with a proposed task and PRIORITY.md."""
    init_project(tmp_path, name="BlockerTest")
    backlog_dir = tmp_path / "docs" / "project" / "backlog"
    proposed_dir = backlog_dir / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)

    task_file = proposed_dir / "0099-test-blocker-task.md"
    task = Task(
        id="0099",
        title="Test Blocker Task",
        status="Proposed",
        file_path=task_file,
        body="# TASK-0099\n\nTask body details.",
    )
    write_task_file(task)

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Index\n\n- **TASK-0099 (Proposed)**: [`0099-test-blocker-task`](proposed/0099-test-blocker-task.md)\n",
        encoding="utf-8",
    )
    return backlog_dir


def test_block_and_unblock_task_lifecycle(tmp_path: Path):
    backlog_dir = setup_test_backlog(tmp_path)

    # 1. Block task with unknown question
    ok, msg, task = block_task(
        backlog_dir,
        "TASK-0099",
        question="Can we use SQLite in WAL mode with concurrent workers?",
        blocker_type="unknown",
        raised_by="Alex",
    )
    assert ok
    assert "marked as Blocked" in msg
    assert task is not None
    assert task.status == "Blocked"
    assert task.blocker is not None
    assert (
        task.blocker.question
        == "Can we use SQLite in WAL mode with concurrent workers?"
    )
    assert task.blocker.raised_by == "Alex"

    # Verify disk state and PRIORITY.md
    reloaded = parse_task(task.file_path)
    assert reloaded.status == "Blocked"
    assert reloaded.blocker is not None
    assert (
        reloaded.blocker.question
        == "Can we use SQLite in WAL mode with concurrent workers?"
    )

    priority_text = (backlog_dir / "PRIORITY.md").read_text(encoding="utf-8")
    assert "Blocked (Unknown)" in priority_text

    # 2. List blockers
    blockers = list_project_blockers(backlog_dir)
    assert len(blockers) == 1
    assert blockers[0]["task_id"] == "TASK-0099"
    assert (
        blockers[0]["question"]
        == "Can we use SQLite in WAL mode with concurrent workers?"
    )

    # 3. Unblock task
    ok, unb_msg, unb_task = unblock_task(
        backlog_dir,
        "TASK-0099",
        resolution="SQLite WAL mode supports concurrent readers with single-writer merge locks.",
        adr_id="ADR-0020",
    )
    assert ok
    assert "unblocked with resolution" in unb_msg
    assert unb_task is not None
    assert unb_task.blocker is not None
    assert (
        unb_task.blocker.resolution
        == "SQLite WAL mode supports concurrent readers with single-writer merge locks."
    )
    assert unb_task.blocker.adr_id == "ADR-0020"

    # Verify PRIORITY.md restored
    priority_text_after = (backlog_dir / "PRIORITY.md").read_text(encoding="utf-8")
    assert "TASK-0099 (Proposed)" in priority_text_after

    # 4. Check blockers list is now empty
    assert len(list_project_blockers(backlog_dir)) == 0


def test_block_task_with_spike_scaffolding(tmp_path: Path):
    backlog_dir = setup_test_backlog(tmp_path)

    ok, msg, task = block_task(
        backlog_dir,
        "TASK-0099",
        question="How fast is tree-sitter AST queries in Python?",
        blocker_type="spike_needed",
        create_spike_flag=True,
        timebox="3h",
        root_dir=tmp_path,
    )
    assert ok
    assert "scaffolded SPIKE-" in msg
    assert task is not None
    assert task.blocker is not None
    spike_id = task.blocker.spike_id
    assert spike_id.startswith("SPIKE-")
    assert spike_id in task.dependencies

    # Verify spike harness created on disk
    spike_num = spike_id.split("-")[-1]
    harness_dir = tmp_path / "spikes" / f"spike_{spike_num}"
    assert harness_dir.exists()
    assert (harness_dir / "test_spike.py").exists()
    assert (harness_dir / "README.md").exists()


def test_block_task_error_conditions(tmp_path: Path):
    backlog_dir = setup_test_backlog(tmp_path)

    # 1. Non-existent task
    ok, msg, _ = block_task(backlog_dir, "TASK-9999", question="Unknown question")
    assert not ok
    assert "not found" in msg

    # 2. Cannot block completed task
    complete_dir = backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    c_file = complete_dir / "0001-done.md"
    c_task = Task(id="0001", title="Done Task", status="Complete", file_path=c_file)
    write_task_file(c_task)

    ok, c_msg, _ = block_task(backlog_dir, "TASK-0001", question="Unknown question")
    assert not ok
    assert "already Complete" in c_msg
