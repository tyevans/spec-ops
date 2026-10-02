"""Generative Hypothesis property tests for TaskDecider and SQLiteEventLedger.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0010.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
import pytest

from spec_ops.backlog import (
    ClaimTask,
    CompleteTask,
    ProposeTask,
    RecordPreflight,
    RefineTask,
    ReleaseTask,
    TaskClaimed,
    TaskCompleted,
    TaskDecider,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
    TaskState,
    task_id_to_uuid,
)
from spec_ops.core.event_store import SQLiteEventLedger


task_ids = st.integers(min_value=1, max_value=9999).map(lambda n: f"TASK-{n:04d}")
titles = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
    min_size=1,
    max_size=60,
).filter(lambda s: bool(s.strip()))
workers = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd")),
    min_size=1,
    max_size=20,
).filter(lambda s: bool(s.strip()))
commits = st.text(
    alphabet="0123456789abcdef",
    min_size=7,
    max_size=40,
)


@settings(max_examples=50)
@given(task_id=task_ids, title=titles, worker=workers, commit_hash=commits)
def test_property_lifecycle_determinism_and_invariants(
    task_id: str, title: str, worker: str, commit_hash: str
) -> None:
    """Property: For any valid task inputs, the lifecycle progression is deterministic and maintains invariants."""
    clean_title = title.strip()

    # Run 1: Progressive evolution
    state1 = TaskDecider.initial_state()
    assert state1.status == "Uninitialized"

    cmd_prop = ProposeTask(task_id=task_id, title=clean_title)
    events_prop = TaskDecider.decide(cmd_prop, state1)
    assert len(events_prop) == 1
    assert isinstance(events_prop[0], TaskProposed)
    state1 = TaskDecider.evolve(state1, events_prop[0])
    assert state1.status == "Proposed"
    assert state1.title == clean_title

    cmd_ref = RefineTask(task_id=task_id)
    events_ref = TaskDecider.decide(cmd_ref, state1)
    assert len(events_ref) == 1
    assert isinstance(events_ref[0], TaskRefined)
    state1 = TaskDecider.evolve(state1, events_ref[0])
    assert state1.status == "Refined"

    cmd_claim = ClaimTask(task_id=task_id, claimed_by=worker, branch=f"feat/{task_id.lower()}")
    events_claim = TaskDecider.decide(cmd_claim, state1)
    assert len(events_claim) == 1
    assert isinstance(events_claim[0], TaskClaimed)
    state1 = TaskDecider.evolve(state1, events_claim[0])
    assert state1.status == "Claimed"
    assert state1.claimed_by == worker

    cmd_pre = RecordPreflight(task_id=task_id, success=True, logs="Pass")
    events_pre = TaskDecider.decide(cmd_pre, state1)
    state1 = TaskDecider.evolve(state1, events_pre[0])
    assert state1.last_preflight_success is True

    cmd_comp = CompleteTask(task_id=task_id, commit_hash=commit_hash)
    events_comp = TaskDecider.decide(cmd_comp, state1)
    assert len(events_comp) == 1
    assert isinstance(events_comp[0], TaskCompleted)
    state1 = TaskDecider.evolve(state1, events_comp[0])
    assert state1.status == "Complete"
    assert state1.commit_hash == commit_hash
    assert state1.claimed_by == ""

    # Run 2: Replay same events from initial state must produce identical state (Determinism)
    all_events = events_prop + events_ref + events_claim + events_pre + events_comp
    state2 = TaskDecider.initial_state()
    for evt in all_events:
        state2 = TaskDecider.evolve(state2, evt)
    assert state1 == state2


@settings(max_examples=30)
@given(task_id=task_ids, title=titles, worker1=workers, worker2=workers)
def test_property_claim_conflict_and_release_invariants(
    task_id: str, title: str, worker1: str, worker2: str
) -> None:
    """Property: Already claimed tasks reject competing workers; releasing allows re-claiming."""
    clean_title = title.strip()
    state = TaskDecider.initial_state()
    for e in TaskDecider.decide(ProposeTask(task_id=task_id, title=clean_title), state):
        state = TaskDecider.evolve(state, e)
    for e in TaskDecider.decide(RefineTask(task_id=task_id), state):
        state = TaskDecider.evolve(state, e)

    # Claim with worker1
    for e in TaskDecider.decide(ClaimTask(task_id=task_id, claimed_by=worker1), state):
        state = TaskDecider.evolve(state, e)
    assert state.claimed_by == worker1

    # Competing claim from worker2 must be rejected if different
    if worker1 != worker2:
        with pytest.raises(ValueError, match="already claimed"):
            TaskDecider.decide(ClaimTask(task_id=task_id, claimed_by=worker2), state)

    # Release task back to refined
    for e in TaskDecider.decide(ReleaseTask(task_id=task_id, reason="Paused"), state):
        state = TaskDecider.evolve(state, e)
    assert state.status == "Refined"
    assert state.claimed_by == ""

    # Now worker2 can successfully claim
    events_claim2 = TaskDecider.decide(ClaimTask(task_id=task_id, claimed_by=worker2), state)
    for e in events_claim2:
        state = TaskDecider.evolve(state, e)
    assert state.claimed_by == worker2


@settings(max_examples=30)
@given(task_id=task_ids, title=titles)
def test_property_sqlite_monotonic_versioning_and_concurrency(task_id: str, title: str) -> None:
    """Property: SQLite ledger guarantees strictly monotonic version increments and optimistic locking."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "prop_events.db"
        ledger = SQLiteEventLedger(db_path=db_path, sync_projection=False)

        uid = task_id_to_uuid(task_id)
        e1 = TaskProposed(aggregate_id=uid, task_id=task_id, title=title.strip())
        e2 = TaskRefined(aggregate_id=uid, task_id=task_id)
        e3 = TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="worker-prop")

        persisted = ledger.append_events(task_id, [e1, e2], expected_version=0)
        assert len(persisted) == 2
        assert persisted[0].aggregate_version == 1
        assert persisted[1].aggregate_version == 2

        # Appending next with expected_version=2 succeeds and gets version 3
        p3 = ledger.append_events(task_id, [e3], expected_version=2)
        assert len(p3) == 1
        assert p3[0].aggregate_version == 3

        # Stream retrieval matches monotonic versions
        stream = ledger.get_stream(task_id)
        assert len(stream) == 3
        assert [e.aggregate_version for e in stream] == [1, 2, 3]

        # Replayed state matches in-memory fold
        replayed = ledger.replay_task_state(task_id)
        assert replayed.status == "Claimed"
        assert replayed.claimed_by == "worker-prop"
