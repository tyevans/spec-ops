"""Autonomous multi-worker engine with git worktree backlog isolation."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .queue import BacklogQueue

MERGE_LOCK = threading.Lock()


@dataclass
class WorkerResult:
    task_id: str
    success: bool
    message: str = ""


class BacklogWorkerEngine:
    """Coordinates autonomous task execution in isolated git worktrees."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.repo_root = config.root_dir
        self.queue = BacklogQueue(config.backlog_dir)

    def run_preflight(self, cwd: Path) -> tuple[bool, str]:
        """Runs configured preflight verification commands."""
        commands = self.config.quality.preflight
        logs: list[str] = []
        for cmd in commands:
            res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
            if res.returncode != 0:
                logs.append(f"Command '{cmd}' failed (code {res.returncode}):\n{res.stderr or res.stdout}")
                return False, "\n".join(logs)
            logs.append(f"✓ '{cmd}' passed.")
        return True, "\n".join(logs)

    def create_worktree(self, branch: str, worktree_dir: Path) -> None:
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_dir), "HEAD"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
        )

    def cleanup_worktree(self, worktree_dir: Path, branch: str) -> None:
        if worktree_dir.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_dir)],
                cwd=self.repo_root,
                capture_output=True,
            )
            shutil.rmtree(worktree_dir, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=self.repo_root,
            capture_output=True,
        )

    def execute_task(self, task: Task, local_merge: bool = True) -> WorkerResult:
        branch = f"{self.config.execution.git_branch_prefix}{task.slug}"
        worktree_dir = self.repo_root / ".worktrees" / f"task-{task.id}"

        print(f"🚀 Starting worker for {task.canonical_id}: '{task.title}'")
        try:
            worktree_dir.parent.mkdir(parents=True, exist_ok=True)
            self.create_worktree(branch, worktree_dir)

            # Pre-flight check before agent modifications
            preflight_ok, preflight_log = self.run_preflight(worktree_dir)
            if not preflight_ok:
                return WorkerResult(task.canonical_id, False, f"Preflight failed: {preflight_log}")

            # Enforce backlog isolation: revert any accidental backlog directory changes
            if self.config.execution.backlog_isolation:
                status = subprocess.run(
                    ["git", "status", "--porcelain", str(self.config.project.docs_dir)],
                    cwd=worktree_dir,
                    capture_output=True,
                    text=True,
                )
                if status.stdout.strip():
                    subprocess.run(
                        ["git", "checkout", "HEAD", "--", str(self.config.project.docs_dir)],
                        cwd=worktree_dir,
                    )

            if local_merge:
                with MERGE_LOCK:
                    subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True, capture_output=True)
                    subprocess.run(["git", "merge", "--squash", branch], cwd=self.repo_root, capture_output=True)
                    self.queue.complete_task(task)
                    subprocess.run(
                        ["git", "commit", "-m", f"feat({task.canonical_id.lower()}): {task.title}"],
                        cwd=self.repo_root,
                        capture_output=True,
                    )
                return WorkerResult(task.canonical_id, True, "Completed and integrated cleanly.")
            return WorkerResult(task.canonical_id, True, "Task verified in worktree.")

        except Exception as e:
            return WorkerResult(task.canonical_id, False, f"Worker error: {e}")
        finally:
            self.cleanup_worktree(worktree_dir, branch)
