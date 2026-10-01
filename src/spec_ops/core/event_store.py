"""Local Embedded SQLite Event Ledger and Synchronous Filesystem Projection.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009, ADR-0010; PRD-0001, PRD-0004; US-0030, US-0081.
Target Bounded Context: core. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from eventsource import DomainEvent, get_event_class_or_none

from ..backlog.decider import TaskDecider, TaskState
from ..backlog.events import (
    TaskClaimed,
    TaskCompleted,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
)
from ..backlog.queue import write_task_file
from ..core.models import Task
from ..core.parser import parse_task

EVENT_TYPE_MAP: dict[str, type[DomainEvent]] = {
    "TaskProposed": TaskProposed,
    "TaskRefined": TaskRefined,
    "TaskClaimed": TaskClaimed,
    "TaskReleased": TaskReleased,
    "TaskPreflightRecorded": TaskPreflightRecorded,
    "TaskCompleted": TaskCompleted,
}


def _slugify(title: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:50] or "task"


def _resolve_backlog_dir(project_root: Path | str) -> Path:
    root = Path(project_root).resolve()
    standard = root / "docs" / "project" / "backlog"
    if standard.exists() or (root / "docs").exists():
        return standard
    if any((root / d).exists() for d in ("proposed", "refined", "complete", "PRIORITY.md")):
        return root
    return standard


def _find_task_file(backlog_dir: Path, num_str: str) -> Path | None:
    if not backlog_dir.exists():
        return None
    for folder_name in ("proposed", "refined", "complete"):
        folder = backlog_dir / folder_name
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            if not p.name.startswith(".") and p.is_file():
                digits = re.findall(r"\d+", p.stem)
                if digits and digits[0].zfill(4) == num_str:
                    return p
    return None


def _sync_priority_entry(backlog_dir: Path, canonical_id: str, new_status: str, new_folder: str, filename: str) -> None:
    priority_file = backlog_dir / "PRIORITY.md"
    if not priority_file.exists():
        return
    content = priority_file.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(\*\*{canonical_id}\s*\()(?:[^\)]+)(\)\*\*:\s*\[`?[^`\]]+`?\]\()(?:[^/]+)(/[^)]+\))",
        re.IGNORECASE,
    )
    if pattern.search(content):
        updated = pattern.sub(rf"\g<1>{new_status}\g<2>{new_folder}\g<3>", content)
        if updated != content:
            priority_file.write_text(updated, encoding="utf-8")
    else:
        entry = f"- **{canonical_id} ({new_status})**: [`{Path(filename).stem}`]({new_folder}/{filename})"
        lines = content.splitlines() + [entry]
        priority_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _move_and_save_task(task: Task, folder: str, backlog_dir: Path, status: str, canonical_id: str) -> Path:
    target_dir = backlog_dir / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    task.status = status
    dest = target_dir / task.file_path.name
    if task.file_path.exists() and task.file_path.resolve() != dest.resolve():
        task.file_path.rename(dest)
    task.file_path = dest
    write_task_file(task)
    _sync_priority_entry(backlog_dir, canonical_id, status, folder, dest.name)
    return dest


def project_task_event_to_filesystem(event: DomainEvent, project_root: Path | str) -> Path | None:
    """Synchronously projects task aggregate domain events into backlog markdown read models."""
    task_id = str(getattr(event, "task_id", "")).strip()
    if not task_id:
        return None

    digits = re.search(r"\d+", task_id)
    num_str = digits.group(0).zfill(4) if digits else task_id
    canonical_id = f"TASK-{num_str}"
    backlog_dir = _resolve_backlog_dir(project_root)
    existing = _find_task_file(backlog_dir, num_str)

    match event:
        case TaskProposed():
            if existing:
                task = parse_task(existing)
                task.title = event.title
                if event.body:
                    task.body = event.body
                task.dependencies = list(event.dependencies)
                task.governing_adrs = list(event.governing_adrs)
                task.governing_prds = list(event.governing_prds)
                task.governing_stories = list(event.governing_stories)
                task.target_bc = event.target_bc
                return _move_and_save_task(task, "proposed", backlog_dir, "Proposed", canonical_id)
            target_dir = backlog_dir / "proposed"
            target_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(event.title)
            dest = target_dir / f"{num_str}-{slug}.md"
            task = Task(
                id=num_str,
                title=event.title,
                status="Proposed",
                dependencies=list(event.dependencies),
                governing_adrs=list(event.governing_adrs),
                governing_prds=list(event.governing_prds),
                governing_stories=list(event.governing_stories),
                target_bc=event.target_bc,
                body=event.body or f"# {canonical_id}: {event.title}\n",
                file_path=dest,
            )
            write_task_file(task)
            _sync_priority_entry(backlog_dir, canonical_id, "Proposed", "proposed", dest.name)
            return dest

        case TaskRefined() if existing:
            return _move_and_save_task(parse_task(existing), "refined", backlog_dir, "Refined", canonical_id)

        case TaskClaimed() if existing:
            task = parse_task(existing)
            task.status = "Claimed"
            task.claimed_by = event.claimed_by
            task.branch = event.branch
            write_task_file(task)
            _sync_priority_entry(backlog_dir, canonical_id, "Claimed", existing.parent.name, existing.name)
            return existing

        case TaskReleased() if existing:
            task = parse_task(existing)
            task.claimed_by, task.branch = "", ""
            return _move_and_save_task(task, "refined", backlog_dir, "Refined", canonical_id)

        case TaskCompleted() if existing:
            task = parse_task(existing)
            task.claimed_by, task.branch = "", ""
            if getattr(event, "commit_hash", ""):
                task.completed_at = getattr(task, "completed_at", "") or "now"
            if getattr(event, "pr_url", ""):
                task.pr_url = event.pr_url
            return _move_and_save_task(task, "complete", backlog_dir, "Complete", canonical_id)

        case _:
            return existing


class SQLiteEventLedger:
    """Embedded SQLite Event Ledger with process-safe monotonic versioning and projections."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        project_root: Path | str | None = None,
        sync_projection: bool = True,
    ) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.db_path = Path(db_path).resolve() if db_path is not None else self.project_root / ".specops" / "events.db"
        self.sync_projection = sync_projection
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
                    (normalized_stream_id, current_version, event_type, aggregate_id, aggregate_type, payload, metadata),
                )
                persisted_events.append(stamped_event)
            conn.commit()

        if self.sync_projection:
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
            cls = get_event_class_or_none(event_type) or EVENT_TYPE_MAP.get(event_type)
            if cls is None:
                raise ValueError(f"Unknown event type: {event_type}")
            events.append(cls.model_validate_json(payload))
        return events

    def replay_task_state(self, task_id_or_stream_id: str) -> TaskState:
        """Reconstitutes TaskState by folding all events in the aggregate stream."""
        events = self.get_stream(task_id_or_stream_id)
        state = TaskDecider.initial_state()
        for event in events:
            state = TaskDecider.evolve(state, event)
        return state

    async def append_events_async(
        self,
        stream_id: str,
        events: list[DomainEvent],
        expected_version: int | None = None,
    ) -> list[DomainEvent]:
        return await asyncio.to_thread(self.append_events, stream_id, events, expected_version)

    async def get_stream_async(self, stream_id: str) -> list[DomainEvent]:
        return await asyncio.to_thread(self.get_stream, stream_id)

    async def replay_task_state_async(self, task_id_or_stream_id: str) -> TaskState:
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
) -> TaskState:
    """Convenience helper to replay task state from SQLite ledger."""
    ledger = SQLiteEventLedger(db_path=db_path, project_root=project_root)
    return ledger.replay_task_state(task_id_or_stream_id)


__all__ = [
    "EVENT_TYPE_MAP",
    "SQLiteEventLedger",
    "append_events",
    "get_stream",
    "project_task_event_to_filesystem",
    "replay_task_state",
]
