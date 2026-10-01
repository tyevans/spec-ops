"""Unit tests for EventStreamer, EventEnvelope, and HTTP visualizer stream integration.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0010; PRD-0006; US-0115, US-0117.
"""

from __future__ import annotations

import asyncio
import json
import queue
import socket
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from spec_ops.backlog.events import TaskClaimed, TaskCompleted, TaskProposed
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.event_store import SQLiteEventLedger
from spec_ops.core.event_streamer import (
    EventEnvelope,
    EventStreamer,
    get_event_streamer,
    reset_event_streamers,
)
from spec_ops.visualizer.server import ThreadingHTTPServer, VisualizerHandler


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_event_streamers()
    yield
    reset_event_streamers()


def test_event_envelope_serialization_roundtrip():
    envelope = EventEnvelope(
        event_id="test-id-123",
        event_type="TaskClaimed",
        aggregate_id="00000000-0000-0000-0000-000000000001",
        sequence_number=42,
        timestamp="2026-10-01T12:00:00Z",
        payload={"task_id": "TASK-0001", "claimed_by": "agent-1"},
    )

    d = envelope.to_dict()
    assert d["event_id"] == "test-id-123"
    assert d["event_type"] == "TaskClaimed"
    assert d["sequence_number"] == 42
    assert d["payload"]["task_id"] == "TASK-0001"

    json_str = envelope.to_json()
    reconstituted = EventEnvelope.from_json(json_str)
    assert reconstituted == envelope


def test_event_envelope_from_domain_event():
    evt = TaskProposed(
        aggregate_id="00000000-0000-0000-0000-000000000002",
        task_id="TASK-0002",
        title="Telemetry Pipeline",
        dependencies=["TASK-0001"],
    )
    envelope = EventEnvelope.from_domain_event(evt, sequence_number=5)
    assert envelope.event_type == "TaskProposed"
    assert envelope.aggregate_id == "00000000-0000-0000-0000-000000000002"
    assert envelope.sequence_number == 5
    assert envelope.payload["title"] == "Telemetry Pipeline"
    assert envelope.payload["dependencies"] == ["TASK-0001"]


def test_event_streamer_sync_subscription():
    streamer = EventStreamer(db_path=None)
    sub = streamer.subscribe_sync()

    env1 = streamer.publish_domain_event("TaskProposed", "TASK-0001", {"title": "First"})
    env2 = streamer.publish_domain_event("TaskClaimed", "TASK-0001", {"claimed_by": "worker"})

    r1 = sub.get(timeout=1.0)
    r2 = sub.get(timeout=1.0)

    assert r1.event_type == "TaskProposed"
    assert r1.payload["title"] == "First"
    assert r2.event_type == "TaskClaimed"
    assert r2.payload["claimed_by"] == "worker"
    assert r2.sequence_number > r1.sequence_number

    # Unsubscribe test
    streamer.unsubscribe_sync(sub)
    streamer.publish_domain_event("TaskCompleted", "TASK-0001", {})
    assert sub.empty()


def test_event_streamer_async_subscription():
    async def run_async_test():
        streamer = EventStreamer(db_path=None)
        sub = streamer.subscribe()

        streamer.publish_domain_event("TaskRefined", "TASK-0003", {})
        received = await asyncio.wait_for(sub.get(), timeout=1.0)
        assert received.event_type == "TaskRefined"
        assert received.aggregate_id == "TASK-0003"

        streamer.unsubscribe(sub)
        streamer.publish_domain_event("TaskCompleted", "TASK-0003", {})
        assert sub.empty()

    asyncio.run(run_async_test())


def test_event_streamer_multiple_concurrent_subscribers():
    streamer = EventStreamer(db_path=None)
    sub1 = streamer.subscribe_sync()
    sub2 = streamer.subscribe_sync()

    streamer.publish_domain_event("TaskProposed", "TASK-0010", {"title": "Concurrent"})

    item1 = sub1.get(timeout=1.0)
    item2 = sub2.get(timeout=1.0)

    assert item1.event_id == item2.event_id
    assert item1.event_type == "TaskProposed"


