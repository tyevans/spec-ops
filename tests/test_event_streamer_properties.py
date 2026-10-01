"""Hypothesis property-based tests for EventStreamer and EventEnvelope.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0010; PRD-0006; US-0115, US-0117.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from hypothesis import given, settings, strategies as st

from spec_ops.backlog.events import (
    TaskClaimed,
    TaskCompleted,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
)
from spec_ops.core.event_store import SQLiteEventLedger
from spec_ops.core.event_streamer import EventEnvelope, EventStreamer

# --- Hypothesis Strategies ---

task_id_strategy = st.integers(min_value=1, max_value=9999).map(lambda n: f"TASK-{n:04d}")
uuid_strategy = st.uuids().map(str)
title_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
    min_size=1,
    max_size=50,
).filter(lambda s: bool(s.strip()))
agent_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd")),
    min_size=1,
    max_size=20,
).filter(lambda s: bool(s.strip()))
commit_strategy = st.text(
    alphabet="0123456789abcdef",
    min_size=7,
    max_size=40,
)
sequence_strategy = st.integers(min_value=1, max_value=10000)


@st.composite
def domain_event_strategy(draw: st.DrawFn) -> Any:
    """Generates arbitrary domain events from backlog domain models."""
    event_cls = draw(
        st.sampled_from(
            [
                TaskProposed,
                TaskRefined,
                TaskClaimed,
                TaskReleased,
                TaskPreflightRecorded,
                TaskCompleted,
            ]
        )
    )
    agg_id = draw(uuid_strategy)
    t_id = draw(task_id_strategy)

    if event_cls is TaskProposed:
        return TaskProposed(
            aggregate_id=agg_id,
            task_id=t_id,
            title=draw(title_strategy).strip(),
            body=draw(st.text(max_size=100)),
            dependencies=draw(st.lists(task_id_strategy, max_size=3)),
            governing_adrs=draw(st.lists(st.just("ADR-0001"), max_size=2)),
            target_bc=draw(st.sampled_from(["core", "backlog", "visualizer"])),
        )
    elif event_cls is TaskRefined:
        return TaskRefined(aggregate_id=agg_id, task_id=t_id)
    elif event_cls is TaskClaimed:
        return TaskClaimed(
            aggregate_id=agg_id,
            task_id=t_id,
            claimed_by=draw(agent_strategy),
            branch=f"feat/{t_id.lower()}",
        )
    elif event_cls is TaskReleased:
        return TaskReleased(
            aggregate_id=agg_id,
            task_id=t_id,
            reason=draw(st.text(max_size=50)),
        )
    elif event_cls is TaskPreflightRecorded:
        return TaskPreflightRecorded(
            aggregate_id=agg_id,
            task_id=t_id,
            success=draw(st.booleans()),
            logs=draw(st.text(max_size=50)),
        )
    else:
        return TaskCompleted(
            aggregate_id=agg_id,
            task_id=t_id,
            commit_hash=draw(commit_strategy),
            pr_url=f"https://github.com/org/repo/pull/{draw(st.integers(min_value=1, max_value=999))}",
        )


# --- Property Tests ---


@settings(max_examples=50)
@given(
    event=domain_event_strategy(),
    sequence_num=sequence_strategy,
)
def test_property_event_envelope_preserves_attributes_without_truncation(
    event: Any, sequence_num: int
) -> None:
    """Property: EventEnvelope preserves exact aggregate ID, sequence version, event type, and payload without truncation."""
    envelope = EventEnvelope.from_domain_event(event, sequence_number=sequence_num)

    expected_agg_id = str(getattr(event, "aggregate_id", getattr(event, "task_id", "")))
    expected_type = type(event).__name__

    assert envelope.aggregate_id == expected_agg_id
    assert envelope.event_type == expected_type
    assert envelope.sequence_number == sequence_num
    assert envelope.event_id != ""
    assert envelope.timestamp != ""

    # Verify JSON serialization round-trip
    json_str = envelope.to_json()
    reconstituted = EventEnvelope.from_json(json_str)

    assert reconstituted.event_id == envelope.event_id
    assert reconstituted.event_type == envelope.event_type
    assert reconstituted.aggregate_id == envelope.aggregate_id
    assert reconstituted.sequence_number == envelope.sequence_number
    assert reconstituted.timestamp == envelope.timestamp
    assert reconstituted.payload == envelope.payload

    # Assert all original event domain fields exist in payload without truncation
    orig_dump = event.model_dump(mode="json")
    for k, v in orig_dump.items():
        assert k in reconstituted.payload
        assert reconstituted.payload[k] == v


@settings(max_examples=40)
@given(
    events=st.lists(domain_event_strategy(), min_size=1, max_size=15),
)
def test_property_event_streamer_monotonic_delivery(events: list[Any]) -> None:
    """Property: Connected subscribers receive envelopes in monotonic sequence order for arbitrary event streams."""
    streamer = EventStreamer(db_path=None)
    sub = streamer.subscribe_sync()

    published_envelopes: list[EventEnvelope] = []
    for evt in events:
        envelope = streamer.publish_event(evt)
        published_envelopes.append(envelope)

    received_envelopes: list[EventEnvelope] = []
    for _ in range(len(events)):
        received_envelopes.append(sub.get_nowait())

    assert len(received_envelopes) == len(events)
    sequences = [e.sequence_number for e in received_envelopes]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)  # Strictly ascending

    for orig, rcv in zip(published_envelopes, received_envelopes):
        assert rcv.event_id == orig.event_id
        assert rcv.event_type == orig.event_type
        assert rcv.aggregate_id == orig.aggregate_id
        assert rcv.sequence_number == orig.sequence_number
        assert rcv.payload == orig.payload


@settings(max_examples=40)
@given(
    event=domain_event_strategy(),
    sequence_num=sequence_strategy,
)
def test_property_sse_formatting_roundtrip(event: Any, sequence_num: int) -> None:
    """Property: format_sse produces valid SSE wire format that deserializes faithfully."""
    envelope = EventEnvelope.from_domain_event(event, sequence_number=sequence_num)
    sse_text = EventStreamer.format_sse(envelope)

    assert sse_text.startswith(f"event: {envelope.event_type}\n")
    assert "\ndata: " in sse_text
    assert sse_text.endswith("\n\n")

    lines = sse_text.strip().split("\n")
    data_line = [l for l in lines if l.startswith("data: ")][0]
    raw_json = data_line[len("data: ") :]

    parsed_dict = json.loads(raw_json)
    reconstituted = EventEnvelope.from_dict(parsed_dict)

    assert reconstituted.event_id == envelope.event_id
    assert reconstituted.event_type == envelope.event_type
    assert reconstituted.aggregate_id == envelope.aggregate_id
    assert reconstituted.sequence_number == envelope.sequence_number
    assert reconstituted.payload == envelope.payload


@settings(max_examples=25)
@given(
    events=st.lists(domain_event_strategy(), min_size=1, max_size=10),
)
def test_property_historical_replay_monotonicity_from_sqlite(events: list[Any]) -> None:
    """Property: SQLite event store replay always yields monotonic sequences matching persisted data."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "prop_events.db"
        ledger = SQLiteEventLedger(db_path=db_path, sync_projection=False)
        streamer = EventStreamer(db_path=db_path)

        task_id = "TASK-0999"
        ledger.append_events(task_id, events, expected_version=0)

        replayed = streamer.replay_events(limit=100, since_sequence=0)
        assert len(replayed) == len(events)

        replayed_seqs = [e.sequence_number for e in replayed]
        assert replayed_seqs == sorted(replayed_seqs)
        assert len(set(replayed_seqs)) == len(replayed_seqs)

        for orig_evt, env in zip(events, replayed):
            assert env.event_type == type(orig_evt).__name__
            assert env.aggregate_id == str(getattr(orig_evt, "aggregate_id", getattr(orig_evt, "task_id", "")))
