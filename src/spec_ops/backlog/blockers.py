"""Task blocker management, 'Big Unknown' resolution workflows, and spike coordination."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from ..core.models import BlockerInfo, Task
from ..spike.scaffold import create_spike
from .queue import BacklogQueue, write_task_file


def _find_task(queue: BacklogQueue, task_id: str) -> Task | None:
    """Finds a task by canonical ID or numeric string in the backlog."""
    clean = task_id.upper().strip()
    digits = re.findall(r"\d+", clean)
    num_str = digits[-1].zfill(4) if digits else ""

    for t in queue.list_all_tasks():
        if t.canonical_id == clean or t.id == task_id:
            return t
        if num_str and t.canonical_id.endswith(num_str):
            return t
    return None


def _sync_priority_status(
    backlog_dir: Path, canonical_id: str, new_status: str
) -> None:
    """Updates status in PRIORITY.md preserving path."""
    priority_file = backlog_dir / "PRIORITY.md"
    if not priority_file.exists():
        return
    content = priority_file.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(\*\*{canonical_id}\s*\().*?(\)\*\*:\s*\[`?[^`\]]+`?\]\([^)]+\))",
        re.IGNORECASE,
    )
    updated = pattern.sub(rf"\g<1>{new_status}\g<2>", content)
    if updated != content:
        priority_file.write_text(updated, encoding="utf-8")


def block_task(
    backlog_dir: Path,
    task_id: str,
    question: str,
    blocker_type: str = "unknown",
    create_spike_flag: bool = False,
    timebox: str = "2h",
    raised_by: str = "",
    root_dir: Path | None = None,
) -> tuple[bool, str, Task | None]:
    """Marks a task as blocked by an unknown or impediment, optionally scaffolding an architectural spike."""
    b_dir = Path(backlog_dir).resolve()
    root = (root_dir or b_dir.parent.parent).resolve()
    queue = BacklogQueue(b_dir)

    task = _find_task(queue, task_id)
    if not task:
        return False, f"Task {task_id} not found in backlog.", None

    if task.status in ("Complete", "Graduated"):
        return (
            False,
            f"Cannot block {task.canonical_id}: task is already Complete.",
            None,
        )

    now_iso = datetime.datetime.now().astimezone().isoformat()
    spike_cid = ""

    if create_spike_flag:
        spike_name = f"Investigate {task.title}"
        spike_task, _ = create_spike(
            root,
            name=spike_name,
            question=question,
            timebox=timebox,
            task_id=task.canonical_id,
        )
        spike_cid = spike_task.canonical_id
        if spike_cid not in task.dependencies:
            task.dependencies.append(spike_cid)

    task.status = "Blocked"
    task.blocker = BlockerInfo(
        type=blocker_type,
        question=question.strip(),
        raised_by=raised_by,
        raised_at=now_iso,
        spike_id=spike_cid,
    )

    write_task_file(task)
    _sync_priority_status(
        b_dir, task.canonical_id, f"Blocked ({blocker_type.capitalize()})"
    )

    spike_msg = (
        f" and scaffolded {spike_cid} in spikes/spike_{spike_cid.split('-')[-1]}/"
        if spike_cid
        else ""
    )
    return (
        True,
        f'Task {task.canonical_id} marked as Blocked: "{question}"{spike_msg}',
        task,
    )


def unblock_task(
    backlog_dir: Path,
    task_id: str,
    resolution: str,
    adr_id: str | None = None,
    resolved_by: str = "",
) -> tuple[bool, str, Task | None]:
    """Resolves an unknown or blocker on a task and restores ready/proposed state."""
    b_dir = Path(backlog_dir).resolve()
    queue = BacklogQueue(b_dir)

    task = _find_task(queue, task_id)
    if not task:
        return False, f"Task {task_id} not found in backlog.", None

    if not task.status.startswith("Blocked") and not task.blocker:
        return False, f"Task {task.canonical_id} is not marked as Blocked.", None

    now_iso = datetime.datetime.now().astimezone().isoformat()
    if task.blocker:
        task.blocker.resolution = resolution.strip()
        task.blocker.resolved_at = now_iso
        if adr_id:
            task.blocker.adr_id = adr_id.strip()

    # Re-evaluate prerequisites
    completed_ids = queue.get_completed_task_ids()
    unsatisfied = [
        d
        for d in task.dependencies
        if (f"TASK-{d.split('-')[-1].zfill(4)}" if d.split("-")[-1].isdigit() else d)
        not in completed_ids
    ]

    # If in refined/ folder and no unsatisfied dependencies, status becomes Refined
    if task.file_path.parent.name == "refined" and not unsatisfied:
        task.status = "Refined"
    else:
        task.status = "Proposed"

    write_task_file(task)
    _sync_priority_status(b_dir, task.canonical_id, task.status)

    adr_msg = f" (referencing {adr_id})" if adr_id else ""
    return (
        True,
        f'Task {task.canonical_id} unblocked with resolution: "{resolution}"{adr_msg}. Status: {task.status}',
        task,
    )


def list_project_blockers(backlog_dir: Path) -> list[dict[str, Any]]:
    """Aggregates all currently blocked tasks across the repository."""
    b_dir = Path(backlog_dir).resolve()
    queue = BacklogQueue(b_dir)
    blockers: list[dict[str, Any]] = []

    for t in queue.list_all_tasks():
        if t.status in ("Complete", "Graduated"):
            continue
        if t.status.startswith("Blocked") or (
            t.blocker and t.blocker.question and not t.blocker.resolution
        ):
            b_info = t.blocker
            blockers.append(
                {
                    "task_id": t.canonical_id,
                    "title": t.title,
                    "status": t.status,
                    "type": b_info.type if b_info else "unknown",
                    "question": b_info.question if b_info else "Unspecified impediment",
                    "raised_by": b_info.raised_by if b_info else "",
                    "raised_at": b_info.raised_at if b_info else "",
                    "spike_id": b_info.spike_id if b_info else "",
                    "file_path": str(t.file_path),
                }
            )

    return blockers