def test_format_sse_and_ws():
    envelope = EventEnvelope(
        event_id="eid-999",
        event_type="TaskCompleted",
        aggregate_id="TASK-0099",
        sequence_number=10,
        timestamp="2026-10-01T12:00:00Z",
        payload={"commit": "abc"},
    )
    sse = EventStreamer.format_sse(envelope)
    assert sse.startswith("event: TaskCompleted\n")
    assert "data: " in sse
    assert sse.endswith("\n\n")

    ws = EventStreamer.format_ws(envelope)
    data = json.loads(ws)
    assert data["event_type"] == "TaskCompleted"
    assert data["aggregate_id"] == "TASK-0099"


def test_replay_events_from_in_memory_store():
    streamer = EventStreamer(db_path=None)
    streamer.publish_domain_event("TaskProposed", "TASK-1", {"seq": 1})
    streamer.publish_domain_event("TaskRefined", "TASK-1", {"seq": 2})
    streamer.publish_domain_event("TaskClaimed", "TASK-1", {"seq": 3})

    replayed = streamer.replay_events(limit=2, since_sequence=0)
    assert len(replayed) == 2
    assert replayed[0].event_type == "TaskProposed"
    assert replayed[1].event_type == "TaskRefined"

    replayed_since = streamer.replay_events(limit=10, since_sequence=replayed[1].sequence_number)
    assert len(replayed_since) == 1
    assert replayed_since[0].event_type == "TaskClaimed"


def test_replay_events_from_sqlite(tmp_path: Path):
    db_file = tmp_path / "test_events.db"
    ledger = SQLiteEventLedger(db_path=db_file, project_root=tmp_path, sync_projection=False)
    streamer = EventStreamer(db_path=db_file, project_root=tmp_path)

    e1 = TaskProposed(aggregate_id="00000000-0000-0000-0000-000000000001", task_id="TASK-0001", title="Task 1")
    e2 = TaskClaimed(aggregate_id="00000000-0000-0000-0000-000000000001", task_id="TASK-0001", claimed_by="worker-1")
    ledger.append_events("TASK-0001", [e1, e2], expected_version=0)

    replayed = streamer.replay_events(limit=50, since_sequence=0)
    assert len(replayed) == 2
    assert replayed[0].event_type == "TaskProposed"
    assert replayed[0].sequence_number == 1
    assert replayed[1].event_type == "TaskClaimed"
    assert replayed[1].sequence_number == 2


def test_get_event_streamer_singleton(tmp_path: Path):
    s1 = get_event_streamer(tmp_path)
    s2 = get_event_streamer(tmp_path)
    assert s1 is s2

    reset_event_streamers()
    s3 = get_event_streamer(tmp_path)
    assert s3 is not s1


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_http_events_stream_replay_and_live(tmp_path: Path):
    port = _find_free_port()
    config = SpecOpsConfig(root_dir=tmp_path)
    db_path = tmp_path / ".specops" / "events.db"
    streamer = get_event_streamer(tmp_path, db_path=db_path, reset=True)

    # Pre-seed an event
    streamer.publish_domain_event("TaskProposed", "TASK-0001", {"title": "HTTP Test"})

    handler_class = VisualizerHandler
    handler_class.config = config
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_class)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    time.sleep(0.1)

    try:
        # Test 1: Fetch with live=false (returns replayed events immediately)
        url_replay = f"http://127.0.0.1:{port}/api/events/stream?live=false"
        with urllib.request.urlopen(url_replay, timeout=5.0) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "text/event-stream"
            body = resp.read().decode("utf-8")
            assert "event: TaskProposed" in body
            assert "HTTP Test" in body

        # Test 2: Live streaming
        url_live = f"http://127.0.0.1:{port}/api/events/stream?since=1"
        req = urllib.request.Request(url_live)
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            # Publish live event in background
            def publish_delayed():
                time.sleep(0.1)
                streamer.publish_domain_event("TaskClaimed", "TASK-0001", {"claimed_by": "http-worker"})

            threading.Thread(target=publish_delayed, daemon=True).start()

            # Read stream
            combined = ""
            for _ in range(10):
                line = resp.readline().decode("utf-8")
                combined += line
                if "event: TaskClaimed" in combined and "http-worker" in combined:
                    break

            assert "event: TaskClaimed" in combined
            assert "http-worker" in combined

    finally:
        server.shutdown()
        server.server_close()
