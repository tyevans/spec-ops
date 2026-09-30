"""Automated reactive unblocking cascade and JIT buffer replenishment."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .queue import BacklogQueue, write_task_file

logger = logging.getLogger(__name__)


def normalize_task_id(tid: str) -> str:
    """Normalizes any task ID representation to canonical uppercase format."""
    clean = str(tid).strip().upper()
    if clean.startswith("TASK-"):
        num = clean[5:]
        return f"TASK-{num.zfill(4)}" if num.isdigit() else clean
    if clean.startswith("SPIKE-"):
        num = clean[6:]
        return f"SPIKE-{num.zfill(4)}" if num.isdigit() else clean
    if clean.isdigit():
        return f"TASK-{clean.zfill(4)}"
    return clean


def find_repo_root(backlog_dir: Path) -> Path:
    """Finds the root repository directory containing specops.toml or .specops."""
    curr = backlog_dir.resolve()
    for _ in range(5):
        if (curr / "specops.toml").exists() or (curr / ".git").exists() or (curr / ".specops").exists():
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent
    return backlog_dir.resolve().parent.parent.parent


@dataclass
class UnblockEvent:
    event: str = "task_unblocked"
    task_id: str = ""
    target_bc: str = "core"
    priority_rank: int = 999999

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "task_id": self.task_id,
            "target_bc": self.target_bc,
            "priority_rank": self.priority_rank,
        }


@dataclass
class CascadeResult:
    completed_task_id: str
    target_buffer: int
    unblocked_tasks: list[Task] = field(default_factory=list)
    promoted_tasks: list[Task] = field(default_factory=list)
    held_tasks: list[Task] = field(default_factory=list)
    events: list[UnblockEvent] = field(default_factory=list)
    log_messages: list[str] = field(default_factory=list)


class UnblockingCascadeEngine:
    """Evaluates downstream task dependencies and replenishes the ready buffer."""

    def __init__(
        self,
        backlog_dir: Path,
        target_buffer: int = 10,
        repo_root: Path | None = None,
        config: SpecOpsConfig | None = None,
    ):
        self.backlog_dir = backlog_dir.resolve()
        self.queue = BacklogQueue(self.backlog_dir)
        self.config = config
        self.target_buffer = target_buffer
        self.repo_root = (
            repo_root
            or (config.root_dir if config else None)
            or find_repo_root(self.backlog_dir)
        ).resolve()

    def find_unblocked_dependents(
        self,
        completed_task_id: str | None,
        all_tasks: list[Task],
        completed_ids: set[str],
    ) -> list[Task]:
        """Identifies proposed tasks whose dependencies are fully satisfied."""
        unblocked: list[Task] = []
        target_norm = normalize_task_id(completed_task_id) if completed_task_id else ""

        for task in all_tasks:
            if task.status != "Proposed":
                continue
            if str(task.status).startswith("Blocked") or getattr(task, "blocker", None):
                continue

            normalized_deps = [normalize_task_id(d) for d in task.dependencies]
            if target_norm:
                if target_norm not in normalized_deps:
                    continue

            # Check if all dependencies are in completed_ids
            if all(dep in completed_ids for dep in normalized_deps):
                unblocked.append(task)

        unblocked.sort(key=lambda t: t.priority_rank)
        return unblocked

    def cascade(
        self,
        completed_task_id: str | None = None,
        emit_events: bool = True,
    ) -> CascadeResult:
        """Executes reactive cascading unblocking and JIT buffer replenishment."""
        all_tasks = self.queue.list_all_tasks()
        completed_ids = self.queue.get_completed_task_ids()

        norm_completed = normalize_task_id(completed_task_id) if completed_task_id else ""
        if norm_completed:
            completed_ids.add(norm_completed)

        # Count tasks currently in refined buffer
        refined_tasks = [
            t for t in all_tasks
            if t.status in ("Refined", "Ready") and t.canonical_id not in completed_ids
        ]
        current_refined_count = len(refined_tasks)

        unblocked = self.find_unblocked_dependents(
            completed_task_id=completed_task_id,
            all_tasks=all_tasks,
            completed_ids=completed_ids,
        )

        available_slots = max(0, self.target_buffer - current_refined_count)
        promoted: list[Task] = []
        held: list[Task] = []
        events: list[UnblockEvent] = []
        log_messages: list[str] = []

        for task in unblocked:
            if available_slots > 0:
                # Promote to refined
                self.queue.refine_task(task)
                promoted.append(task)
                available_slots -= 1
                current_refined_count += 1

                ev = UnblockEvent(
                    event="task_unblocked",
                    task_id=task.canonical_id,
                    target_bc=task.target_bc or "core",
                    priority_rank=task.priority_rank,
                )
                events.append(ev)

                if emit_events:
                    self._emit_event(ev)
            else:
                # Buffer ceiling reached: tag unblocked: true and hold in proposed
                task.unblocked = True
                write_task_file(task)
                held.append(task)

                msg = (
                    f"{task.canonical_id} unblocked but held in proposed to "
                    f"preserve lean ready buffer ({current_refined_count}/{self.target_buffer})"
                )
                log_messages.append(msg)
                logger.info(msg)
                if emit_events:
                    print(msg)

        return CascadeResult(
            completed_task_id=completed_task_id or "",
            target_buffer=self.target_buffer,
            unblocked_tasks=unblocked,
            promoted_tasks=promoted,
            held_tasks=held,
            events=events,
            log_messages=log_messages,
        )

    def _emit_event(self, ev: UnblockEvent) -> None:
        """Emits telemetry event to stdout and appends to event files."""
        payload = ev.to_dict()
        line = json.dumps(payload)
        print(line)

        # 1. Log to .specops/events.log
        specops_dir = self.repo_root / ".specops"
        try:
            specops_dir.mkdir(parents=True, exist_ok=True)
            with (specops_dir / "events.log").open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            logger.warning("Could not write to %s/events.log: %s", specops_dir, e)

        # 2. Write to .spec-ops/events/unblocked.json and .specops/events/unblocked.json
        for dir_name in (".spec-ops", ".specops"):
            events_dir = self.repo_root / dir_name / "events"
            try:
                events_dir.mkdir(parents=True, exist_ok=True)
                (events_dir / "unblocked.json").write_text(
                    json.dumps(payload, indent=2), encoding="utf-8"
                )
            except OSError as e:
                logger.warning("Could not write to %s/unblocked.json: %s", events_dir, e)
