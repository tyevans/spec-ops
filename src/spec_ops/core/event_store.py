"""Local Embedded SQLite Event Ledger and Synchronous Filesystem Projection.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009, ADR-0010, ADR-0021; PRD-0001, PRD-0004; US-0030, US-0081.
Target Bounded Context: core. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from eventsource import DomainEvent, get_event_class_or_none

_EVENT_TYPE_MAP: dict[str, type[DomainEvent]] = {}
_PROJECTION_HANDLERS: list[Callable[[DomainEvent, Path], Path | None]] = []
_TASK_REPLAYER: Callable[[Any, str], Any] | None = None


def register_event_type(cls: type[DomainEvent]) -> None:
    """Registers an event class for deserialization."""
    _EVENT_TYPE_MAP[cls.__name__] = cls


def register_projection_handler(handler: Callable[[DomainEvent, Path], Path | None]) -> None:
    """Registers a projection handler to project events to external read models (ADR-0021)."""
    if handler not in _PROJECTION_HANDLERS:
        _PROJECTION_HANDLERS.append(handler)


def register_task_replayer(replayer: Callable[[Any, str], Any]) -> None:
    """Registers a task state replayer fold implementation (ADR-0021)."""
    global _TASK_REPLAYER
    _TASK_REPLAYER = replayer


def project_task_event_to_filesystem(event: DomainEvent, project_root: Path | str) -> Path | None:
    """Projects task domain events to read models via registered handlers (ADR-0021)."""
    root_p = Path(project_root)
    if not _PROJECTION_HANDLERS:
        try:
            import importlib

            importlib.import_module("spec_ops.backlog.projection")
        except Exception:
            pass
    for handler in _PROJECTION_HANDLERS:
        res = handler(event, root_p)
        if res is not None:
            return res
    return None


class SQLiteEventLedger:
    """Embedded SQLite Event Ledger with process-safe monotonic versioning and projections."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        project_root: Path | str | None = None,
        sync_projection: bool = True,
        projection_handler: Callable[[DomainEvent, Path], Path | None] | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.db_path = (
            Path(db_path).resolve() if db_path is not None else self.project_root / ".specops" / "events.db"
        )
        self.sync_projection = sync_projection
        self.projection_handler = projection_handler
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_stream (
                    global_position INTEGER PRIMARY KEY AUTOINCREMENT,
                    stream_id TEXT NOT NULL,
                    stream_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL DEFAULT 'Task',
                    payload TEXT NOT NULL,
                    metadata TEXT,
                    recorded_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(stream_id, stream_version)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stream_id ON event_stream(stream_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_aggregate_id ON event_stream(aggregate_id);")
            conn.commit()

    def append_events(
        self,
        stream_id: str,
        events: list[DomainEvent],
        expected_version: int | None = None,
    ) -> list[DomainEvent]:
        """Appends events monotonically to stream_id with optimistic concurrency protection."""
        if not events:
            return []

        normalized_stream_id = stream_id.strip()
        persisted_events: list[DomainEvent] = []

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MAX(stream_version) FROM event_stream WHERE stream_id = ?",
                (normalized_stream_id,),
            )
            row = cursor.fetchone()
            current_version = int(row[0]) if (row and row[0] is not None) else 0

            if expected_version is not None and expected_version != current_version:
                raise ValueError(
                    f"Optimistic concurrency violation on stream '{stream_id}': "
                    f"expected version {expected_version}, but stream is at version {current_version}"
                )

            for event in events:
                current_version += 1
                event_type = type(event).__name__
                aggregate_id = str(getattr(event, "aggregate_id", ""))
                aggregate_type = getattr(event, "aggregate_type", "Task")
                stamped_event = event.model_copy(update={"aggregate_version": current_version})
                payload = stamped_event.model_dump_json()
                metadata = json.dumps(getattr(stamped_event, "metadata", {}))

                cursor.execute(
                    """
                    INSERT INTO event_stream (
                        stream_id, stream_version, event_type, aggregate_id, aggregate_type, payload, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_stream_id,
                        current_version,
                        event_type,
                        aggregate_id,
                        aggregate_type,
                        payload,
                        metadata,
                    ),
                )
                persisted_events.append(stamped_event)
            conn.commit()

        if self.sync_projection:
            if self.projection_handler is not None:
                for event in persisted_events:
                    self.projection_handler(event, self.project_root)
            else:
                for event in persisted_events:
                    project_task_event_to_filesystem(event, self.project_root)

        try:
            from .event_streamer import get_event_streamer

            streamer = get_event_streamer(self.project_root, db_path=self.db_path)
            for event in persisted_events:
                streamer.publish_event(event)
        except Exception:
            pass

        return persisted_events

    def get_stream(self, stream_id: str) -> list[DomainEvent]:
        """Retrieves and deserializes all domain events recorded for a stream."""
        normalized_stream_id = stream_id.strip()
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT event_type, payload FROM event_stream
                WHERE stream_id = ? OR aggregate_id = ?
                ORDER BY stream_version ASC
                """,
                (normalized_stream_id, normalized_stream_id),
            )
            rows = cursor.fetchall()

        events: list[DomainEvent] = []
        for event_type, payload in rows:
            cls = get_event_class_or_none(event_type) or _EVENT_TYPE_MAP.get(event_type)
            if cls is None:
                try:
                    import importlib

                    importlib.import_module("spec_ops.backlog.events")
                    cls = get_event_class_or_none(event_type) or _EVENT_TYPE_MAP.get(event_type)
                except Exception:
                    pass
            if cls is None:
                raise ValueError(f"Unknown event type: {event_type}")
            events.append(cls.model_validate_json(payload))
        return events

    def replay_task_state(self, task_id_or_stream_id: str) -> Any:
        """Reconstitutes TaskState by delegating to registered task replayer."""
        global _TASK_REPLAYER
        if _TASK_REPLAYER is None:
            try:
                import importlib

                importlib.import_module("spec_ops.backlog.projection")
            except Exception:
                pass
        if _TASK_REPLAYER is not None:
            return _TASK_REPLAYER(self, task_id_or_stream_id)
        raise RuntimeError("No task replayer registered in event store.")

    async def append_events_async(
        self,
        stream_id: str,
        events: list[DomainEvent],
        expected_version: int | None = None,
    ) -> list[DomainEvent]:
        return await asyncio.to_thread(self.append_events, stream_id, events, expected_version)

    async def get_stream_async(self, stream_id: str) -> list[DomainEvent]:
        return await asyncio.to_thread(self.get_stream, stream_id)

    async def replay_task_state_async(self, task_id_or_stream_id: str) -> Any:
        return await asyncio.to_thread(self.replay_task_state, task_id_or_stream_id)


def append_events(
    stream_id: str,
    events: list[DomainEvent],
    expected_version: int | None = None,
    db_path: Path | str | None = None,
    project_root: Path | str | None = None,
    sync_projection: bool = True,
) -> list[DomainEvent]:
    """Convenience helper to append events into SQLite ledger."""
    ledger = SQLiteEventLedger(db_path=db_path, project_root=project_root, sync_projection=sync_projection)
    return ledger.append_events(stream_id, events, expected_version)


def get_stream(
    stream_id: str,
    db_path: Path | str | None = None,
    project_root: Path | str | None = None,
) -> list[DomainEvent]:
    """Convenience helper to retrieve stream from SQLite ledger."""
    ledger = SQLiteEventLedger(db_path=db_path, project_root=project_root)
    return ledger.get_stream(stream_id)


def replay_task_state(
    task_id_or_stream_id: str,
    db_path: Path | str | None = None,
    project_root: Path | str | None = None,
) -> Any:
    """Convenience helper to replay task state from SQLite ledger."""
    ledger = SQLiteEventLedger(db_path=db_path, project_root=project_root)
    return ledger.replay_task_state(task_id_or_stream_id)


__all__ = [
    "SQLiteEventLedger",
    "append_events",
    "get_stream",
    "project_task_event_to_filesystem",
    "register_event_type",
    "register_projection_handler",
    "register_task_replayer",
    "replay_task_state",
]
