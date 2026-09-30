"""Worktree rescue and human takeover manager for SpecOps."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..worker.integration import rebase_with_inference_healing, squash_merge_and_commit
from ..worker.merge_lock import MergeLockManager
from .queue import BacklogQueue
from .worker import BacklogWorkerEngine


@dataclass
class RescueInfo:
    task_id: str
    worktree_dir: Path
    branch: str
    exists: bool
    is_dirty: bool = False
    failure_feedback: str = ""
    prompt_path: Path | None = None


class WorktreeRescueManager:
    """Manages human takeover and recovery of failed or stalled autonomous worktrees."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.repo_root = config.root_dir
        self.worktrees_parent = self.repo_root / ".worktrees"
        self.queue = BacklogQueue(config.backlog_dir)

    def _normalize_task_id(self, task_id_input: str) -> str:
        clean = task_id_input.upper().replace("TASK-", "").lstrip("0")
        return clean.zfill(4) if clean else task_id_input

    def list_active_worktrees(self) -> list[RescueInfo]:
        """Lists all existing task worktrees in .worktrees/."""
        if not self.worktrees_parent.exists():
            return []

        results: list[RescueInfo] = []
        for p in sorted(self.worktrees_parent.iterdir()):
            if not p.is_dir():
                continue
            m = re.match(r"^task-(\d+)", p.name)
            if not m:
                continue

            tid_num = m.group(1).zfill(4)
            tid = f"TASK-{tid_num}"

            # Branch detection
            branch_res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=p,
                capture_output=True,
                text=True,
            )
            branch = branch_res.stdout.strip() if branch_res.returncode == 0 else ""

            # Dirty check
            status_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=p,
                capture_output=True,
                text=True,
            )
            is_dirty = bool(status_res.stdout.strip())

            # Feedback check
            prompt_file = p / ".task-prompt.md"
            feedback = ""
            if prompt_file.exists():
                text = prompt_file.read_text(encoding="utf-8", errors="ignore")
                if "## Preflight Failure Feedback" in text and "## Architectural Review Feedback" in text:
                    feedback = text.split("## Preflight Failure Feedback")[-1].strip()
                elif "## Preflight Failure Feedback" in text:
                    feedback = text.split("## Preflight Failure Feedback")[-1].strip()
                elif "## Architectural Review Feedback" in text:
                    feedback = text.split("## Architectural Review Feedback")[-1].strip()

            results.append(
                RescueInfo(
                    task_id=tid,
                    worktree_dir=p,
                    branch=branch,
                    exists=True,
                    is_dirty=is_dirty,
                    failure_feedback=feedback[:300],
                    prompt_path=prompt_file if prompt_file.exists() else None,
                )
            )

        return results

    def inspect_task(self, task_id_input: str) -> RescueInfo | None:
        """Inspects a specific task worktree."""
        tid_num = self._normalize_task_id(task_id_input)
        tid = f"TASK-{tid_num}"
        worktree_dir = self.worktrees_parent / f"task-{tid_num}"

        if not worktree_dir.exists():
            return None

        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else ""

        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        is_dirty = bool(status_res.stdout.strip())

        prompt_file = worktree_dir / ".task-prompt.md"
        feedback = ""
        if prompt_file.exists():
            text = prompt_file.read_text(encoding="utf-8", errors="ignore")
            if "## Preflight Failure Feedback" in text:
                feedback = text.split("## Preflight Failure Feedback")[-1].strip()

        return RescueInfo(
            task_id=tid,
            worktree_dir=worktree_dir,
            branch=branch,
            exists=True,
            is_dirty=is_dirty,
            failure_feedback=feedback,
            prompt_path=prompt_file if prompt_file.exists() else None,
        )

    def complete_rescue(self, task_id_input: str) -> tuple[bool, str]:
        """Runs preflight verification and merges human-rescued worktree into main."""
        info = self.inspect_task(task_id_input)
        if not info or not info.worktree_dir.exists():
            return False, f"Worktree for {task_id_input} not found."

        # 1. Find target task
        clean_id = f"TASK-{self._normalize_task_id(task_id_input)}"
        target_task = None
        for t in self.queue.list_all_tasks():
            if t.canonical_id == clean_id:
                target_task = t
                break

        if not target_task:
            return False, f"Task {clean_id} not found in backlog."

        # 2. Commit any uncommitted changes in the worktree
        for p in (info.worktree_dir / ".task-prompt.md", info.worktree_dir / ".task-review-prompt.md"):
            if p.exists():
                p.unlink()

        from ..worker.guardrails import prepare_guardrailed_commit

        diff_res = subprocess.run(["git", "status", "--porcelain"], cwd=info.worktree_dir, capture_output=True, text=True)
        if diff_res.stdout.strip():
            commit_ok, commit_msg = prepare_guardrailed_commit(
                info.worktree_dir,
                commit_msg=f"fix({clean_id.lower()}): human rescue and completion",
                allows_dependencies=getattr(target_task, "allows_dependencies", False),
            )
            if not commit_ok and "No modifications staged" not in commit_msg:
                return False, f"Failed to commit changes in rescued worktree: {commit_msg}"

        # 3. Auto-rebase onto main if behind
        lock_mgr = MergeLockManager(self.repo_root)
        if lock_mgr.is_branch_behind_main(info.branch):
            print(f"🔄 Rescued branch '{info.branch}' is behind main. Auto-rebasing onto latest main...")
            rebase_ok, rebase_msg = rebase_with_inference_healing(
                info.worktree_dir,
                target_task,
                self.config,
            )
            if not rebase_ok:
                return False, f"Rebase conflict against main during rescue: {rebase_msg}"

        # Ensure active repository profiles (e.g. security) are synchronized in rescued worktree
        if (
            self.config.security is not None
            or (self.repo_root / "docs" / "project" / "SECURITY.md").exists()
        ):
            from ..profiles.security import sync_security_profile, validate_security_policy

            sec_ok, _ = validate_security_policy(info.worktree_dir)
            if not sec_ok:
                sync_security_profile(info.worktree_dir, sync_worktrees=False)

        # 4. Run preflight
        worker_engine = BacklogWorkerEngine(self.config)
        ok, log = worker_engine.run_preflight(info.worktree_dir, task=target_task)
        if not ok:
            return False, f"Preflight failed in rescued worktree:\n{log}"

        # 5. Enforce backlog isolation before merge
        if self.config.execution.backlog_isolation:
            try:
                backlog_target = str(self.config.backlog_dir.relative_to(self.config.root_dir))
            except ValueError:
                backlog_target = str(self.config.backlog_dir)
            status = subprocess.run(
                ["git", "status", "--porcelain", backlog_target],
                cwd=info.worktree_dir,
                capture_output=True,
                text=True,
            )
            if status.stdout.strip():
                subprocess.run(["git", "checkout", "HEAD", "--", backlog_target], cwd=info.worktree_dir)

        # 6. Merge under MERGE_LOCK
        try:
            with lock_mgr.acquire(timeout=120.0):
                if lock_mgr.is_branch_behind_main(info.branch):
                    rebase_ok, rebase_msg = rebase_with_inference_healing(
                        info.worktree_dir,
                        target_task,
                        self.config,
                    )
                    if not rebase_ok:
                        return False, f"Rebase conflict against main under merge lock: {rebase_msg}"

                merge_ok, merge_msg = squash_merge_and_commit(
                    self.repo_root,
                    info.branch,
                    f"feat({clean_id.lower()}): {target_task.title} (rescued)",
                    on_staged=lambda: self.queue.complete_task(target_task),
                )
                if not merge_ok:
                    return False, f"Merge failed: {merge_msg}"

            # 7. Cleanup
            worker_engine.cleanup_worktree(info.worktree_dir, info.branch, delete_branch=True)
            return True, f"Successfully verified, merged, and completed {clean_id}."
        except Exception as e:
            return False, f"Merge failed: {e}"

    def discard_worktree(self, task_id_input: str) -> tuple[bool, str]:
        """Safely removes a worktree and deletes its branch."""
        info = self.inspect_task(task_id_input)
        if not info or not info.worktree_dir.exists():
            return False, f"Worktree for {task_id_input} not found."

        worker_engine = BacklogWorkerEngine(self.config)
        worker_engine.cleanup_worktree(info.worktree_dir, info.branch, delete_branch=True)
        return True, f"Discarded worktree for {info.task_id}."

    def prune_all_worktrees(self) -> int:
        """Safely cleans up all worktrees under .worktrees/ and prunes git records."""
        count = 0
        worker_engine = BacklogWorkerEngine(self.config)
        for info in self.list_active_worktrees():
            worker_engine.cleanup_worktree(info.worktree_dir, info.branch, delete_branch=True)
            count += 1
        subprocess.run(["git", "worktree", "prune"], cwd=self.repo_root, capture_output=True)
        return count

