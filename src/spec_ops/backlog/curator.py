"""JIT Backlog Curator for maintaining lean ready buffers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .queue import BacklogQueue


@dataclass
class CurationResult:
    initial_refined_count: int
    target_buffer: int
    tasks_refined: list[str] = field(default_factory=list)
    remaining_proposed_count: int = 0
    message: str = ""


class BacklogCurator:
    """Performs Just-In-Time (JIT) refinement to maintain lean ready buffers."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.queue = BacklogQueue(config.backlog_dir)
        self.target_buffer = config.architecture.buffer_target

    def curate(self) -> CurationResult:
        all_tasks = self.queue.list_all_tasks()
        refined_tasks = [t for t in all_tasks if t.status in ("Refined", "Ready")]
        proposed_tasks = [
            t for t in all_tasks
            if t.status == "Proposed" and not str(t.status).startswith("Blocked")
        ]
        completed_ids = self.queue.get_completed_task_ids()

        needed = max(0, self.target_buffer - len(refined_tasks))
        refined_ids: list[str] = []

        if needed > 0 and proposed_tasks:
            # Sort proposed by priority rank
            proposed_tasks.sort(key=lambda t: t.priority_rank)

            for task in proposed_tasks:
                if str(task.status).startswith("Blocked"):
                    continue
                if len(refined_ids) >= needed:
                    break

                # Check if dependencies are complete
                deps_satisfied = all(
                    (f"TASK-{d.split('-')[-1].zfill(4)}" if d.split('-')[-1].isdigit() else d) in completed_ids
                    for d in task.dependencies
                )

                if deps_satisfied:
                    self.queue.refine_task(task)
                    refined_ids.append(task.canonical_id)

        msg = (
            f"Refined {len(refined_ids)} task(s). Ready buffer now at "
            f"{len(refined_tasks) + len(refined_ids)}/{self.target_buffer}."
        )

        return CurationResult(
            initial_refined_count=len(refined_tasks),
            target_buffer=self.target_buffer,
            tasks_refined=refined_ids,
            remaining_proposed_count=len(proposed_tasks) - len(refined_ids),
            message=msg,
        )
