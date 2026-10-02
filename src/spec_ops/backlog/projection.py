"""Synchronous filesystem projection and decider replaying for task domain events.

Governed by ADR-0001, ADR-0007, ADR-0021; PRD-0001, PRD-0004; US-0030, US-0081.
Target Bounded Context: backlog. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from eventsource import DomainEvent

from ..core.event_store import register_projection_handler, register_task_replayer
from ..core.models import Task
from ..core.parser import parse_task
from .decider import TaskDecider, TaskState
from .events import (
    TaskClaimed,
    TaskCompleted,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
)
from .queue import write_task_file


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


def _sync_priority_entry(
    backlog_dir: Path, canonical_id: str, new_status: str, new_folder: str, filename: str
) -> None:
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


def replay_task_state_impl(ledger: Any, task_id_or_stream_id: str) -> TaskState:
    events = ledger.get_stream(task_id_or_stream_id)
    state = TaskDecider.initial_state()
    for event in events:
        state = TaskDecider.evolve(state, event)
    return state


def replay_task_state(
    task_id_or_stream_id: str,
    db_path: Path | str | None = None,
    project_root: Path | str | None = None,
) -> TaskState:
    from ..core.event_store import SQLiteEventLedger

    ledger = SQLiteEventLedger(db_path=db_path, project_root=project_root)
    return replay_task_state_impl(ledger, task_id_or_stream_id)


# Auto-register projection handler and replayer with core event store
register_projection_handler(project_task_event_to_filesystem)
register_task_replayer(replay_task_state_impl)

__all__ = [
    "project_task_event_to_filesystem",
    "replay_task_state",
    "replay_task_state_impl",
]
