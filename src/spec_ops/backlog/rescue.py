"""Worktree rescue and human takeover manager for SpecOps."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .queue import BacklogQueue
from .worker import MERGE_LOCK, BacklogWorkerEngine


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

        # 1. Run preflight
        worker_engine = BacklogWorkerEngine(self.config)
        ok, log = worker_engine.run_preflight(info.worktree_dir)
        if not ok:
            return False, f"Preflight failed in rescued worktree:\n{log}"

        # 2. Find target task
        clean_id = f"TASK-{self._normalize_task_id(task_id_input)}"
        target_task = None
        for t in self.queue.list_all_tasks():
            if t.canonical_id == clean_id:
                target_task = t
                break

        if not target_task:
            return False, f"Task {clean_id} not found in backlog."

        # 3. Commit any uncommitted changes
        diff_res = subprocess.run(["git", "status", "--porcelain"], cwd=info.worktree_dir, capture_output=True, text=True)
        if diff_res.stdout.strip():
            subprocess.run(["git", "add", "-A"], cwd=info.worktree_dir, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"fix({clean_id.lower()}): human rescue and completion"],
                cwd=info.worktree_dir,
                check=True,
            )

        # 4. Enforce backlog isolation before merge
        if self.config.execution.backlog_isolation:
            status = subprocess.run(
                ["git", "status", "--porcelain", str(self.config.project.docs_dir)],
                cwd=info.worktree_dir,
                capture_output=True,
                text=True,
            )
            if status.stdout.strip():
                subprocess.run(["git", "checkout", "HEAD", "--", str(self.config.project.docs_dir)], cwd=info.worktree_dir)

        # 5. Merge under MERGE_LOCK
        try:
            with MERGE_LOCK:
                subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True, capture_output=True)
                subprocess.run(["git", "merge", "--squash", info.branch], cwd=self.repo_root, check=True, capture_output=True)
                self.queue.complete_task(target_task)
                subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True, capture_output=True)
                subprocess.run(
                    ["git", "commit", "-m", f"feat({clean_id.lower()}): {target_task.title} (rescued)"],
                    cwd=self.repo_root,
                    capture_output=True,
                )

            # 6. Cleanup
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

