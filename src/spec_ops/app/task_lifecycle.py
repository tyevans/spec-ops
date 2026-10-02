"""Task lifecycle application service.

Coordinates task progression across backlog, security, and worker bounded contexts.
Governed by ADR-0007 and ADR-0021.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task


@dataclass
class TaskIntegrationResult:
    """Outcome of a task completion and integration workflow."""

    task_id: str
    success: bool
    message: str
    branch: str = ""
    commit_sha: str = ""
    details: dict[str, Any] | None = None


class TaskLifecycleService:
    """Application service coordinating multi-context task workflows."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.root_dir = config.root_dir
        self.backlog_dir = config.backlog_dir

    def verify_ready_for_completion(self, task_id: str) -> tuple[bool, str, Task | None]:
        """Verifies whether a task satisfies all preflight gates and human sign-offs."""
        from ..backlog.queue import BacklogQueue

        queue = BacklogQueue(self.backlog_dir)
        clean_id = f"TASK-{task_id.zfill(4)}" if task_id.isdigit() else task_id.upper()
        task = next((t for t in queue.list_all_tasks() if t.canonical_id == clean_id or t.id == task_id), None)
        if not task:
            return False, f"Task {task_id} not found in backlog queue.", None

        # 1. Dual custody sign-off check via security context
        from ..security.dual_custody import is_signed_off

        signed_off, sign_msg = is_signed_off(self.config, task.canonical_id)
        if not signed_off:
            return False, f"Dual-custody verification failed: {sign_msg}", task

        return True, "Task satisfies completion gates.", task

    def complete_task(
        self,
        task_id: str,
        author: str | None = None,
        bypass_preflight: bool = False,
    ) -> TaskIntegrationResult:
        """Executes full task integration workflow under merge lock."""
        ready, msg, task = self.verify_ready_for_completion(task_id)
        if not ready or not task:
            return TaskIntegrationResult(
                task_id=task_id,
                success=False,
                message=msg,
            )

        clean_id = task.canonical_id
        branch_name = task.branch or f"feat/{clean_id.lower()}"

        from ..worker.merge_lock import MergeLockManager

        lock_mgr = MergeLockManager(self.root_dir)

        # Acquire merge lock to prevent race conditions during integration
        with lock_mgr.acquire(owner=f"task-lifecycle-{clean_id}"):
            from ..worker.commits import format_task_commit_message
            from ..worker.integration import squash_merge_and_commit

            commit_msg = format_task_commit_message(
                task_id=clean_id,
                title=task.title,
                governing_prds=task.governing_prds,
                governing_stories=task.governing_stories,
            )

            success, merge_msg = squash_merge_and_commit(
                root_dir=self.root_dir,
                branch_name=branch_name,
                commit_message=commit_msg,
                author=author,
            )
            if not success:
                return TaskIntegrationResult(
                    task_id=clean_id,
                    success=False,
                    message=f"Git merge failed under MERGE_LOCK: {merge_msg}",
                    branch=branch_name,
                )

            # Transition task to complete in backlog queue
            from ..backlog.queue import BacklogQueue

            queue = BacklogQueue(self.backlog_dir)
            completed_task = queue.transition_task(clean_id, "Complete")

            return TaskIntegrationResult(
                task_id=clean_id,
                success=True,
                message="Task successfully integrated and completed under MERGE_LOCK.",
                branch=branch_name,
                details={"completed_task_id": clean_id},
            )

    def complete_task_with_gate(
        self,
        task: Task,
        base_branch: str = "main",
        repo_root: Path | None = None,
        config: Any | None = None,
    ) -> tuple[bool, str]:
        """Orchestrates git integration under merge lock and gates task completion."""
        root = (repo_root or self.root_dir).resolve()
        cfg = config or self.config

        from ..worker.merge_lock import MergeLockManager
        from ..worker.commits import format_task_commit_message
        from ..worker.integration import squash_merge_and_commit
        from ..backlog.queue import BacklogQueue

        lock_mgr = MergeLockManager(root)
        with lock_mgr.acquire(timeout=120.0):
            queue = BacklogQueue(cfg.backlog_dir)

            def _git_merge_runner(root_p, tgt_b, base_b, t, buf, on_staged_fn):
                commit_msg = format_task_commit_message(t)
                return squash_merge_and_commit(
                    root_p,
                    tgt_b,
                    commit_msg,
                    on_staged=on_staged_fn,
                    main_branch=base_b,
                )

            return queue.complete_task_with_gate(
                task,
                base_branch=base_branch,
                repo_root=root,
                config=cfg,
                integration_runner=_git_merge_runner,
            )
