"""Merge lock manager and transactional auto-rebase coordinator."""

from __future__ import annotations

import contextlib
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Generator

# In-process lock for threading concurrency
_THREAD_LOCK = threading.RLock()


class MergeLockManager:
    """Coordinates thread-safe and process-safe git integration under MERGE_LOCK."""

    def __init__(self, repo_root: Path, lock_file: Path | None = None):
        self.repo_root = repo_root.resolve()
        self.lock_file = lock_file or (self.repo_root / ".git" / "spec_ops_merge.lock")
        self._fd: int | None = None

    @contextlib.contextmanager
    def acquire(self, timeout: float = 60.0) -> Generator[None, None, None]:
        """Context manager to acquire both thread and file-based merge lock."""
        acquired_thread = _THREAD_LOCK.acquire(timeout=timeout)
        if not acquired_thread:
            raise TimeoutError("Timed out waiting for in-process MERGE_LOCK")

        acquired_file = False
        start_time = time.monotonic()
        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            while time.monotonic() - start_time < timeout:
                try:
                    # Open file for locking
                    self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR, 0o644)
                    try:
                        import fcntl
                        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except (ImportError, AttributeError):
                        pass
                    acquired_file = True
                    break
                except (OSError, BlockingIOError):
                    if self._fd is not None:
                        with contextlib.suppress(Exception):
                            os.close(self._fd)
                        self._fd = None
                    time.sleep(0.05)

            if not acquired_file:
                raise TimeoutError(f"Timed out waiting for file MERGE_LOCK at {self.lock_file}")

            yield

        finally:
            if self._fd is not None:
                try:
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                except (ImportError, AttributeError, OSError):
                    pass
                with contextlib.suppress(Exception):
                    os.close(self._fd)
                self._fd = None
            if self.lock_file.exists():
                with contextlib.suppress(Exception):
                    self.lock_file.unlink()
            if acquired_thread:
                _THREAD_LOCK.release()

    def is_branch_behind_main(self, branch: str, main_branch: str = "main") -> bool:
        """Determines if a task branch's merge-base is behind the current main branch HEAD."""
        base_res = subprocess.run(
            ["git", "merge-base", branch, main_branch],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        main_res = subprocess.run(
            ["git", "rev-parse", main_branch],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if base_res.returncode != 0 or main_res.returncode != 0:
            return False
        return base_res.stdout.strip() != main_res.stdout.strip()

    def rebase_branch(self, worktree_dir: Path, main_branch: str = "main") -> tuple[bool, str]:
        """Attempts to rebase worktree branch onto latest main; aborts cleanly on conflict."""
        res = subprocess.run(
            ["git", "rebase", main_branch],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return True, "Rebased successfully onto latest main."

        # Abort rebase on conflict to prevent dirty git state
        subprocess.run(
            ["git", "rebase", "--abort"],
            cwd=worktree_dir,
            capture_output=True,
        )
        conflict_msg = res.stderr.strip() or res.stdout.strip() or "Merge conflict during rebase"
        return False, conflict_msg
