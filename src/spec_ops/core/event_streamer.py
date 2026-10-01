"""Real-Time Orchestration Event Streaming and Pub/Sub Telemetry Bridge.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0010; PRD-0006; US-0115, US-0117.
Target Bounded Context: core. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eventsource import DomainEvent

logger = logging.getLogger(__name__)


@dataclass
class EventEnvelope:
    """Standardized serialization envelope for real-time pub/sub telemetry."""

    event_id: str
    event_type: str
    aggregate_id: str
    sequence_number: int
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serializes envelope to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }

    def to_json(self) -> str:
        """Serializes envelope to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventEnvelope:
        """Constructs envelope from dictionary."""
        return cls(
            event_id=str(data.get("event_id", "")),
            event_type=str(data.get("event_type", "")),
            aggregate_id=str(data.get("aggregate_id", "")),
            sequence_number=int(data.get("sequence_number", 0)),
            timestamp=str(data.get("timestamp", "")),
            payload=dict(data.get("payload", {})),
        )

    @classmethod
    def from_json(cls, json_str: str) -> EventEnvelope:
        """Constructs envelope from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_domain_event(cls, event: DomainEvent, sequence_number: int = 0) -> EventEnvelope:
        """Converts an eventsource DomainEvent into an EventEnvelope."""
        dump = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event.__dict__)
        event_id = str(getattr(event, "event_id", dump.get("event_id") or uuid.uuid4()))
        event_type = getattr(event, "event_type", type(event).__name__)
        aggregate_id = str(getattr(event, "aggregate_id", dump.get("aggregate_id") or dump.get("task_id", "")))
        if sequence_number > 0:
            seq = sequence_number
        else:
            seq = int(getattr(event, "aggregate_version", dump.get("aggregate_version", 0)))
        ts_val = getattr(event, "occurred_at", dump.get("occurred_at"))
        timestamp = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val or datetime.now(timezone.utc).isoformat())

        return cls(
            event_id=event_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            sequence_number=seq,
            timestamp=timestamp,
            payload=dump,
        )


class EventStreamer:
    """Thread-safe pub/sub event streamer and historical replay bridge."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        project_root: Path | str | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        if db_path is not None:
            self.db_path: Path | None = Path(db_path).resolve()
        else:
            default_db = self.project_root / ".specops" / "events.db"
            self.db_path = default_db if default_db.exists() else None

        self._lock = threading.RLock()
        self._async_subscribers: set[asyncio.Queue[EventEnvelope]] = set()
        self._sync_subscribers: set[queue.Queue[EventEnvelope]] = set()
        self._in_memory_events: list[EventEnvelope] = []
        self._sequence_counter: int = 0
        self._sync_sequence_from_db()

    def _sync_sequence_from_db(self) -> None:
        """Synchronizes sequence counter with highest global position in SQLite ledger."""
        if self.db_path and self.db_path.exists():
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT MAX(global_position) FROM event_stream")
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        max_pos = int(row[0])
                        with self._lock:
                            if max_pos > self._sequence_counter:
                                self._sequence_counter = max_pos
            except Exception:
                pass

    def subscribe(
        self,
        queue_instance: asyncio.Queue[EventEnvelope] | queue.Queue[EventEnvelope] | None = None,
        sync: bool = False,
    ) -> Any:
        """Subscribes to live event stream, returning an async or sync queue."""
        with self._lock:
            if sync or isinstance(queue_instance, queue.Queue):
                q: queue.Queue[EventEnvelope] = queue_instance if isinstance(queue_instance, queue.Queue) else queue.Queue()
                self._sync_subscribers.add(q)
                return q

            aq: asyncio.Queue[EventEnvelope] = queue_instance if isinstance(queue_instance, asyncio.Queue) else asyncio.Queue()
            self._async_subscribers.add(aq)
            return aq

    def subscribe_sync(
        self,
        queue_instance: queue.Queue[EventEnvelope] | None = None,
    ) -> queue.Queue[EventEnvelope]:
        """Convenience method subscribing a synchronous threading queue."""
        return self.subscribe(queue_instance=queue_instance, sync=True)

    def unsubscribe(self, q: asyncio.Queue[EventEnvelope] | queue.Queue[EventEnvelope]) -> None:
        """Removes a subscriber queue."""
        with self._lock:
            if isinstance(q, asyncio.Queue):
                self._async_subscribers.discard(q)
            if isinstance(q, queue.Queue):
                self._sync_subscribers.discard(q)

    def unsubscribe_sync(self, q: queue.Queue[EventEnvelope]) -> None:
        """Removes a synchronous subscriber queue."""
        with self._lock:
            self._sync_subscribers.discard(q)

    def publish(self, event: EventEnvelope) -> None:
        """Publishes an EventEnvelope to all connected subscribers."""
        self._sync_sequence_from_db()
        with self._lock:
            if event.sequence_number <= self._sequence_counter:
                self._sequence_counter += 1
                event.sequence_number = self._sequence_counter
            else:
                self._sequence_counter = event.sequence_number

            self._in_memory_events.append(event)
            async_targets = list(self._async_subscribers)
            sync_targets = list(self._sync_subscribers)

        for aq in async_targets:
            try:
                aq.put_nowait(event)
            except Exception as exc:
                logger.debug("Failed delivering event to async subscriber: %s", exc)

        for sq in sync_targets:
            try:
                sq.put_nowait(event)
            except Exception as exc:
                logger.debug("Failed delivering event to sync subscriber: %s", exc)

    def publish_domain_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: dict[str, Any] | None = None,
        sequence_number: int | None = None,
    ) -> EventEnvelope:
        """Constructs and broadcasts an EventEnvelope from primitive attributes."""
        self._sync_sequence_from_db()
        with self._lock:
            if sequence_number is None or sequence_number <= 0:
                self._sequence_counter += 1
                seq = self._sequence_counter
            else:
                seq = sequence_number
                if seq > self._sequence_counter:
                    self._sequence_counter = seq

        envelope = EventEnvelope(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_id=aggregate_id,
            sequence_number=seq,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=dict(payload or {}),
        )
        self.publish(envelope)
        return envelope

    def publish_event(
        self,
        domain_event: DomainEvent,
        sequence_number: int | None = None,
    ) -> EventEnvelope:
        """Converts DomainEvent and broadcasts it to the pub/sub stream."""
        envelope = EventEnvelope.from_domain_event(domain_event, sequence_number=sequence_number or 0)
        self.publish(envelope)
        return envelope

    @staticmethod
    def format_sse(envelope: EventEnvelope) -> str:
        """Formats envelope as Server-Sent Event string (event: ...\\ndata: ...\\n\\n)."""
        data = json.dumps(envelope.to_dict())
        return f"event: {envelope.event_type}\ndata: {data}\n\n"

    @staticmethod
    def format_ws(envelope: EventEnvelope) -> str:
        """Formats envelope as WebSocket JSON payload."""
        return envelope.to_json()

    def replay_events(self, limit: int = 50, since_sequence: int = 0) -> list[EventEnvelope]:
        """Replays past events from SQLite event store or in-memory store in monotonic order."""
        replayed: list[EventEnvelope] = []

        if self.db_path and self.db_path.exists():
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT global_position, event_type, aggregate_id, payload, recorded_at
                        FROM event_stream
                        WHERE global_position > ?
                        ORDER BY global_position ASC
                        LIMIT ?
                        """,
                        (since_sequence, limit),
                    )
                    rows = cursor.fetchall()
                    for pos, ev_type, agg_id, raw_payload, recorded_at in rows:
                        try:
                            p_dict = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                        except Exception:
                            p_dict = {"raw": raw_payload}
                        ev_id = str(p_dict.get("event_id", "") or uuid.uuid4())
                        ts = str(p_dict.get("occurred_at", recorded_at or datetime.now(timezone.utc).isoformat()))
                        replayed.append(
                            EventEnvelope(
                                event_id=ev_id,
                                event_type=ev_type,
                                aggregate_id=agg_id,
                                sequence_number=pos,
                                timestamp=ts,
                                payload=p_dict if isinstance(p_dict, dict) else {"data": p_dict},
                            )
                        )
                        with self._lock:
                            if pos > self._sequence_counter:
                                self._sequence_counter = pos
            except Exception as exc:
                logger.warning("Error replaying events from SQLite store (%s): %s", self.db_path, exc)

        if not replayed:
            with self._lock:
                candidates = [e for e in self._in_memory_events if e.sequence_number > since_sequence]
                candidates.sort(key=lambda e: e.sequence_number)
                replayed = candidates[:limit]

        return replayed

    def clear(self) -> None:
        """Resets in-memory subscribers, events, and sequence counter."""
        with self._lock:
            self._async_subscribers.clear()
            self._sync_subscribers.clear()
            self._in_memory_events.clear()
            self._sequence_counter = 0


_STREAMERS: dict[str, EventStreamer] = {}
_STREAMER_LOCK = threading.RLock()


def get_event_streamer(
    project_root: Path | str | None = None,
    db_path: Path | str | None = None,
    reset: bool = False,
) -> EventStreamer:
    """Returns the shared EventStreamer singleton for the specified project root."""
    root_key = str(Path(project_root or Path.cwd()).resolve())
    with _STREAMER_LOCK:
        if reset or root_key not in _STREAMERS:
            _STREAMERS[root_key] = EventStreamer(db_path=db_path, project_root=root_key)
        return _STREAMERS[root_key]


def reset_event_streamers() -> None:
    """Resets all cached EventStreamer singletons."""
    with _STREAMER_LOCK:
        _STREAMERS.clear()


__all__ = [
    "EventEnvelope",
    "EventStreamer",
    "get_event_streamer",
    "reset_event_streamers",
]
