"""In-memory relational graph event bus and debouncing coordination.

Governed by ADR-0001, ADR-0003, ADR-0007, ADR-0008; PRD-0005; US-0065.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .graph import process_project_graph
from .models import ADR, PRD, Persona, ProjectData, Task, UserStory
from .parser import (
    parse_adr,
    parse_personas,
    parse_prd,
    parse_priority_ranks,
    parse_task,
    parse_user_story,
)
from .topology import DirectedGraph, detect_cycles

logger = logging.getLogger(__name__)

TASK_PROMOTED = "TASK_PROMOTED"
UNANCHORED_REFERENCE_DETECTED = "UNANCHORED_REFERENCE_DETECTED"
GRAPH_CYCLE_INTRODUCED = "GRAPH_CYCLE_INTRODUCED"
NODE_UPDATED = "node_updated"
BATCHED_UPDATE = "BATCHED_UPDATE"


@dataclass
class GraphEvent:
    """Represents a structured graph change or invariant notification."""

    event_type: str
    entity_id: str | None = None
    entity_type: str | None = None
    status: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Converts event to dictionary structure."""
        base = {
            "event": self.event_type,
            "id": self.entity_id,
            "type": self.entity_type,
            "status": self.status,
            **self.payload,
        }
        return {k: v for k, v in base.items() if v is not None}

    def to_json(self) -> str:
        """Converts event to JSON string."""
        return json.dumps(self.to_dict())


