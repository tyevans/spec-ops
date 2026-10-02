"""Cross-process file locking and transactional concurrency protection for backlog operations."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Generator

# In-process reentrant lock for thread safety
_THREAD_LOCK = threading.RLock()


def is_pid_alive(pid: int) -> bool:
    """Checks whether a process ID currently exists in the OS process table."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_lock_pid(lock_path: Path) -> int | None:
    """Extracts PID from a lock file supporting numeric text or JSON format."""
    try:
        if not lock_path.exists():
            return None
        text = lock_path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "pid" in data:
                return int(data["pid"])
        except Exception:
            pass
        m = re.search(r"\b(\d+)\b", text)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def recover_stale_lock(lock_path: Path, max_age: float = 300.0) -> bool:
    """Reclaims a stale lockfile if held by a dead process or if expired."""
    if not lock_path.exists():
        return False
    pid = read_lock_pid(lock_path)
    if pid is not None and not is_pid_alive(pid):
        msg = f"Recovered stale backlog lock from terminated process {pid}"
        print(f"Warning: {msg}", file=sys.stderr)
        with contextlib.suppress(Exception):
            lock_path.unlink()
        return True
    try:
        age = time.time() - lock_path.stat().st_mtime
        if age > max_age:
            msg = f"Recovered stale backlog lock expired after {max_age}s"
            print(f"Warning: {msg}", file=sys.stderr)
            with contextlib.suppress(Exception):
                lock_path.unlink()
            return True
    except Exception:
        pass
    return False


def find_repo_root(path: Path) -> Path:
    """Resolves repository root from a target path by looking for project root markers."""
    cur = path.resolve()
    start_dir = cur if cur.is_dir() else cur.parent
    for parent in [start_dir, *start_dir.parents]:
        if (
            (parent / ".git").exists()
            or (parent / "docs" / "project").exists()
            or (parent / ".spec-ops").exists()
            or (parent / ".specops").exists()
        ):
            return parent
    return start_dir


