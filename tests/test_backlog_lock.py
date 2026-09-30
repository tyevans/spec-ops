"""Unit and edge-case tests for cross-process file locking and transactional operations."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from spec_ops.backlog.lock import (
    BacklogLock,
    TwoPhaseFileTransaction,
    atomic_write,
    find_repo_root,
    is_pid_alive,
    read_lock_pid,
    recover_stale_lock,
    recover_transactions,
)


def test_is_pid_alive():
    assert is_pid_alive(os.getpid()) is True
    assert is_pid_alive(0) is False
    assert is_pid_alive(-1) is False
    assert is_pid_alive(-999) is False
    # Large unused PID should not be alive
    assert is_pid_alive(9999999) is False

    with patch("os.kill", side_effect=PermissionError):
        assert is_pid_alive(12345) is True


def test_read_lock_pid(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.lock"
    assert read_lock_pid(non_existent) is None

    empty = tmp_path / "empty.lock"
    empty.write_text("   \n", encoding="utf-8")
    assert read_lock_pid(empty) is None

    plain = tmp_path / "plain.lock"
    plain.write_text("12345\n", encoding="utf-8")
    assert read_lock_pid(plain) == 12345

    json_lock = tmp_path / "json.lock"
    json_lock.write_text('{"pid": 54321, "heartbeat": 1000}', encoding="utf-8")
    assert read_lock_pid(json_lock) == 54321

    regex_lock = tmp_path / "regex.lock"
    regex_lock.write_text("worker locked with PID 67890", encoding="utf-8")
    assert read_lock_pid(regex_lock) == 67890

    invalid = tmp_path / "invalid.lock"
    invalid.write_text("no-digits-here", encoding="utf-8")
    assert read_lock_pid(invalid) is None


def test_recover_stale_lock(tmp_path: Path, capsys):
    non_existent = tmp_path / "no.lock"
    assert recover_stale_lock(non_existent) is False

    # Alive PID should not be recovered
    alive_lock = tmp_path / "alive.lock"
    alive_lock.write_text(f"{os.getpid()}\n", encoding="utf-8")
    assert recover_stale_lock(alive_lock, max_age=3600) is False
    assert alive_lock.exists()

    # Dead PID should be recovered
    dead_lock = tmp_path / "dead.lock"
    dead_lock.write_text("9999999\n", encoding="utf-8")
    assert recover_stale_lock(dead_lock, max_age=3600) is True
    assert not dead_lock.exists()
    _, err = capsys.readouterr()
    assert "Recovered stale backlog lock from terminated process 9999999" in err

    # Expired lock by mtime with alive PID
    expired_lock = tmp_path / "expired.lock"
    expired_lock.write_text(f"{os.getpid()}\n", encoding="utf-8")
    past = 0.0
    os.utime(expired_lock, (past, past))
    assert recover_stale_lock(expired_lock, max_age=0.5) is True
    assert not expired_lock.exists()
    _, err = capsys.readouterr()
    assert "Recovered stale backlog lock expired after 0.5s" in err


def test_find_repo_root(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".git").mkdir()
    sub = root / "docs" / "project" / "backlog"
    sub.mkdir(parents=True)
    target = sub / "test.md"
    target.touch()

    assert find_repo_root(target) == root
    assert find_repo_root(sub) == root

    standalone = tmp_path / "standalone.md"
    standalone.touch()
    assert find_repo_root(standalone) == tmp_path


def test_two_phase_transaction_lifecycle(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    target = repo / "PRIORITY.md"
    target.write_text("# Initial", encoding="utf-8")

    tx = TwoPhaseFileTransaction(target, repo_root=repo)
    staged = tx.prepare("# Updated")
    assert staged.exists()
    assert target.read_text(encoding="utf-8") == "# Initial"
    assert tx.backup_file.exists()

    # Commit
    tx.commit()
    assert target.read_text(encoding="utf-8") == "# Updated"
    assert not staged.exists()
    assert not tx.backup_file.exists()

    # Commit without prepare raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        tx.commit()

    # Rollback
    target.write_text("# Before Rollback", encoding="utf-8")
    tx2 = TwoPhaseFileTransaction(target, repo_root=repo)
    tx2.prepare("# New Draft")
    tx2.rollback()
    assert target.read_text(encoding="utf-8") == "# Before Rollback"
    assert not tx2.staging_file.exists()
    assert not tx2.backup_file.exists()


def test_atomic_write(tmp_path: Path):
    target = tmp_path / "test_atomic.md"
    res = atomic_write(target, "Hello Atomic World")
    assert res == target
    assert target.read_text(encoding="utf-8") == "Hello Atomic World"


def test_recover_transactions(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tmp_dir = repo / ".spec-ops" / "tmp"
    tmp_dir.mkdir(parents=True)
    bak_dir = repo / ".spec-ops" / "backups"
    bak_dir.mkdir(parents=True)

    orphan_tmp = tmp_dir / "orphaned.tmp"
    orphan_tmp.write_text("garbage", encoding="utf-8")

    target = repo / "PRIORITY.md"
    target.write_text("", encoding="utf-8")  # 0 bytes (corrupt)
    bak = bak_dir / "PRIORITY.md.bak"
    bak.write_text("# Saved Content", encoding="utf-8")

    recover_transactions(repo)
    assert not orphan_tmp.exists()
    assert target.read_text(encoding="utf-8") == "# Saved Content"
    assert not bak.exists()


def test_backlog_lock_acquire_and_release(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    lock = BacklogLock(repo)

    with lock.acquire(timeout=5.0):
        # Assert lock files are created and hold current PID
        primary = repo / ".spec-ops" / "locks" / "backlog.lock"
        secondary = repo / ".specops" / "locks" / "queue.lock"
        assert primary.exists()
        assert secondary.exists()
        assert read_lock_pid(primary) == os.getpid()
        assert read_lock_pid(secondary) == os.getpid()

    # After exit, lock files should be cleaned up
    assert not primary.exists()
    assert not secondary.exists()


def test_backlog_lock_timeout_error(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    lock_file = repo / "exclusive.lock"

    lock1 = BacklogLock(repo, lock_file=lock_file)
    lock2 = BacklogLock(repo, lock_file=lock_file)

    with lock1.acquire(timeout=5.0):
        with pytest.raises(TimeoutError) as exc_info:
            with lock2.acquire(timeout=0.1):
                pass
        assert "Timed out waiting for backlog lock" in str(exc_info.value)