class EventBus:
    """Thread-safe pub-sub event bus for in-memory graph delta events."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._listeners: dict[str, list[Callable[[GraphEvent], None]]] = {}
        self._history: list[GraphEvent] = []

    def subscribe(self, event_type: str, callback: Callable[[GraphEvent], None]) -> Callable[[], None]:
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            if callback not in self._listeners[event_type]:
                self._listeners[event_type].append(callback)
        return lambda: self.unsubscribe(event_type, callback)

    def unsubscribe(self, event_type: str, callback: Callable[[GraphEvent], None]) -> bool:
        with self._lock:
            if event_type in self._listeners and callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)
                if not self._listeners[event_type]:
                    del self._listeners[event_type]
                return True
            return False

    def publish(self, event: GraphEvent) -> int:
        with self._lock:
            self._history.append(event)
            targets: list[Callable[[GraphEvent], None]] = list(self._listeners.get(event.event_type, []))
            if "*" in self._listeners:
                for cb in self._listeners["*"]:
                    if cb not in targets:
                        targets.append(cb)

        dispatched = 0
        for callback in targets:
            try:
                callback(event)
                dispatched += 1
            except Exception as exc:
                logger.warning("Error in event listener for %s: %s", event.event_type, exc)
        return dispatched

    def clear_listeners(self) -> None:
        with self._lock:
            self._listeners.clear()

    def get_history(self, event_type: str | None = None) -> list[GraphEvent]:
        with self._lock:
            if event_type is None:
                return list(self._history)
            return [e for e in self._history if e.event_type == event_type]

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()


class Debouncer:
    """Debounces rapid bursts of items across a sliding time window."""

    def __init__(self, debounce_ms: float = 250.0, on_flush: Callable[[list[Any]], None] | None = None) -> None:
        self.debounce_ms = max(0.0, float(debounce_ms))
        self.on_flush = on_flush
        self._pending: list[Any] = []
        self._pending_set: set[Any] = set()
        self._lock = threading.RLock()
        self._timer: threading.Timer | None = None

    def add(self, item: Any) -> None:
        with self._lock:
            if item not in self._pending_set:
                self._pending_set.add(item)
                self._pending.append(item)
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            if self.on_flush is not None and self.debounce_ms > 0:
                interval_secs = self.debounce_ms / 1000.0
                self._timer = threading.Timer(interval_secs, self._handle_timer_expired)
                self._timer.daemon = True
                self._timer.start()

    def _handle_timer_expired(self) -> None:
        items = self.flush()
        if items and self.on_flush is not None:
            try:
                self.on_flush(items)
            except Exception as exc:
                logger.warning("Error in debouncer on_flush: %s", exc)

    def is_pending(self) -> bool:
        with self._lock:
            return len(self._pending) > 0

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def flush(self) -> list[Any]:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            items = list(self._pending)
            self._pending.clear()
            self._pending_set.clear()
            return items

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending.clear()
            self._pending_set.clear()


class InMemoryGraphState:
    """Synchronized in-memory project data and directed graph."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.docs_dir = self.root_dir / "docs" / "project"
        self.project_data = ProjectData()
        self.graph = DirectedGraph()
        self._file_to_entity: dict[str, tuple[str, str]] = {}
        self._ranks: dict[str, int] = {}
        self._invalid_nodes: set[str] = set()

    def load_initial_state(self) -> None:
        from .cache import RelationalGraphCacheEngine

        cache_engine = RelationalGraphCacheEngine(self.root_dir)
        self.project_data, _ = cache_engine.compile_graph(force_cold=False)
        self.graph = DirectedGraph.from_project_data(self.project_data)
        self._reindex_file_mappings()

    def _reindex_file_mappings(self) -> None:
        self._file_to_entity.clear()
        p_len = len(str(self.root_dir)) + len(os.sep)
        for s in self.project_data.stories:
            if s.file_path:
                self._file_to_entity[str(s.file_path)[p_len:]] = ("story", s.id)
        for p in self.project_data.prds:
            if p.file_path:
                self._file_to_entity[str(p.file_path)[p_len:]] = ("prd", p.id)
        for a in self.project_data.adrs:
            if a.file_path:
                self._file_to_entity[str(a.file_path)[p_len:]] = ("adr", a.id)
        for t in self.project_data.tasks:
            if t.file_path:
                self._file_to_entity[str(t.file_path)[p_len:]] = ("task", t.canonical_id)

    def _determine_entity_type(self, path: Path) -> str:
        parts = path.parts
        if path.name == "PERSONAS.md":
            return "persona"
        if "user_stories" in parts:
            return "story"
        if "product" in parts:
            return "prd"
        if "adrs" in parts:
            return "adr"
        if "backlog" in parts:
            return "task"
        return ""

    def apply_file_changes(
        self, changed_paths: list[Path], event_bus: EventBus | None = None
    ) -> list[GraphEvent]:
        events: list[GraphEvent] = []
        p_len = len(str(self.root_dir)) + len(os.sep)
        backlog_dir = self.docs_dir / "backlog"
        if backlog_dir.exists():
            self._ranks = parse_priority_ranks(backlog_dir)

        modified_tasks: list[tuple[Task, str]] = []

        for p in changed_paths:
            full_p = (self.root_dir / p).resolve() if not p.is_absolute() else p.resolve()
            rel_str = str(full_p)[p_len:] if str(full_p).startswith(str(self.root_dir)) else str(p)
            etype = self._determine_entity_type(full_p)
            if not etype:
                continue

            if not full_p.exists():
                self._remove_entity(rel_str, etype)
                continue

            try:
                if etype == "persona":
                    self.project_data.personas = parse_personas(full_p)
                elif etype == "story":
                    self._upsert_entity(parse_user_story(full_p), "story", rel_str)
                elif etype == "prd":
                    self._upsert_entity(parse_prd(full_p), "prd", rel_str)
                elif etype == "adr":
                    self._upsert_entity(parse_adr(full_p), "adr", rel_str)
                elif etype == "task":
                    m = re.match(r"^(\d+)", full_p.stem)
                    cid = f"TASK-{m.group(1).zfill(4)}" if m else full_p.stem
                    rank = self._ranks.get(cid, 999999)
                    task = parse_task(full_p, priority_rank=rank)
                    prev_status = self._find_task_status(task.canonical_id)
                    self._upsert_entity(task, "task", rel_str)
                    modified_tasks.append((task, prev_status))
            except Exception as exc:
                logger.warning("Error parsing %s: %s", rel_str, exc)

        process_project_graph(self.project_data)
        self.graph = DirectedGraph.from_project_data(self.project_data)

        # Handle task transitions
        for task, prev_status in modified_tasks:
            edges = [e for e in self.project_data.edges if e.source_id == task.canonical_id or e.target_id == task.canonical_id]
            edges_count = len(edges)
            if prev_status and prev_status != task.status and task.status == "Refined":
                events.append(
                    GraphEvent(
                        event_type=TASK_PROMOTED,
                        entity_id=task.canonical_id,
                        entity_type="task",
                        status=task.status,
                        payload={"previous_status": prev_status, "new_status": task.status, "edges_recalculated": edges_count},
                    )
                )
            events.append(
                GraphEvent(
                    event_type=NODE_UPDATED,
                    entity_id=task.canonical_id,
                    entity_type="task",
                    status=task.status,
                    payload={"edges_recalculated": edges_count},
                )
            )

        events.extend(self._validate_references())

        cycles = detect_cycles(self.graph)
        if cycles:
            events.append(
                GraphEvent(
                    event_type=GRAPH_CYCLE_INTRODUCED,
                    payload={"cycle_count": len(cycles), "cycle_path": cycles[0].cycle_path, "path_str": cycles[0].path_str},
                )
            )

        if event_bus is not None:
            for ev in events:
                event_bus.publish(ev)

        return events

    def _remove_entity(self, rel_path: str, etype: str) -> None:
        attr = "stories" if etype == "story" else f"{etype}s"
        lst = getattr(self.project_data, attr, None)
        if lst is not None:
            setattr(self.project_data, attr, [x for x in lst if not str(x.file_path).endswith(rel_path)])
        self._file_to_entity.pop(rel_path, None)

    def _find_task_status(self, cid: str) -> str:
        for t in self.project_data.tasks:
            if t.canonical_id == cid:
                return t.status
        return ""

    def _upsert_entity(self, entity: Any, etype: str, rel: str) -> None:
        attr = "stories" if etype == "story" else f"{etype}s"
        lst = getattr(self.project_data, attr)
        eid = getattr(entity, "canonical_id", getattr(entity, "id", None))
        setattr(self.project_data, attr, [x for x in lst if getattr(x, "canonical_id", getattr(x, "id", None)) != eid] + [entity])
        self._file_to_entity[rel] = (etype, eid)

    def _validate_references(self) -> list[GraphEvent]:
        events: list[GraphEvent] = []
        prd_ids = {p.id for p in self.project_data.prds}
        p_len = len(str(self.root_dir)) + len(os.sep)

        for story in self.project_data.stories:
            if story.governing_prd:
                g_prd = story.governing_prd
                clean_prd = f"PRD-{g_prd.split('-')[-1].zfill(4)}" if g_prd.split("-")[-1].isdigit() else g_prd
                if clean_prd not in prd_ids and g_prd not in prd_ids:
                    rel_p = str(story.file_path)[p_len:] if story.file_path else f"docs/project/user_stories/accepted/{story.id.lower()}.md"
                    events.append(
                        GraphEvent(
                            event_type=UNANCHORED_REFERENCE_DETECTED,
                            entity_id=story.id,
                            entity_type="story",
                            status="DRAFT_INVALID",
                            payload={"source_file": rel_p, "missing_ref": story.governing_prd, "target_type": "PRD"},
                        )
                    )
                    story.status = "DRAFT_INVALID"
                    if story.id in self.graph.nodes:
                        self.graph.nodes[story.id]["status"] = "DRAFT_INVALID"
                        self.graph.nodes[story.id]["draft_invalid"] = True
                    self._invalid_nodes.add(story.id)
                elif story.id in self._invalid_nodes:
                    self._invalid_nodes.remove(story.id)
        return events
