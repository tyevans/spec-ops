"""Unit and Hypothesis property-based tests for UnblockingCascadeEngine and JIT buffer replenishment."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.backlog.unblocker import (
    CascadeResult,
    UnblockEvent,
    UnblockingCascadeEngine,
    find_repo_root,
    normalize_task_id,
)
from spec_ops.core.models import BlockerInfo, Task
from spec_ops.scaffold.init import init_project


def setup_test_backlog(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="UnblockerUnitTest", target_dir=repo)
    backlog_dir = repo / "docs" / "project" / "backlog"
    import shutil
    for folder in ("complete", "refined", "proposed"):
        f_dir = backlog_dir / folder
        if f_dir.exists():
            shutil.rmtree(f_dir)
        f_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "PRIORITY.md").write_text("# Backlog Priority Index\n\n", encoding="utf-8")
    return repo, backlog_dir


def test_normalize_task_id_variations():
    assert normalize_task_id("TASK-0001") == "TASK-0001"
    assert normalize_task_id("task-1") == "TASK-0001"
    assert normalize_task_id("TASK-42") == "TASK-0042"
    assert normalize_task_id("SPIKE-0005") == "SPIKE-0005"
    assert normalize_task_id("spike-3") == "SPIKE-0003"
    assert normalize_task_id("99") == "TASK-0099"
    assert normalize_task_id("TASK-XYZ") == "TASK-XYZ"
    assert normalize_task_id("SPIKE-ABC") == "SPIKE-ABC"
    assert normalize_task_id("CUSTOM-1") == "CUSTOM-1"


def test_find_repo_root(tmp_path: Path):
    repo = tmp_path / "my_project"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "specops.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    backlog_dir = repo / "docs" / "project" / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    found = find_repo_root(backlog_dir)
    assert found == repo

    # Deep folder without marker falls back to 3 levels up
    deep = tmp_path / "a" / "b" / "c" / "docs" / "project" / "backlog"
    deep.mkdir(parents=True, exist_ok=True)
    assert find_repo_root(deep) == tmp_path / "a" / "b" / "c"


def test_unblock_event_to_dict():
    ev = UnblockEvent(
        event="task_unblocked",
        task_id="TASK-0042",
        target_bc="security",
        priority_rank=5,
    )
    d = ev.to_dict()
    assert d == {
        "event": "task_unblocked",
        "task_id": "TASK-0042",
        "target_bc": "security",
        "priority_rank": 5,
    }


def test_find_unblocked_dependents_filtering(tmp_path: Path):
    repo, backlog_dir = setup_test_backlog(tmp_path)
    engine = UnblockingCascadeEngine(backlog_dir=backlog_dir, target_buffer=10, repo_root=repo)

    # 1. Blocked task (should be skipped)
    t_blocked = Task(
        id="0001",
        title="Blocked Task",
        status="Proposed",
        blocker=BlockerInfo(type="unknown", question="Need info"),
        dependencies=["TASK-0100"],
        file_path=backlog_dir / "proposed" / "0001-blocked.md",
    )
    # 2. Already refined task (should be skipped)
    t_refined = Task(
        id="0002",
        title="Refined Task",
        status="Refined",
        dependencies=["TASK-0100"],
        file_path=backlog_dir / "refined" / "0002-refined.md",
    )
    # 3. Status with 'Blocked' prefix
    t_blocked_status = Task(
        id="0003",
        title="Blocked Status Task",
        status="Blocked: Waiting",
        dependencies=["TASK-0100"],
        file_path=backlog_dir / "proposed" / "0003-blocked-status.md",
    )
    # 4. Incomplete dependencies (TASK-0100 and TASK-0101; TASK-0101 not complete)
    t_multi_dep = Task(
        id="0004",
        title="Multi Dep Task",
        status="Proposed",
        dependencies=["TASK-0100", "TASK-0101"],
        file_path=backlog_dir / "proposed" / "0004-multi.md",
    )
    # 5. Fully satisfied downstream task
    t_satisfied = Task(
        id="0005",
        title="Satisfied Task",
        status="Proposed",
        dependencies=["TASK-0100"],
        priority_rank=1,
        file_path=backlog_dir / "proposed" / "0005-satisfied.md",
    )
    # 6. Unrelated task (does not depend on TASK-0100)
    t_unrelated = Task(
        id="0006",
        title="Unrelated Task",
        status="Proposed",
        dependencies=["TASK-0200"],
        priority_rank=2,
        file_path=backlog_dir / "proposed" / "0006-unrelated.md",
    )

    all_tasks = [t_blocked, t_refined, t_blocked_status, t_multi_dep, t_satisfied, t_unrelated]
    completed_ids = {"TASK-0100"}

    # Testing with completed_task_id = "TASK-0100"
    unblocked = engine.find_unblocked_dependents("TASK-0100", all_tasks, completed_ids)
    assert len(unblocked) == 1
    assert unblocked[0].canonical_id == "TASK-0005"

    # Testing with completed_task_id = None: both t_satisfied and if t_unrelated had deps in completed_ids
    completed_ids.add("TASK-0200")
    unblocked_all = engine.find_unblocked_dependents(None, all_tasks, completed_ids)
    assert len(unblocked_all) == 2
    assert [t.canonical_id for t in unblocked_all] == ["TASK-0005", "TASK-0006"]


def test_priority_ordering_under_buffer_constraint(tmp_path: Path, capsys):
    repo, backlog_dir = setup_test_backlog(tmp_path)
    engine = UnblockingCascadeEngine(backlog_dir=backlog_dir, target_buffer=3, repo_root=repo)

    # 2 existing refined tasks (buffer count = 2, target = 3 -> only 1 available slot)
    for i in (1, 2):
        write_task_file(Task(
            id=f"{i:04d}",
            title=f"Existing Refined {i}",
            status="Refined",
            priority_rank=i,
            file_path=backlog_dir / "refined" / f"{i:04d}-ref.md",
        ))

    # 2 unblocked candidates depending on TASK-0050: rank 10 and rank 20
    t_high = Task(
        id="0010",
        title="High Priority",
        status="Proposed",
        dependencies=["TASK-0050"],
        priority_rank=10,
        file_path=backlog_dir / "proposed" / "0010-high.md",
    )
    t_low = Task(
        id="0020",
        title="Low Priority",
        status="Proposed",
        dependencies=["TASK-0050"],
        priority_rank=20,
        file_path=backlog_dir / "proposed" / "0020-low.md",
    )
    write_task_file(t_high)
    write_task_file(t_low)

    res = engine.cascade(completed_task_id="TASK-0050", emit_events=True)

    assert len(res.promoted_tasks) == 1
    assert res.promoted_tasks[0].canonical_id == "TASK-0010"
    assert len(res.held_tasks) == 1
    assert res.held_tasks[0].canonical_id == "TASK-0020"
    assert res.held_tasks[0].unblocked is True

    # Check stdout output
    out = capsys.readouterr().out
    assert "task_unblocked" in out
    assert "TASK-0010" in out
    assert "TASK-0020 unblocked but held in proposed to preserve lean ready buffer (3/3)" in out


def test_emit_event_file_error_handling(tmp_path: Path):
    repo, backlog_dir = setup_test_backlog(tmp_path)
    engine = UnblockingCascadeEngine(backlog_dir=backlog_dir, target_buffer=5, repo_root=repo)

    ev = UnblockEvent(task_id="TASK-0001", target_bc="core", priority_rank=1)

    # Simulate OSError on open to verify exception handling doesn't crash cascade
    with patch("pathlib.Path.open", side_effect=OSError("Disk write error")):
        with patch("pathlib.Path.write_text", side_effect=OSError("Disk write error")):
            engine._emit_event(ev)  # Should handle without raising


# --- Hypothesis Property-Based Invariant Tests (ADR-0009) ---

@given(
    target_buffer=st.integers(min_value=1, max_value=15),
    initial_refined_count=st.integers(min_value=0, max_value=15),
    num_unblocked=st.integers(min_value=0, max_value=15),
)
@settings(max_examples=50)
def test_hypothesis_buffer_ceiling_invariant(
    tmp_path_factory: pytest.TempPathFactory,
    target_buffer: int,
    initial_refined_count: int,
    num_unblocked: int,
):
    """Hypothesis Invariant: Cascading unblocking never causes the refined buffer count to exceed the configured target."""
    tmp_path = tmp_path_factory.mktemp("prop_test")
    repo, backlog_dir = setup_test_backlog(tmp_path)
    engine = UnblockingCascadeEngine(backlog_dir=backlog_dir, target_buffer=target_buffer, repo_root=repo)

    # 1. Populate initial refined buffer
    for i in range(1, initial_refined_count + 1):
        write_task_file(Task(
            id=f"{i:04d}",
            title=f"Refined Task {i}",
            status="Refined",
            priority_rank=i,
            file_path=backlog_dir / "refined" / f"{i:04d}-task.md",
        ))

    # 2. Populate proposed tasks depending on TASK-0100
    for j in range(1, num_unblocked + 1):
        tid = 1000 + j
        write_task_file(Task(
            id=f"{tid:04d}",
            title=f"Proposed Dependent {j}",
            status="Proposed",
            dependencies=["TASK-0100"],
            priority_rank=j,
            file_path=backlog_dir / "proposed" / f"{tid:04d}-task.md",
        ))

    # 3. Execute cascading unblocking upon completion of TASK-0100
    result = engine.cascade(completed_task_id="TASK-0100", emit_events=False)

    queue = BacklogQueue(backlog_dir)
    final_refined = [t for t in queue.list_all_tasks() if t.status in ("Refined", "Ready")]
    final_refined_count = len(final_refined)

    # Invariant A: If initial_refined_count <= target_buffer, final count CANNOT exceed target_buffer
    if initial_refined_count <= target_buffer:
        assert final_refined_count <= target_buffer

    # Invariant B: Promoted count must strictly equal min(available_slots, num_unblocked)
    available_slots = max(0, target_buffer - initial_refined_count)
    expected_promoted = min(available_slots, num_unblocked)
    assert len(result.promoted_tasks) == expected_promoted

    # Invariant C: Held count must strictly equal excess unblocked candidates
    expected_held = num_unblocked - expected_promoted
    assert len(result.held_tasks) == expected_held

    # Invariant D: Every held task remains in proposed and is tagged unblocked: true
    for held_task in result.held_tasks:
        assert held_task.unblocked is True
        assert (backlog_dir / "proposed" / held_task.file_path.name).exists()
        assert not (backlog_dir / "refined" / held_task.file_path.name).exists()
