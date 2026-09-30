"""Unit tests for in-memory graph EventBus, Debouncer, and InMemoryGraphState."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.event_bus import (
    BATCHED_UPDATE,
    GRAPH_CYCLE_INTRODUCED,
    NODE_UPDATED,
    TASK_PROMOTED,
    UNANCHORED_REFERENCE_DETECTED,
    Debouncer,
    EventBus,
    GraphEvent,
    InMemoryGraphState,
)
from spec_ops.core.models import ADR, PRD, Task, UserStory
from spec_ops.core.watcher import WorkspaceWatcher
from spec_ops.cli.graph_handler import handle_watch_command


def test_graph_event_to_dict_and_json() -> None:
    ev = GraphEvent(
        event_type=TASK_PROMOTED,
        entity_id="TASK-0010",
        entity_type="task",
        status="Refined",
        payload={"edges_recalculated": 3, "extra": "data"},
    )
    d = ev.to_dict()
    assert d["event"] == TASK_PROMOTED
    assert d["id"] == "TASK-0010"
    assert d["type"] == "task"
    assert d["status"] == "Refined"
    assert d["edges_recalculated"] == 3
    assert d["extra"] == "data"

    json_str = ev.to_json()
    assert '"event": "TASK_PROMOTED"' in json_str
    assert '"id": "TASK-0010"' in json_str


def test_event_bus_subscribe_unsubscribe() -> None:
    bus = EventBus()
    received: list[GraphEvent] = []

    def cb(event: GraphEvent) -> None:
        received.append(event)

    unsub = bus.subscribe("TEST_EVENT", cb)
    # duplicate subscribe does not add twice
    bus.subscribe("TEST_EVENT", cb)

    dispatched = bus.publish(GraphEvent(event_type="TEST_EVENT", entity_id="1"))
    assert dispatched == 1
    assert len(received) == 1

    # Unsubscribe via function
    assert unsub() is True
    # Unsubscribe again returns False
    assert bus.unsubscribe("TEST_EVENT", cb) is False
    assert bus.unsubscribe("NON_EXISTENT", cb) is False

    dispatched2 = bus.publish(GraphEvent(event_type="TEST_EVENT", entity_id="2"))
    assert dispatched2 == 0
    assert len(received) == 1


def test_event_bus_wildcard_and_history() -> None:
    bus = EventBus()
    all_events: list[GraphEvent] = []
    spec_events: list[GraphEvent] = []

    def cb_wildcard(ev: GraphEvent) -> None:
        all_events.append(ev)

    def cb_spec(ev: GraphEvent) -> None:
        spec_events.append(ev)

    bus.subscribe("*", cb_wildcard)
    bus.subscribe("EV_A", cb_spec)
    # If same callback subscribed to both, targets are deduplicated
    bus.subscribe("EV_A", cb_wildcard)

    bus.publish(GraphEvent(event_type="EV_A", entity_id="A1"))
    bus.publish(GraphEvent(event_type="EV_B", entity_id="B1"))

    assert len(all_events) == 2
    assert len(spec_events) == 1

    history_all = bus.get_history()
    assert len(history_all) == 2
    history_a = bus.get_history("EV_A")
    assert len(history_a) == 1
    assert history_a[0].entity_id == "A1"

    bus.clear_history()
    assert len(bus.get_history()) == 0

    bus.clear_listeners()
    bus.publish(GraphEvent(event_type="EV_A", entity_id="A2"))
    assert len(all_events) == 2


def test_event_bus_listener_exception_handling(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()

    def bad_cb(ev: GraphEvent) -> None:
        raise RuntimeError("boom")

    good_received = []

    def good_cb(ev: GraphEvent) -> None:
        good_received.append(ev)

    bus.subscribe("TEST", bad_cb)
    bus.subscribe("TEST", good_cb)

    dispatched = bus.publish(GraphEvent(event_type="TEST"))
    assert dispatched == 1
    assert len(good_received) == 1


def test_debouncer_basic_and_deduplication() -> None:
    debouncer = Debouncer(debounce_ms=50.0)
    assert not debouncer.is_pending()
    assert debouncer.pending_count == 0

    debouncer.add("file1.md")
    debouncer.add("file2.md")
    debouncer.add("file1.md")  # duplicate

    assert debouncer.is_pending()
    assert debouncer.pending_count == 2

    items = debouncer.flush()
    assert items == ["file1.md", "file2.md"]
    assert not debouncer.is_pending()

    debouncer.add("file3.md")
    debouncer.cancel()
    assert not debouncer.is_pending()


def test_debouncer_timer_callback() -> None:
    flushed_items: list[list[Any]] = []

    def on_flush(items: list[Any]) -> None:
        flushed_items.append(items)

    debouncer = Debouncer(debounce_ms=30.0, on_flush=on_flush)
    debouncer.add("a.md")
    time.sleep(0.01)
    debouncer.add("b.md")  # resets timer

    time.sleep(0.08)
    assert len(flushed_items) == 1
    assert flushed_items[0] == ["a.md", "b.md"]


def test_debouncer_exception_in_on_flush() -> None:
    def broken_on_flush(items: list[Any]) -> None:
        raise ValueError("flush error")

    debouncer = Debouncer(debounce_ms=10.0, on_flush=broken_on_flush)
    debouncer.add("err.md")
    debouncer._handle_timer_expired()
    assert not debouncer.is_pending()


def test_in_memory_graph_state_helpers(tmp_path: Path) -> None:
    state = InMemoryGraphState(tmp_path)

    # _determine_entity_type
    assert state._determine_entity_type(tmp_path / "docs/project/user_stories/PERSONAS.md") == "persona"
    assert state._determine_entity_type(tmp_path / "docs/project/user_stories/accepted/us-0001.md") == "story"
    assert state._determine_entity_type(tmp_path / "docs/project/product/accepted/prd-0001.md") == "prd"
    assert state._determine_entity_type(tmp_path / "docs/project/adrs/accepted/adr-0001.md") == "adr"
    assert state._determine_entity_type(tmp_path / "docs/project/backlog/refined/0001-task.md") == "task"
    assert state._determine_entity_type(tmp_path / "docs/unknown/file.txt") == ""

    # _find_task_status
    state.project_data.tasks.append(Task(id="0001", title="Task 1", status="Refined"))
    assert state._find_task_status("TASK-0001") == "Refined"
    assert state._find_task_status("TASK-9999") == ""


def test_watcher_cli_handle_command(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    docs = repo / "docs" / "project"
    docs.mkdir(parents=True)

    args = argparse.Namespace(dir=str(repo), debounce_ms=10.0, event_stream=False, once=True)
    cfg = SpecOpsConfig(root_dir=repo)
    code = handle_watch_command(args, cfg)
    assert code == 0