class TwoPhaseFileTransaction:
    """Two-phase transactional file updates with atomic commit and crash rollback."""

    def __init__(self, target_path: Path, repo_root: Path | None = None):
        self.target_path = target_path.resolve()
        self.repo_root = (repo_root or find_repo_root(self.target_path)).resolve()
        self.staging_dir = self.repo_root / ".spec-ops" / "tmp"
        self.staging_file = self.staging_dir / f"{self.target_path.name}.tmp"
        self.backup_dir = self.repo_root / ".spec-ops" / "backups"
        self.backup_file = self.backup_dir / f"{self.target_path.name}.bak"

    def prepare(self, content: str) -> Path:
        """Phase 1: Backs up original file and stages new content in temporary file."""
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        if self.target_path.exists():
            shutil.copy2(self.target_path, self.backup_file)

        # Write to staging file
        fd = os.open(str(self.staging_file), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
        try:
            os.write(fd, content.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

        return self.staging_file

    def commit(self) -> None:
        """Phase 2: Atomically replaces target with staged file and cleans up backup."""
        if not self.staging_file.exists():
            raise FileNotFoundError(f"Staging file {self.staging_file} not found for commit")
        os.replace(self.staging_file, self.target_path)
        with contextlib.suppress(Exception):
            if self.backup_file.exists():
                self.backup_file.unlink()

    def rollback(self) -> None:
        """Rolls back target file from backup and cleans up staging file."""
        if self.backup_file.exists():
            shutil.copy2(self.backup_file, self.target_path)
            with contextlib.suppress(Exception):
                self.backup_file.unlink()
        with contextlib.suppress(Exception):
            if self.staging_file.exists():
                self.staging_file.unlink()


def atomic_write(target_path: Path, content: str, repo_root: Path | None = None) -> Path:
    """Executes a two-phase atomic write on a file with crash rollback protection."""
    tx = TwoPhaseFileTransaction(target_path, repo_root=repo_root)
    tx.prepare(content)
    tx.commit()
    return target_path


def recover_transactions(repo_root: Path) -> None:
    """Scans staging and backup directories, restoring corrupt targets and cleaning up."""
    for base in [repo_root / ".spec-ops", repo_root / ".specops"]:
        tmp_dir = base / "tmp"
        if tmp_dir.exists():
            for p in tmp_dir.glob("*.tmp"):
                with contextlib.suppress(Exception):
                    p.unlink()

        bak_dir = base / "backups"
        if bak_dir.exists():
            for bak in bak_dir.glob("*.bak"):
                orig_name = bak.stem
                restored = False
                candidates = [
                    repo_root / "docs" / "project" / "backlog" / orig_name,
                    repo_root / "docs" / "project" / orig_name,
                    repo_root / orig_name,
                ]
                for candidate in candidates:
                    if candidate.exists() and candidate.stat().st_size == 0:
                        shutil.copy2(bak, candidate)
                        restored = True
                        break
                if not restored:
                    for candidate in candidates:
                        if candidate.parent.exists():
                            shutil.copy2(bak, candidate)
                            restored = True
                            break
                with contextlib.suppress(Exception):
                    bak.unlink()


class BacklogLock:
    """OS-level advisory file locking and stale recovery for queue concurrency."""

    def __init__(
        self,
        repo_root: Path,
        lock_file: Path | None = None,
        stale_timeout: float = 300.0,
    ):
        self.repo_root = repo_root.resolve()
        self.stale_timeout = stale_timeout
        if lock_file is not None:
            self._lock_paths = [lock_file.resolve()]
        else:
            self._lock_paths = [
                self.repo_root / ".spec-ops" / "locks" / "backlog.lock",
                self.repo_root / ".specops" / "locks" / "queue.lock",
            ]
        self._open_fds: list[tuple[int, Path]] = []

    @contextlib.contextmanager
    def acquire(self, timeout: float = 30.0) -> Generator[None, None, None]:
        """Context manager acquiring both thread and advisory OS flock across lock paths."""
        acquired_thread = _THREAD_LOCK.acquire(timeout=timeout)
        if not acquired_thread:
            raise TimeoutError("Timed out waiting for in-process backlog lock")

        acquired_files = False
        start_time = time.monotonic()
        sleep_interval = 0.02

        try:
            for p in self._lock_paths:
                p.parent.mkdir(parents=True, exist_ok=True)

            while time.monotonic() - start_time < timeout:
                # 1. Stale lock auto-recovery check
                for p in self._lock_paths:
                    recover_stale_lock(p, max_age=self.stale_timeout)

                # 2. Attempt flock on each candidate path
                succeeded_fds: list[tuple[int, Path]] = []
                locked_all = True
                for p in self._lock_paths:
                    try:
                        fd = os.open(str(p), os.O_CREAT | os.O_RDWR, 0o644)
                        try:
                            import fcntl
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except (ImportError, AttributeError):
                            pass
                        succeeded_fds.append((fd, p))
                    except (OSError, BlockingIOError):
                        locked_all = False
                        break

                if locked_all:
                    self._open_fds = succeeded_fds
                    # Write current PID into each lock file
                    cur_pid_str = f"{os.getpid()}\n"
                    for fd, _ in self._open_fds:
                        os.ftruncate(fd, 0)
                        os.lseek(fd, 0, os.SEEK_SET)
                        os.write(fd, cur_pid_str.encode("utf-8"))
                        with contextlib.suppress(OSError):
                            os.fsync(fd)
                    acquired_files = True
                    break
                else:
                    # Release any partially acquired fds
                    for fd, _ in succeeded_fds:
                        with contextlib.suppress(Exception):
                            import fcntl
                            fcntl.flock(fd, fcntl.LOCK_UN)
                            os.close(fd)
                    time.sleep(min(sleep_interval, 0.2))
                    sleep_interval *= 1.2

            if not acquired_files:
                paths_str = ", ".join(str(p) for p in self._lock_paths)
                raise TimeoutError(f"Timed out waiting for backlog lock at {paths_str}")

            yield

        finally:
            for fd, path in self._open_fds:
                try:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except (ImportError, AttributeError, OSError):
                    pass
                with contextlib.suppress(Exception):
                    os.close(fd)
                if path.exists():
                    with contextlib.suppress(Exception):
                        path.unlink()
            self._open_fds.clear()

            if acquired_thread:
                _THREAD_LOCK.release()


# Aliases for backward compatibility and clean naming
QueueLock = BacklogLock
