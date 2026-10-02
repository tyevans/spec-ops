"""Unit tests for SQLiteEventLedger and synchronous filesystem projection.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0010.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from spec_ops.backlog import (
    ClaimTask,
    CompleteTask,
    ProposeTask,
    RefineTask,
    ReleaseTask,
    TaskClaimed,
    TaskCompleted,
    TaskDecider,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
    task_id_to_uuid,
)
from spec_ops.core.event_store import (
    SQLiteEventLedger,
    append_events,
    get_stream,
    project_task_event_to_filesystem,
    replay_task_state,
)


def test_sqlite_ledger_append_and_read(tmp_path: Path) -> None:
    db_file = tmp_path / "custom" / "events.db"
    ledger = SQLiteEventLedger(db_path=db_file, sync_projection=False)

    task_id = "TASK-0200"
    uid = task_id_to_uuid(task_id)
    evt1 = TaskProposed(aggregate_id=uid, task_id=task_id, title="Test Task")
    evt2 = TaskRefined(aggregate_id=uid, task_id=task_id)

    persisted = ledger.append_events(task_id, [evt1, evt2])
    assert len(persisted) == 2
    assert persisted[0].aggregate_version == 1
    assert persisted[1].aggregate_version == 2

    stream = ledger.get_stream(task_id)
    assert len(stream) == 2
    assert isinstance(stream[0], TaskProposed)
    assert stream[0].title == "Test Task"
    assert isinstance(stream[1], TaskRefined)


def test_optimistic_concurrency_control(tmp_path: Path) -> None:
    db_file = tmp_path / "events.db"
    ledger = SQLiteEventLedger(db_path=db_file, sync_projection=False)

    task_id = "TASK-0201"
    uid = task_id_to_uuid(task_id)
    evt1 = TaskProposed(aggregate_id=uid, task_id=task_id, title="Optimistic Task")

    # Initial append with expected_version=0
    ledger.append_events(task_id, [evt1], expected_version=0)

    # Next append with correct expected_version=1
    evt2 = TaskRefined(aggregate_id=uid, task_id=task_id)
    ledger.append_events(task_id, [evt2], expected_version=1)

    # Appending with stale expected_version=1 must fail
    evt3 = TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="worker-a")
    with pytest.raises(ValueError, match="Optimistic concurrency violation"):
        ledger.append_events(task_id, [evt3], expected_version=1)


def test_replay_task_state(tmp_path: Path) -> None:
    db_file = tmp_path / "events.db"
    ledger = SQLiteEventLedger(db_path=db_file, sync_projection=False)

    task_id = "TASK-0202"
    uid = task_id_to_uuid(task_id)
    events = [
        TaskProposed(aggregate_id=uid, task_id=task_id, title="Replayable Task", body="Spec body"),
        TaskRefined(aggregate_id=uid, task_id=task_id),
        TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="agent-007", branch="feat/0202"),
        TaskPreflightRecorded(aggregate_id=uid, task_id=task_id, success=True, logs="Pass"),
        TaskCompleted(aggregate_id=uid, task_id=task_id, commit_hash="sha-1234", pr_url="https://pr/202"),
    ]
    ledger.append_events(task_id, events)

    state = ledger.replay_task_state(task_id)
    assert state.task_id == task_id
    assert state.title == "Replayable Task"
    assert state.status == "Complete"
    assert state.commit_hash == "sha-1234"
    assert state.pr_url == "https://pr/202"
    assert state.last_preflight_success is True


def test_filesystem_projection_lifecycle(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    backlog_dir = project_root / "docs" / "project" / "backlog"
    (backlog_dir / "proposed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "refined").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "complete").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "PRIORITY.md").write_text("# Priorities\n", encoding="utf-8")

    ledger = SQLiteEventLedger(project_root=project_root, sync_projection=True)
    task_id = "TASK-0203"
    uid = task_id_to_uuid(task_id)

    # 1. Proposed
    evt_prop = TaskProposed(
        aggregate_id=uid,
        task_id=task_id,
        title="Projected Lifecycle Feature",
        dependencies=["TASK-0001"],
        governing_adrs=["ADR-0010"],
        governing_prds=["PRD-0001"],
        governing_stories=["US-0030"],
        target_bc="core",
    )
    ledger.append_events(task_id, [evt_prop])

    prop_file = list((backlog_dir / "proposed").glob("*.md"))[0]
    assert prop_file.exists()
    content = prop_file.read_text(encoding="utf-8")
    assert "status: Proposed" in content
    assert "ADR-0010" in content

    # 2. Refined
    evt_ref = TaskRefined(aggregate_id=uid, task_id=task_id)
    ledger.append_events(task_id, [evt_ref])

    assert not prop_file.exists()
    ref_file = list((backlog_dir / "refined").glob("*.md"))[0]
    assert ref_file.exists()
    assert "status: Refined" in ref_file.read_text(encoding="utf-8")

    # 3. Claimed
    evt_claim = TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="worker-alpha", branch="feat/0203")
    ledger.append_events(task_id, [evt_claim])
    content = ref_file.read_text(encoding="utf-8")
    assert "claimed_by: worker-alpha" in content
    assert "branch: feat/0203" in content

    # 4. Released
    evt_rel = TaskReleased(aggregate_id=uid, task_id=task_id, reason="Reset")
    ledger.append_events(task_id, [evt_rel])
    content = ref_file.read_text(encoding="utf-8")
    assert "claimed_by" not in content or "claimed_by: ''" in content

    # 5. Completed
    evt_comp = TaskCompleted(aggregate_id=uid, task_id=task_id, commit_hash="11223344", pr_url="https://pr/abc")
    ledger.append_events(task_id, [evt_comp])
    assert not ref_file.exists()
    comp_file = list((backlog_dir / "complete").glob("*.md"))[0]
    assert comp_file.exists()
    content = comp_file.read_text(encoding="utf-8")
    assert "status: Complete" in content
    assert "pr_url: https://pr/abc" in content

    # PRIORITY.md check
    priority = (backlog_dir / "PRIORITY.md").read_text(encoding="utf-8")
    assert f"**{task_id} (Complete)**" in priority


def test_async_ledger_methods(tmp_path: Path) -> None:
    async def run() -> None:
        db_file = tmp_path / "async_events.db"
        ledger = SQLiteEventLedger(db_path=db_file, sync_projection=False)
        task_id = "TASK-0204"
        uid = task_id_to_uuid(task_id)
        evt = TaskProposed(aggregate_id=uid, task_id=task_id, title="Async Task")

        await ledger.append_events_async(task_id, [evt])
        stream = await ledger.get_stream_async(task_id)
        assert len(stream) == 1
        assert stream[0].task_id == task_id

        state = await ledger.replay_task_state_async(task_id)
        assert state.status == "Proposed"
        assert state.title == "Async Task"

    asyncio.run(run())


def test_convenience_functions(tmp_path: Path) -> None:
    db_file = tmp_path / "conv_events.db"
    task_id = "TASK-0205"
    uid = task_id_to_uuid(task_id)
    evt = TaskProposed(aggregate_id=uid, task_id=task_id, title="Convenience Task")

    append_events(task_id, [evt], db_path=db_file, sync_projection=False)
    stream = get_stream(task_id, db_path=db_file)
    assert len(stream) == 1
    assert stream[0].title == "Convenience Task"

    state = replay_task_state(task_id, db_path=db_file)
    assert state.status == "Proposed"
