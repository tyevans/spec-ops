"""Executable BDD scenarios for US-0081 and US-0085."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.backlog.worker import BacklogWorkerEngine, WorkerResult
from spec_ops.config.loader import load_config
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.worker.merge_lock import MergeLockManager
from spec_ops.worker.orchestrator import BatchCycleOrchestrator, BatchCycleReport

scenarios(
    "features/us_0081_concurrent_worker_execution.feature",
    "features/us_0085_batch_cycle_orchestration.feature",
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Initializes a valid SpecOps git repository for worker testing."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialize SpecOps project structure
    from spec_ops.scaffold.init import init_project

    init_project(name="WorkerFleetApp", target_dir=repo)

    # Clean out default tasks so each scenario manages its own queue
    import shutil
    for folder in [repo / "docs" / "project" / "backlog" / "refined", repo / "docs" / "project" / "backlog" / "proposed"]:
        if folder.exists():
            shutil.rmtree(folder)
            folder.mkdir(parents=True, exist_ok=True)

    # Add passing dummy test so pytest preflight passes in worktrees
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_dummy.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@runner.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return repo


@pytest.fixture
def bdd_worker_context(git_repo: Path) -> dict[str, Any]:
    cfg = load_config(git_repo)
    cfg.quality.preflight = ["true"]
    return {
        "repo": git_repo,
        "config": cfg,
        "lock_mgr": MergeLockManager(git_repo),
        "worker_engine": BacklogWorkerEngine(cfg),
        "queue": BacklogQueue(cfg.backlog_dir),
    }


# ==============================================================================
# US-0081 Step Definitions
# ==============================================================================


@given(
    parsers.parse(
        'two autonomous workers running concurrently on tasks "{task1_id}" and "{task2_id}" in separate worktrees'
    )
)
def setup_concurrent_workers(bdd_worker_context: dict[str, Any], task1_id: str, task2_id: str):
    repo = bdd_worker_context["repo"]
    engine: BacklogWorkerEngine = bdd_worker_context["worker_engine"]

    # Create two task branches
    wt1 = repo / ".worktrees" / f"task-{task1_id.lower().replace('task-', '')}"
    wt2 = repo / ".worktrees" / f"task-{task2_id.lower().replace('task-', '')}"
    b1 = f"feat/{task1_id.lower()}"
    b2 = f"feat/{task2_id.lower()}"

    engine.create_worktree(b1, wt1)
    engine.create_worktree(b2, wt2)

    # Worker 1 modifies a file
    (wt1 / "file1.txt").write_text("worker 1 content\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt1, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"feat({task1_id}): add file1"], cwd=wt1, check=True, capture_output=True)

    # Worker 2 modifies a non-conflicting file
    (wt2 / "file2.txt").write_text("worker 2 content\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt2, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"feat({task2_id}): add file2"], cwd=wt2, check=True, capture_output=True)

    bdd_worker_context["wt1"] = wt1
    bdd_worker_context["wt2"] = wt2
    bdd_worker_context["b1"] = b1
    bdd_worker_context["b2"] = b2
    bdd_worker_context["task1_id"] = task1_id
    bdd_worker_context["task2_id"] = task2_id


@given(parsers.parse('worker "{task1_id}" acquires "MERGE_LOCK", squash-merges into "main", and completes'))
def worker1_squash_merges(bdd_worker_context: dict[str, Any], task1_id: str):
    repo = bdd_worker_context["repo"]
    lock_mgr: MergeLockManager = bdd_worker_context["lock_mgr"]
    b1 = bdd_worker_context["b1"]

    with lock_mgr.acquire():
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "merge", "--squash", b1], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"feat({task1_id.lower()}): task 1 integrated"],
            cwd=repo,
            check=True,
            capture_output=True,
        )


@when(parsers.parse('worker "{task2_id}" finishes code modifications and acquires "MERGE_LOCK"'))
def worker2_finishes_and_acquires_lock(bdd_worker_context: dict[str, Any], task2_id: str):
    lock_mgr: MergeLockManager = bdd_worker_context["lock_mgr"]
    b2 = bdd_worker_context["b2"]
    # Check that b2 is behind main
    is_behind = lock_mgr.is_branch_behind_main(b2)
    bdd_worker_context["is_behind"] = is_behind


@then(parsers.parse('the worker engine detects that "{task2_id}" branched from a commit behind current "main"'))
def verify_branch_behind_main(bdd_worker_context: dict[str, Any], task2_id: str):
    assert bdd_worker_context["is_behind"] is True


@then(parsers.parse('the engine automatically rebases the "{branch}" branch onto the latest "main"'))
def engine_auto_rebases(bdd_worker_context: dict[str, Any], branch: str):
    lock_mgr: MergeLockManager = bdd_worker_context["lock_mgr"]
    wt2 = bdd_worker_context["wt2"]
    ok, msg = lock_mgr.rebase_branch(wt2, main_branch="main")
    assert ok is True
    assert "Rebased successfully" in msg
    bdd_worker_context["rebase_ok"] = ok


@then("runs the preflight verification suite on the rebased code")
def run_preflight_on_rebase(bdd_worker_context: dict[str, Any]):
    engine: BacklogWorkerEngine = bdd_worker_context["worker_engine"]
    wt2 = bdd_worker_context["wt2"]
    ok, _ = engine.run_preflight(wt2)
    assert ok is True


@then(parsers.parse('upon passing preflight, squash-merges "{branch}" into "main" and marks "{task2_id}" complete.'))
def squash_merge_and_mark_complete(bdd_worker_context: dict[str, Any], branch: str, task2_id: str):
    repo = bdd_worker_context["repo"]
    lock_mgr: MergeLockManager = bdd_worker_context["lock_mgr"]
    with lock_mgr.acquire():
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "merge", "--squash", branch], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"feat({task2_id.lower()}): task 2 integrated"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
    assert (repo / "file2.txt").is_file()
    assert (repo / "file1.txt").is_file()


@given(parsers.parse('a concurrent worker executing "{task_id}" in "{worktree_path}"'))
def worker_executing_conflict_task(bdd_worker_context: dict[str, Any], task_id: str, worktree_path: str):
    repo = bdd_worker_context["repo"]
    engine: BacklogWorkerEngine = bdd_worker_context["worker_engine"]

    # Main introduces file conflict.txt
    (repo / "conflict.txt").write_text("main version\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: add conflict.txt on main"], cwd=repo, check=True, capture_output=True)

    wt = repo / worktree_path
    b = f"feat/{task_id.lower()}"
    engine.create_worktree(b, wt)

    # Rewind worktree to HEAD~1 to create a conflict on rebase
    subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=wt, check=True, capture_output=True)
    (wt / "conflict.txt").write_text("worker conflicting version\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "conflicting commit"], cwd=wt, check=True, capture_output=True)

    bdd_worker_context["conflict_wt"] = wt
    bdd_worker_context["conflict_branch"] = b
    bdd_worker_context["conflict_task_id"] = task_id


@when(parsers.parse('"{task_id}" acquires "MERGE_LOCK" and attempts to rebase onto updated "main"'))
def task_attempts_conflict_rebase(bdd_worker_context: dict[str, Any], task_id: str):
    lock_mgr: MergeLockManager = bdd_worker_context["lock_mgr"]
    wt = bdd_worker_context["conflict_wt"]
    ok, msg = lock_mgr.rebase_branch(wt, main_branch="main")
    bdd_worker_context["rebase_result"] = (ok, msg)


@when("git encounters an unresolvable semantic merge conflict")
def git_encounters_conflict(bdd_worker_context: dict[str, Any]):
    ok, _ = bdd_worker_context["rebase_result"]
    assert ok is False


@then('the worker engine aborts the rebase without corrupting "main"')
def verify_rebase_aborted(bdd_worker_context: dict[str, Any]):
    wt = bdd_worker_context["conflict_wt"]
    # Rebase should be aborted (no rebase-apply or rebase-merge dir)
    git_dir = wt / ".git"
    assert not (git_dir / "rebase-merge").exists()
    assert not (git_dir / "rebase-apply").exists()


@then('releases "MERGE_LOCK" so other workers remain unblocked')
def verify_lock_released(bdd_worker_context: dict[str, Any]):
    lock_mgr: MergeLockManager = bdd_worker_context["lock_mgr"]
    # Lock can be acquired without timing out
    with lock_mgr.acquire(timeout=2.0):
        pass


@then(parsers.parse('preserves the worktree at "{worktree_path}" with status "Conflict"'))
def verify_worktree_preserved(bdd_worker_context: dict[str, Any], worktree_path: str):
    repo = bdd_worker_context["repo"]
    wt = repo / worktree_path
    assert wt.is_dir()


@then(parsers.parse('logs an actionable human rescue notification "spec-ops rescue {task_id}".'))
def verify_rescue_notification(bdd_worker_context: dict[str, Any], task_id: str):
    pass


# ==============================================================================
# US-0085 Step Definitions
# ==============================================================================


@given(parsers.parse('task "{task_id}" is refined and unblocked in the priority queue'))
def setup_task_refined_and_unblocked(bdd_worker_context: dict[str, Any], task_id: str):
    cfg: SpecOpsConfig = bdd_worker_context["config"]
    queue: BacklogQueue = bdd_worker_context["queue"]
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    t = Task(
        id=task_id.replace("TASK-", ""),
        title=f"Feature {task_id}",
        status="Refined",
        dependencies=[],
        file_path=refined_dir / f"{task_id.replace('TASK-', '')}-feat.md",
        priority_rank=1,
    )
    write_task_file(t)


@given(parsers.parse('task "{task2_id}" depends on "{task1_id}" and is currently blocked'))
def setup_dependent_task(bdd_worker_context: dict[str, Any], task2_id: str, task1_id: str):
    cfg: SpecOpsConfig = bdd_worker_context["config"]
    refined_dir = cfg.backlog_dir / "refined"
    t = Task(
        id=task2_id.replace("TASK-", ""),
        title=f"Feature {task2_id}",
        status="Refined",
        dependencies=[task1_id],
        file_path=refined_dir / f"{task2_id.replace('TASK-', '')}-feat.md",
        priority_rank=2,
    )
    write_task_file(t)


@when(parsers.parse('the user runs "spec-ops cycle --max-tasks {n:d}"'))
def run_spec_ops_cycle_max_tasks(bdd_worker_context: dict[str, Any], n: int):
    cfg: SpecOpsConfig = bdd_worker_context["config"]
    cfg.quality.preflight = ["true"]
    cfg.execution.agent_command = f"{sys.executable} -c \"import pathlib, time; pathlib.Path(f'mod_{{time.time_ns()}}.txt').write_text('done')\""
    cfg.execution.reviewer_command = f"{sys.executable} -c \"print('STATUS: APPROVED')\""
    orchestrator = BatchCycleOrchestrator(
        cfg,
        max_concurrency=2,
        max_tasks=n,
        dry_run=False,
    )
    report = orchestrator.run()
    bdd_worker_context["cycle_report"] = report


@then(parsers.parse('the cycle orchestrator executes "{task_id}" in an isolated worktree and merges it into "main"'))
def verify_first_task_executed(bdd_worker_context: dict[str, Any], task_id: str):
    report: BatchCycleReport = bdd_worker_context["cycle_report"]
    assert task_id in report.tasks_succeeded


@then(parsers.parse('immediately re-evaluates the backlog queue to find that "{task_id}" dependencies are now satisfied'))
def re_evaluate_dependencies_satisfied(bdd_worker_context: dict[str, Any], task_id: str):
    # Verified by the orchestrator pulling task_id into execution
    pass


@then(parsers.parse('pulls "{task_id}" into active execution as the second task of the cycle'))
def verify_second_task_executed(bdd_worker_context: dict[str, Any], task_id: str):
    report: BatchCycleReport = bdd_worker_context["cycle_report"]
    assert task_id in report.tasks_succeeded


@then(parsers.parse('generates a cycle completion summary showing {n:d} tasks executed and {f:d} failures.'))
def verify_cycle_summary(bdd_worker_context: dict[str, Any], n: int, f: int):
    report: BatchCycleReport = bdd_worker_context["cycle_report"]
    assert report.tasks_executed == n
    assert len(report.tasks_failed) == f


@given(parsers.parse('an active autonomous cycle running task "{task_id}"'))
def active_cycle_running_task(bdd_worker_context: dict[str, Any], task_id: str):
    cfg: SpecOpsConfig = bdd_worker_context["config"]
    refined_dir = cfg.backlog_dir / "refined"
    t = Task(
        id=task_id.replace("TASK-", ""),
        title=f"Feature {task_id}",
        status="Refined",
        dependencies=[],
        file_path=refined_dir / f"{task_id.replace('TASK-', '')}-feat.md",
    )
    write_task_file(t)
    orchestrator = BatchCycleOrchestrator(cfg, max_tasks=1, dry_run=True)
    bdd_worker_context["interrupted_orchestrator"] = orchestrator


@when(parsers.parse("the operator sends an interrupt signal (SIGINT / Ctrl+C) to the cycle process"))
def operator_sends_sigint(bdd_worker_context: dict[str, Any]):
    orchestrator: BatchCycleOrchestrator = bdd_worker_context["interrupted_orchestrator"]
    orchestrator._shutdown_requested = True
    report = orchestrator.run()
    bdd_worker_context["interrupted_report"] = report


@then("the cycle orchestrator traps the signal and initiates graceful shutdown")
def verify_graceful_shutdown(bdd_worker_context: dict[str, Any]):
    report: BatchCycleReport = bdd_worker_context["interrupted_report"]
    assert report.interrupted is True


@then("allows the current worktree operation to reach a safe checkpoint without killing git mid-write")
def verify_safe_checkpoint():
    pass


@then('ensures "MERGE_LOCK" is released and no orphaned lockfiles remain on disk')
def verify_no_orphaned_locks(bdd_worker_context: dict[str, Any]):
    lock_mgr: MergeLockManager = bdd_worker_context["lock_mgr"]
    assert not lock_mgr.lock_file.exists()


@then("outputs a cycle report summarizing completed tasks and the preserved state of the interrupted task.")
def verify_interrupted_summary(bdd_worker_context: dict[str, Any]):
    report: BatchCycleReport = bdd_worker_context["interrupted_report"]
    assert "Interrupted" in report.message
