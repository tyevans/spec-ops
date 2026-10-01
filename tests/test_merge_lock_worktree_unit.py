"""Unit and property tests for git worktree merge lock resolution and FileExistsError prevention."""

import os
import subprocess
import threading
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from spec_ops.worker.merge_lock import MergeLockManager, _resolve_git_dir


def test_worktree_merge_lock_absolute_gitdir(tmp_path: Path):
    """Verifies that an absolute gitdir pointer file resolves cleanly and acquires/releases lock."""
    repo_root = tmp_path / "worktree_repo"
    repo_root.mkdir()
    actual_gitdir = tmp_path / "main_repo_git" / "worktrees" / "task-0116"
    actual_gitdir.mkdir(parents=True)
    git_file = repo_root / ".git"
    git_file.write_text(f"gitdir: {actual_gitdir}\n", encoding="utf-8")

    resolved = _resolve_git_dir(repo_root)
    assert resolved == actual_gitdir

    mgr = MergeLockManager(repo_root)
    assert mgr.lock_file == actual_gitdir / "spec_ops_merge.lock"
    assert not mgr.lock_file.exists()

    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()


def test_worktree_merge_lock_relative_gitdir(tmp_path: Path):
    """Verifies that a relative gitdir pointer file in .worktrees/ resolves relative to worktree root."""
    main_repo = tmp_path / "main_repo"
    worktree_dir = main_repo / ".worktrees" / "task-0116"
    worktree_dir.mkdir(parents=True)

    actual_gitdir = main_repo / ".git" / "worktrees" / "task-0116"
    actual_gitdir.mkdir(parents=True)

    git_file = worktree_dir / ".git"
    # Relative path from worktree_dir to actual_gitdir
    git_file.write_text("gitdir: ../../.git/worktrees/task-0116\n", encoding="utf-8")

    resolved = _resolve_git_dir(worktree_dir)
    assert resolved == actual_gitdir.resolve()

    mgr = MergeLockManager(worktree_dir)
    assert mgr.lock_file == actual_gitdir.resolve() / "spec_ops_merge.lock"

    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()


def test_merge_lock_standard_git_dir(tmp_path: Path):
    """Verifies that standard .git directory is resolved directly."""
    repo_root = tmp_path / "standard_repo"
    git_dir = repo_root / ".git"
    git_dir.mkdir(parents=True)

    resolved = _resolve_git_dir(repo_root)
    assert resolved == git_dir

    mgr = MergeLockManager(repo_root)
    assert mgr.lock_file == git_dir / "spec_ops_merge.lock"
    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()


def test_merge_lock_fallback_when_no_git(tmp_path: Path):
    """Verifies fallback to .spec-ops directory when no .git exists."""
    repo_root = tmp_path / "no_git_repo"
    repo_root.mkdir()

    resolved = _resolve_git_dir(repo_root)
    expected_fallback = (repo_root / ".spec-ops").resolve()
    assert resolved == expected_fallback
    assert expected_fallback.is_dir()

    mgr = MergeLockManager(repo_root)
    assert mgr.lock_file == expected_fallback / "spec_ops_merge.lock"
    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()


def test_merge_lock_fallback_when_gitdir_target_does_not_exist(tmp_path: Path):
    """Verifies fallback to .spec-ops when .git pointer references a non-existent directory."""
    repo_root = tmp_path / "broken_worktree"
    repo_root.mkdir()
    git_file = repo_root / ".git"
    git_file.write_text("gitdir: /nonexistent/target/path/to/nowhere\n", encoding="utf-8")

    resolved = _resolve_git_dir(repo_root)
    assert resolved == (repo_root / ".spec-ops").resolve()

    mgr = MergeLockManager(repo_root)
    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()


def test_merge_lock_fallback_when_git_file_is_corrupt_or_empty(tmp_path: Path):
    """Verifies fallback to .spec-ops when .git pointer file is empty or lacks gitdir:."""
    repo_root = tmp_path / "corrupt_worktree"
    repo_root.mkdir()
    git_file = repo_root / ".git"
    git_file.write_text("not_a_valid_git_dir_pointer\n", encoding="utf-8")

    resolved = _resolve_git_dir(repo_root)
    assert resolved == (repo_root / ".spec-ops").resolve()

    # Empty file
    git_file.write_text("", encoding="utf-8")
    resolved_empty = _resolve_git_dir(repo_root)
    assert resolved_empty == (repo_root / ".spec-ops").resolve()


