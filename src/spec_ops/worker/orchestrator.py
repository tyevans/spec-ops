"""Concurrent multi-worker batch orchestrator with dynamic queue unblocking."""

from __future__ import annotations

import concurrent.futures
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..backlog.commands import ClaimTask, ReleaseTask
from ..backlog.decider import TaskDecider, TaskState
from ..backlog.queue import BacklogQueue, write_task_file
from ..config.models import SpecOpsConfig
from .merge_lock import MergeLockManager

if TYPE_CHECKING:
    from ..backlog.worker import BacklogWorkerEngine, WorkerResult


@dataclass
class BatchCycleReport:
    """Summary of batch cycle execution."""

    tasks_executed: int
    tasks_succeeded: list[str] = field(default_factory=list)
    tasks_failed: list[str] = field(default_factory=list)
    interrupted: bool = False
    message: str = ""


class BatchCycleOrchestrator:
    """Coordinates concurrent worker pool execution with dynamic task unblocking."""

    def __init__(
        self,
        config: SpecOpsConfig,
        max_concurrency: int = 3,
        max_tasks: int | None = None,
        drain: bool = False,
        dry_run: bool = False,
        no_merge: bool = False,
        skip_review: bool = False,
    ):
        self.config = config
        self.repo_root = config.root_dir
        self.queue = BacklogQueue(config.backlog_dir)
        from ..backlog.worker import BacklogWorkerEngine
        self.worker_engine = BacklogWorkerEngine(config)
        self.lock_mgr = MergeLockManager(self.repo_root)

        self.max_concurrency = max(1, max_concurrency)
        self.max_tasks = max_tasks if (max_tasks is not None and max_tasks > 0) else None
        self.drain = drain
        self.dry_run = dry_run
        self.no_merge = no_merge
        self.skip_review = skip_review

        self._shutdown_requested = False
        self._orig_sigint: Any = None
        self._orig_sigterm: Any = None

    def setup_signal_handlers(self) -> None:
        """Installs graceful shutdown traps for SIGINT and SIGTERM."""
        try:
            self._orig_sigint = signal.getsignal(signal.SIGINT)
            self._orig_sigterm = signal.getsignal(signal.SIGTERM)

            def _handle_signal(sig: int, _frame: Any) -> None:
                print("\n⚠️ Graceful shutdown requested. Allowing active worktrees to checkpoint...")
                self._shutdown_requested = True
                try:
                    from ..backlog.worker import request_global_shutdown
                    request_global_shutdown()
                except Exception:
                    pass

            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            # Non-main thread or unsupported platform
            pass

    def restore_signal_handlers(self) -> None:
        """Restores original signal handlers."""
        try:
            if self._orig_sigint is not None:
                signal.signal(signal.SIGINT, self._orig_sigint)
            if self._orig_sigterm is not None:
                signal.signal(signal.SIGTERM, self._orig_sigterm)
        except (ValueError, AttributeError):
            pass

    def _record_claim(self, task_id: str, worker_id: str, branch: str) -> None:
        """Records task claim using TaskDecider and updates task frontmatter."""
        all_tasks = self.queue.list_all_tasks()
        target = next((t for t in all_tasks if t.canonical_id == task_id), None)
        if not target:
            return
        state = TaskState(
            task_id=target.canonical_id,
            title=target.title,
            status="Refined",
            dependencies=target.dependencies,
        )
        try:
            events = TaskDecider.decide(
                ClaimTask(task_id=task_id, claimed_by=worker_id, branch=branch),
                state,
            )
            for ev in events:
                state = TaskDecider.evolve(state, ev)
            target.claimed_by = state.claimed_by
            target.branch = state.branch
        except Exception:
            target.claimed_by = worker_id
            target.branch = branch
        write_task_file(target)

    def _record_release(self, task_id: str, reason: str = "") -> None:
        """Releases task claim on failure or interruption."""
        all_tasks = self.queue.list_all_tasks()
        target = next((t for t in all_tasks if t.canonical_id == task_id), None)
        if not target:
            return
        target.claimed_by = ""
        target.branch = ""
        write_task_file(target)

    def run(self) -> BatchCycleReport:
        """Executes concurrent workers, dynamically unblocking ready tasks."""
        self.setup_signal_handlers()

        succeeded: list[str] = []
        failed: list[str] = []
        active_futures: dict[concurrent.futures.Future[WorkerResult], str] = {}

        print(
            f"⚡ Starting multi-worker orchestrator (concurrency: {self.max_concurrency}, "
            f"max_tasks: {self.max_tasks or 'unlimited/drain'})..."
        )

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrency)
        try:
            while not self._shutdown_requested:
                # 1. Calculate available capacity
                if self.max_tasks is not None:
                    accounted = len(succeeded) + len(failed) + len(active_futures)
                    remaining = max(0, self.max_tasks - accounted)
                    slots = min(self.max_concurrency - len(active_futures), remaining)
                else:
                    slots = self.max_concurrency - len(active_futures)

                # 2. Query dynamic ready unblocked tasks
                if slots > 0:
                    dispatched_ids = set(active_futures.values()) | set(failed)
                    ready_tasks = [
                        t for t in self.queue.get_ready_unblocked_tasks()
                        if t.canonical_id not in dispatched_ids
                    ]
                    to_dispatch = ready_tasks[:slots]

                    for task in to_dispatch:
                        worker_id = f"worker-{len(active_futures) + 1}"
                        branch = f"{self.config.execution.git_branch_prefix}{task.slug}"
                        self._record_claim(task.canonical_id, worker_id, branch)

                        future = executor.submit(
                            self.worker_engine.execute_task,
                            task,
                            local_merge=not self.no_merge,
                            dry_run=self.dry_run,
                            skip_review=self.skip_review,
                        )
                        active_futures[future] = task.canonical_id

                # 3. If no active work and no tasks to dispatch, queue is drained
                if not active_futures:
                    break

                # 4. Wait for at least one worker to complete
                done, _ = concurrent.futures.wait(
                    active_futures.keys(),
                    timeout=0.2,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )

                for fut in done:
                    task_id = active_futures.pop(fut)
                    try:
                        res: WorkerResult = fut.result()
                        if res.success:
                            succeeded.append(task_id)
                            print(f"✅ Task {task_id} completed successfully.")
                        else:
                            failed.append(task_id)
                            self._record_release(task_id, reason=res.message)
                            print(f"❌ Task {task_id} failed: {res.message}")
                    except Exception as exc:
                        failed.append(task_id)
                        self._record_release(task_id, reason=str(exc))
                        print(f"❌ Task {task_id} raised unexpected error: {exc}")

                # 5. Break if max_tasks quota satisfied and no active work remaining
                if (
                    self.max_tasks is not None
                    and (len(succeeded) + len(failed)) >= self.max_tasks
                    and not active_futures
                ):
                    break

            # Handle graceful shutdown wait
            if self._shutdown_requested and active_futures:
                print("⏳ Waiting for in-flight tasks to finish cleanly...")
                for fut in concurrent.futures.as_completed(active_futures.keys(), timeout=30):
                    task_id = active_futures[fut]
                    try:
                        res = fut.result()
                        if res.success:
                            succeeded.append(task_id)
                        else:
                            failed.append(task_id)
                    except Exception:
                        failed.append(task_id)

        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            self.restore_signal_handlers()

        total = len(succeeded) + len(failed)
        status_msg = (
            f"Batch cycle finished: {total} tasks executed ({len(succeeded)} succeeded, "
            f"{len(failed)} failed)."
        )
        if self._shutdown_requested:
            status_msg += " (Interrupted via signal)."
        print(f"\n📊 {status_msg}")

        return BatchCycleReport(
            tasks_executed=total,
            tasks_succeeded=succeeded,
            tasks_failed=failed,
            interrupted=self._shutdown_requested,
            message=status_msg,
        )
