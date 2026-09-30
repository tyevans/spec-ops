"""Unit and integration tests for MergeLockManager and BatchCycleOrchestrator."""

import subprocess
import threading
import time
from pathlib import Path

import pytest

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.merge_lock import MergeLockManager
from spec_ops.worker.orchestrator import BatchCycleOrchestrator


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="OrchTestApp", target_dir=repo)

    # Clean out default tasks so tests control queue state
    import shutil
    for folder in [repo / "docs" / "project" / "backlog" / "refined", repo / "docs" / "project" / "backlog" / "proposed"]:
        if folder.exists():
            shutil.rmtree(folder)
            folder.mkdir(parents=True, exist_ok=True)

    # Provide a passing test
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_dummy.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@runner.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_merge_lock_acquire_and_release(initialized_repo: Path):
    mgr = MergeLockManager(initialized_repo)
    lock_file = mgr.lock_file

    assert not lock_file.exists()
    with mgr.acquire(timeout=5.0):
        assert lock_file.exists()
    assert not lock_file.exists()


def test_merge_lock_concurrency_contention(initialized_repo: Path):
    mgr = MergeLockManager(initialized_repo)
    acquired_first = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    second_acquired = threading.Event()

    def worker_one():
        with mgr.acquire(timeout=5.0):
            acquired_first.set()
            release_first.wait(timeout=2.0)

    def worker_two():
        acquired_first.wait(timeout=2.0)
        second_started.set()
        with mgr.acquire(timeout=5.0):
            second_acquired.set()

    t1 = threading.Thread(target=worker_one)
    t2 = threading.Thread(target=worker_two)

    t1.start()
    t2.start()

    acquired_first.wait(timeout=2.0)
    second_started.wait(timeout=2.0)
    # At this point, worker 2 should NOT have acquired the lock yet
    assert not second_acquired.is_set()

    # Release worker 1
    release_first.set()
    t1.join()
    t2.join()

    # Now worker 2 has acquired and finished
    assert second_acquired.is_set()
    assert not mgr.lock_file.exists()


def test_is_branch_behind_main(initialized_repo: Path):
    mgr = MergeLockManager(initialized_repo)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feat/test-behind"], cwd=initialized_repo, check=True, capture_output=True)
    (initialized_repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.txt"], cwd=initialized_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: test"], cwd=initialized_repo, check=True, capture_output=True)

    # Switch back to main and commit
    subprocess.run(["git", "checkout", "main"], cwd=initialized_repo, check=True, capture_output=True)
    assert not mgr.is_branch_behind_main("feat/test-behind", "main")

    (initialized_repo / "main_advance.txt").write_text("advance\n", encoding="utf-8")
    subprocess.run(["git", "add", "main_advance.txt"], cwd=initialized_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "advance main"], cwd=initialized_repo, check=True, capture_output=True)

    # Now feat/test-behind is behind main!
    assert mgr.is_branch_behind_main("feat/test-behind", "main")


def test_batch_cycle_orchestrator_empty(initialized_repo: Path):
    cfg = load_config(initialized_repo)
    orchestrator = BatchCycleOrchestrator(cfg, max_concurrency=3)
    report = orchestrator.run()

    assert report.tasks_executed == 0
    assert report.tasks_succeeded == []
    assert report.tasks_failed == []
    assert report.interrupted is False


def test_batch_cycle_orchestrator_dynamic_unblock_and_drain(initialized_repo: Path):
    cfg = load_config(initialized_repo)
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    # Task 1: No dependencies
    t1 = Task(
        id="0101",
        title="First task",
        status="Refined",
        dependencies=[],
        file_path=refined_dir / "0101-first.md",
        priority_rank=1,
    )
    write_task_file(t1)

    # Task 2: Depends on Task 1
    t2 = Task(
        id="0102",
        title="Second task",
        status="Refined",
        dependencies=["TASK-0101"],
        file_path=refined_dir / "0102-second.md",
        priority_rank=2,
    )
    write_task_file(t2)

    import sys
    cfg.quality.preflight = ["true"]
    cfg.execution.agent_command = f"{sys.executable} -c \"import pathlib, time; pathlib.Path(f'mod_{{time.time_ns()}}.txt').write_text('done')\""
    cfg.execution.reviewer_command = f"{sys.executable} -c \"print('STATUS: APPROVED')\""
    orchestrator = BatchCycleOrchestrator(
        cfg,
        max_concurrency=2,
        drain=True,
        dry_run=False,
    )
    report = orchestrator.run()

    assert report.tasks_executed == 2
    assert "TASK-0101" in report.tasks_succeeded
    assert "TASK-0102" in report.tasks_succeeded
    assert len(report.tasks_failed) == 0


def test_merge_lock_in_worktree_with_gitdir_file(tmp_path: Path):
    repo_root = tmp_path / "worktree_repo"
    repo_root.mkdir()
    actual_gitdir = tmp_path / "main_repo_git" / "worktrees" / "wt1"
    actual_gitdir.mkdir(parents=True)
    git_file = repo_root / ".git"
    git_file.write_text(f"gitdir: {actual_gitdir}\n", encoding="utf-8")

    mgr = MergeLockManager(repo_root)
    assert mgr.lock_file.parent == actual_gitdir

    assert not mgr.lock_file.exists()
    with mgr.acquire(timeout=5.0):
        assert mgr.lock_file.exists()
    assert not mgr.lock_file.exists()