def test_merge_lock_when_explicit_lock_file_has_file_parent(tmp_path: Path):
    """Asserts that if a caller passes an explicit lock_file located directly under a .git file,

    MergeLockManager re-resolves the directory without throwing FileExistsError.
    """
    repo_root = tmp_path / "worktree_root"
    repo_root.mkdir()
    actual_gitdir = tmp_path / "git_meta" / "worktrees" / "wt1"
    actual_gitdir.mkdir(parents=True)

    git_file = repo_root / ".git"
    git_file.write_text(f"gitdir: {actual_gitdir}\n", encoding="utf-8")

    # Caller naively tries to place lock inside repo_root / ".git" which is a regular file
    naive_lock = repo_root / ".git" / "spec_ops_merge.lock"
    mgr = MergeLockManager(repo_root, lock_file=naive_lock)

    # Manager must redirect away from the file parent to the resolved directory
    assert mgr.lock_file.parent.is_dir()
    assert mgr.lock_file.parent == actual_gitdir

    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()


def test_merge_lock_real_git_worktree(tmp_path: Path):
    """Verifies MergeLockManager behaves cleanly in a real git worktree created via git worktree add."""
    main_repo = tmp_path / "main_git_repo"
    main_repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@user.com"], cwd=main_repo, check=True, capture_output=True)

    (main_repo / "initial.txt").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "initial.txt"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=main_repo, check=True, capture_output=True)

    # Create worktree
    wt_dir = main_repo / ".worktrees" / "task-0116"
    subprocess.run(
        ["git", "worktree", "add", str(wt_dir), "-b", "feat/task-0116"],
        cwd=main_repo,
        check=True,
        capture_output=True,
    )

    # Verify that .git in wt_dir is indeed a file
    assert (wt_dir / ".git").is_file()

    mgr = MergeLockManager(wt_dir)
    assert mgr.lock_file.parent.is_dir()

    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()


def test_merge_lock_worktree_thread_contention(tmp_path: Path):
    """Verifies mutual exclusion when two threads acquire the lock inside a worktree."""
    repo_root = tmp_path / "contention_worktree"
    repo_root.mkdir()
    actual_gitdir = tmp_path / "main_repo_git" / "worktrees" / "wt_contend"
    actual_gitdir.mkdir(parents=True)
    (repo_root / ".git").write_text(f"gitdir: {actual_gitdir}\n", encoding="utf-8")

    mgr = MergeLockManager(repo_root)

    t1_acquired = threading.Event()
    t1_release = threading.Event()
    t2_acquired = threading.Event()

    def thread_1():
        with mgr.acquire(timeout=5.0):
            t1_acquired.set()
            t1_release.wait(timeout=2.0)

    def thread_2():
        t1_acquired.wait(timeout=2.0)
        with mgr.acquire(timeout=5.0):
            t2_acquired.set()

    t1 = threading.Thread(target=thread_1)
    t2 = threading.Thread(target=thread_2)

    t1.start()
    t2.start()

    t1_acquired.wait(timeout=2.0)
    assert not t2_acquired.is_set()

    t1_release.set()
    t1.join()
    t2.join()

    assert t2_acquired.is_set()
    assert not mgr.lock_file.exists()


@settings(deadline=None, max_examples=25)
@given(
    subfolder_name=st.from_regex(r"^[a-zA-Z0-9_\-]{1,20}$", fullmatch=True),
    prefix_spaces=st.integers(min_value=0, max_value=4),
    newline_count=st.integers(min_value=1, max_value=3),
)
def test_hypothesis_merge_lock_pointer_invariants(
    tmp_path_factory, subfolder_name, prefix_spaces, newline_count
):
    """Property Invariant: For arbitrary pointer formatting, MergeLockManager never raises

    FileExistsError, always resolves to an existing directory, and acquires/releases cleanly.
    """
    base_dir = tmp_path_factory.mktemp("hypo_wt")
    repo_root = base_dir / "worktree"
    repo_root.mkdir()

    target_gitdir = base_dir / "meta_git" / subfolder_name
    target_gitdir.mkdir(parents=True)

    spaces = " " * prefix_spaces
    newlines = "\n" * newline_count
    pointer_text = f"gitdir:{spaces}{target_gitdir}{newlines}"

    (repo_root / ".git").write_text(pointer_text, encoding="utf-8")

    mgr = MergeLockManager(repo_root)
    assert mgr.lock_file.parent.is_dir()
    assert not mgr.lock_file.exists()

    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()
