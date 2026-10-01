"""Executable BDD scenarios for US-0115 / TASK-0154: Real-Time Event Streaming Bridge.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0010; PRD-0006; US-0115, US-0117.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.events import TaskClaimed, TaskCompleted, TaskProposed, TaskRefined
from spec_ops.core.event_store import SQLiteEventLedger
from spec_ops.core.event_streamer import EventEnvelope, EventStreamer, reset_event_streamers

scenarios("features/us_0115_event_streaming.feature")


@pytest.fixture(autouse=True)
def cleanup_streamers():
    reset_event_streamers()
    yield
    reset_event_streamers()


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    """Shared context for US-0115 BDD scenarios."""
    db_file = tmp_path / "events.db"
    streamer = EventStreamer(db_path=db_file, project_root=tmp_path)
    ledger = SQLiteEventLedger(db_path=db_file, project_root=tmp_path, sync_projection=False)
    return {
        "dir": tmp_path,
        "db_path": db_file,
        "streamer": streamer,
        "ledger": ledger,
    }


# --- Scenario 1: Streaming task lifecycle events to connected clients ---


@given("a running SpecOps event streaming bridge")
def running_event_bridge(bdd_context: dict[str, Any]):
    streamer: EventStreamer = bdd_context["streamer"]
    subscriber = streamer.subscribe_sync()
    bdd_context["subscriber"] = subscriber


@when("a task transitions from refined to claimed")
def task_transitions_to_claimed(bdd_context: dict[str, Any]):
    streamer: EventStreamer = bdd_context["streamer"]
    task_id = "TASK-0154"
    aggregate_id = "00000000-0000-0000-0000-000000000154"

    event = TaskClaimed(
        aggregate_id=aggregate_id,
        task_id=task_id,
        claimed_by="agent-worker-1",
        branch="feat/TASK-0154",
    )

    t0 = time.perf_counter()
    envelope = streamer.publish_event(event)
    duration_ms = (time.perf_counter() - t0) * 1000.0

    bdd_context["duration_ms"] = duration_ms
    bdd_context["published_envelope"] = envelope


@then("a TaskClaimed event envelope is published to the stream in under 20 milliseconds")
def verify_published_under_20ms(bdd_context: dict[str, Any]):
    assert bdd_context["duration_ms"] < 20.0, f"Publishing took {bdd_context['duration_ms']:.2f}ms >= 20ms"
    envelope: EventEnvelope = bdd_context["published_envelope"]
    assert envelope.event_type == "TaskClaimed"
    assert envelope.aggregate_id == "00000000-0000-0000-0000-000000000154"


@then("connected subscribers receive the serialized event payload")
def verify_subscriber_received(bdd_context: dict[str, Any]):
    subscriber = bdd_context["subscriber"]
    received: EventEnvelope = subscriber.get(timeout=1.0)
    assert received is not None
    assert received.event_type == "TaskClaimed"
    assert received.payload.get("task_id") == "TASK-0154"
    assert received.payload.get("claimed_by") == "agent-worker-1"
    assert received.sequence_number >= 1


# --- Scenario 2: Historical event replay on new subscriber connection ---


@given("an existing event store containing historical task lifecycle events")
def historical_events_in_store(bdd_context: dict[str, Any]):
    ledger: SQLiteEventLedger = bdd_context["ledger"]
    task_id = "TASK-0154"
    agg_id = "00000000-0000-0000-0000-000000000154"

    e1 = TaskProposed(aggregate_id=agg_id, task_id=task_id, title="Stream Bridge")
    e2 = TaskRefined(aggregate_id=agg_id, task_id=task_id)
    e3 = TaskClaimed(aggregate_id=agg_id, task_id=task_id, claimed_by="worker-alpha")

    persisted = ledger.append_events(task_id, [e1, e2, e3], expected_version=0)
    assert len(persisted) == 3
    bdd_context["expected_count"] = 3


@when("a new subscriber connects with a replay request")
def subscriber_connects_with_replay(bdd_context: dict[str, Any]):
    streamer: EventStreamer = bdd_context["streamer"]
    replayed = streamer.replay_events(limit=50, since_sequence=0)
    live_sub = streamer.subscribe_sync()

    bdd_context["replayed_events"] = replayed
    bdd_context["live_subscriber"] = live_sub


@then("the bridge streams past events in monotonic sequence order")
def verify_monotonic_replay(bdd_context: dict[str, Any]):
    replayed: list[EventEnvelope] = bdd_context["replayed_events"]
    assert len(replayed) >= bdd_context["expected_count"]

    seqs = [e.sequence_number for e in replayed]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)  # strictly monotonic
    event_types = [e.event_type for e in replayed]
    assert event_types == ["TaskProposed", "TaskRefined", "TaskClaimed"]


@then("transitions to live streaming seamlessly")
def verify_seamless_live_streaming(bdd_context: dict[str, Any]):
    streamer: EventStreamer = bdd_context["streamer"]
    live_sub = bdd_context["live_subscriber"]
    replayed: list[EventEnvelope] = bdd_context["replayed_events"]

    last_replayed_seq = replayed[-1].sequence_number

    live_event = streamer.publish_domain_event(
        event_type="TaskCompleted",
        aggregate_id="00000000-0000-0000-0000-000000000154",
        payload={"task_id": "TASK-0154", "commit_hash": "deadbeef123"},
    )

    received: EventEnvelope = live_sub.get(timeout=1.0)
    assert received.event_id == live_event.event_id
    assert received.event_type == "TaskCompleted"
    assert received.payload.get("commit_hash") == "deadbeef123"
    assert received.sequence_number > last_replayed_seq
