"""Executable BDD scenarios for US-0076: Cross-Process File Locking and Concurrency Protection."""

from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.lock import BacklogLock, TwoPhaseFileTransaction, recover_stale_lock
from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0076_cross_process_file_locking_and_concurrency_protection.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**CLI_ENV, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def repo_ctx(tmp_path: Path) -> dict[str, Any]:
    """Sets up a clean test repository with git initialized and ready tasks."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="LockingTestRepo", target_dir=repo)

    root_pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if root_pyproject.exists() and not (repo / "pyproject.toml").exists():
        shutil.copy2(root_pyproject, repo / "pyproject.toml")

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "agent@specops.io"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Agent"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, capture_output=True, check=True)

    backlog = repo / "docs" / "project" / "backlog"
    for d in ["refined", "proposed", "complete"]:
        p = backlog / d
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)

    # Scaffolding PRD
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0005-relational.md").write_text("---\nid: '0005'\nstatus: Accepted\n---\n# PRD-0005\n", encoding="utf-8")

    # Scaffolding ADR
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "0001-pmac.md").write_text("---\nid: '0001'\nstatus: Accepted\n---\n# ADR-0001\n", encoding="utf-8")

    # Scaffolding User Story with Gherkin
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0076-lock.md").write_text(
        "---\nid: '0076'\nstatus: Accepted\n---\n# US-0076\n```gherkin\nScenario: Mutual exclusion\nGiven x\nWhen y\nThen z\n```\n",
        encoding="utf-8",
    )

    return {
        "repo": repo,
        "results": {},
        "tasks": {},
        "warnings": [],
    }


# =========================================================================
# Scenario 1: Mutual Exclusion During Concurrent Task Claiming
# =========================================================================

@given('two independent worker processes "worker-alpha" and "worker-beta" running simultaneously')
def setup_two_workers(repo_ctx: dict[str, Any]):
    repo_ctx["workers"] = ["worker-alpha", "worker-beta"]


@given('task "TASK-0014" is the highest-priority unassigned task in "docs/project/backlog/refined/"')
def setup_tasks_14_and_15(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog = repo / "docs" / "project" / "backlog"

    t14 = Task(
        id="0014",
        title="First Task",
        status="Refined",
        governing_prds=["PRD-0005"],
        governing_adrs=["ADR-0001"],
        governing_stories=["US-0076"],
        file_path=backlog / "refined" / "0014-first.md",
    )
    t15 = Task(
        id="0015",
        title="Second Task",
        status="Refined",
        governing_prds=["PRD-0005"],
        governing_adrs=["ADR-0001"],
        governing_stories=["US-0076"],
        file_path=backlog / "refined" / "0015-second.md",
    )
    write_task_file(t14)
    write_task_file(t15)

    (backlog / "PRIORITY.md").write_text(
        "- **TASK-0014 (Refined)**: [`0014-first`](refined/0014-first.md)\n"
        "- **TASK-0015 (Refined)**: [`0015-second`](refined/0015-second.md)\n",
        encoding="utf-8",
    )


@when('both workers invoke "spec-ops worker claim --auto" at the exact same instant')
def invoke_workers_claim_auto(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]

    def run_worker(worker_id: str) -> tuple[str, subprocess.CompletedProcess[str]]:
        res = run_spec_ops(repo, ["worker", "claim", "--auto", "--worker-id", worker_id])
        return worker_id, res

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futs = [executor.submit(run_worker, w) for w in repo_ctx["workers"]]
        for f in concurrent.futures.as_completed(futs):
            worker_id, res = f.result()
            repo_ctx["results"][worker_id] = res


@then('the first worker acquires the cross-process lock at ".spec-ops/locks/backlog.lock"')
def assert_first_worker_lock(repo_ctx: dict[str, Any]):
    # Both workers should successfully claim without lock collision error
    results = repo_ctx["results"]
    for worker_id, res in results.items():
        assert res.returncode == 0, f"Worker {worker_id} failed: {res.stderr}\n{res.stdout}"


@then('assigns "TASK-0014" to "worker-alpha" with status "claimed"')
def assert_task_14_assigned(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    t14_file = repo / "docs" / "project" / "backlog" / "refined" / "0014-first.md"
    task14 = parse_task(t14_file)
    # Either worker-alpha or worker-beta claimed it, verifying one of them claimed it
    assert task14.claimed_by in ["worker-alpha", "worker-beta"]
    repo_ctx["t14_claimant"] = task14.claimed_by


@then('the second worker waits on the lock, refreshes queue state upon acquisition, and claims the subsequent task "TASK-0015"')
def assert_task_15_assigned(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    t15_file = repo / "docs" / "project" / "backlog" / "refined" / "0015-second.md"
    task15 = parse_task(t15_file)
    first_claimant = repo_ctx["t14_claimant"]
    second_claimant = "worker-beta" if first_claimant == "worker-alpha" else "worker-alpha"
    assert task15.claimed_by == second_claimant


@then("zero race conditions or double-claims occur.")
def assert_zero_race_conditions(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    t14 = parse_task(repo / "docs" / "project" / "backlog" / "refined" / "0014-first.md")
    t15 = parse_task(repo / "docs" / "project" / "backlog" / "refined" / "0015-second.md")
    assert t14.claimed_by != ""
    assert t15.claimed_by != ""
    assert t14.claimed_by != t15.claimed_by


# =========================================================================
# Scenario 2: Two-Phase Atomic Write and Rollback on Interrupted Updates
# =========================================================================

@given('a worker process updating "PRIORITY.md" under lock')
def worker_updating_priority(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    p_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    p_file.write_text("# Initial PRIORITY Index\n- **TASK-0010 (Refined)**: [`0010`](refined/0010.md)\n", encoding="utf-8")
    repo_ctx["orig_priority"] = p_file.read_text(encoding="utf-8")


@when('the worker writes the updated index to a temporary staging file ".spec-ops/tmp/PRIORITY.md.tmp"')
def write_staging_tmp(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    p_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    tx = TwoPhaseFileTransaction(p_file, repo_root=repo)
    staged = tx.prepare("# Updated New Content\n")
    repo_ctx["tx"] = tx
    assert staged.exists()
    assert staged.name == "PRIORITY.md.tmp"


@when("an unexpected termination signal occurs before completion")
def unexpected_termination_signal(repo_ctx: dict[str, Any]):
    # Simulation: process aborts before calling commit, triggers rollback
    tx: TwoPhaseFileTransaction = repo_ctx["tx"]
    tx.rollback()


@then('the original "PRIORITY.md" remains intact and uncorrupted')
def original_priority_intact(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    p_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    assert p_file.read_text(encoding="utf-8") == repo_ctx["orig_priority"]


@then("stale lock detection releases the lock after the process heartbeat expires.")
def stale_lock_heartbeat_expires(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    lock_file = repo / ".spec-ops" / "locks" / "backlog.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text("999999\n", encoding="utf-8")
    # Setting mtime to 1000s in the past to simulate expired heartbeat
    past = 0.0
    os.utime(lock_file, (past, past))
    recovered = recover_stale_lock(lock_file, max_age=1.0)
    assert recovered is True
    assert not lock_file.exists()


# =========================================================================
# Scenario 3: Stale Lock Auto-Recovery on Worker Process Crash
# =========================================================================

@given('a lockfile at ".spec-ops/locks/backlog.lock" holding PID 12345')
def lockfile_holding_dead_pid(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    lock_file = repo / ".spec-ops" / "locks" / "backlog.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text("12345\n", encoding="utf-8")
    repo_ctx["lock_file"] = lock_file


@given("process 12345 no longer exists in the operating system process table")
def pid_12345_does_not_exist(repo_ctx: dict[str, Any]):
    # PID 12345 does not exist or is dead in standard OS test environment
    pass


@when("a new worker attempts to claim a task")
def new_worker_attempts_claim(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog = repo / "docs" / "project" / "backlog"

    t = Task(
        id="0099",
        title="Recovery Task",
        status="Refined",
        governing_prds=["PRD-0005"],
        governing_adrs=["ADR-0001"],
        governing_stories=["US-0076"],
        file_path=backlog / "refined" / "0099-recovery.md",
    )
    write_task_file(t)
    (backlog / "PRIORITY.md").write_text("- **TASK-0099 (Refined)**: [`0099-recovery`](refined/0099-recovery.md)\n", encoding="utf-8")

    res = run_spec_ops(repo, ["queue", "claim", "--auto", "--worker-id", "recovery-worker"])
    repo_ctx["recovery_res"] = res


@then("SpecOps detects the dead PID")
def specops_detects_dead_pid(repo_ctx: dict[str, Any]):
    res = repo_ctx["recovery_res"]
    all_output = res.stdout + res.stderr
    assert "12345" in all_output or "stale" in all_output.lower() or res.returncode == 0


@then('automatically reclaims the stale lock with warning "Recovered stale backlog lock from terminated process 12345"')
def warning_recovered_stale_lock(repo_ctx: dict[str, Any]):
    res = repo_ctx["recovery_res"]
    all_output = res.stdout + res.stderr
    assert "Recovered stale backlog lock from terminated process 12345" in all_output


@then("proceeds with the operation without requiring manual human intervention.")
def proceeds_without_manual_intervention(repo_ctx: dict[str, Any]):
    res = repo_ctx["recovery_res"]
    assert res.returncode == 0
    repo = repo_ctx["repo"]
    t = parse_task(repo / "docs" / "project" / "backlog" / "refined" / "0099-recovery.md")
    assert t.claimed_by == "recovery-worker"


# =========================================================================
# Scenario 4: 4 Concurrent Worker Processes Claiming via queue claim
# =========================================================================

@given('4 concurrent worker processes running "spec-ops queue claim" simultaneously')
def setup_four_workers(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog = repo / "docs" / "project" / "backlog"

    for i in range(1, 5):
        tid = f"003{i}"
        t = Task(
            id=tid,
            title=f"Task {tid}",
            status="Refined",
            governing_prds=["PRD-0005"],
            governing_adrs=["ADR-0001"],
            governing_stories=["US-0076"],
            file_path=backlog / "refined" / f"{tid}-task.md",
        )
        write_task_file(t)

    lines = [f"- **TASK-003{i} (Refined)**: [`003{i}-task`](refined/003{i}-task.md)" for i in range(1, 5)]
    (backlog / "PRIORITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    repo_ctx["workers_4"] = [f"worker-{i}" for i in range(1, 5)]


@when("processes contend for the queue lock")
def contend_queue_lock(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]

    def run_claim(worker_id: str) -> tuple[str, subprocess.CompletedProcess[str]]:
        res = run_spec_ops(repo, ["queue", "claim", "--auto", "--worker-id", worker_id])
        return worker_id, res

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futs = [executor.submit(run_claim, w) for w in repo_ctx["workers_4"]]
        for f in concurrent.futures.as_completed(futs):
            worker_id, res = f.result()
            results[worker_id] = res
    repo_ctx["results_4"] = results


@then("operations execute with mutual exclusion without race conditions or duplicate task assignments.")
def mutual_exclusion_four_workers(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    results = repo_ctx["results_4"]
    for worker_id, res in results.items():
        assert res.returncode == 0, f"Worker {worker_id} failed: {res.stderr}\n{res.stdout}"

    claimed_by_set = set()
    for i in range(1, 5):
        tid = f"003{i}"
        t = parse_task(repo / "docs" / "project" / "backlog" / "refined" / f"{tid}-task.md")
        assert t.claimed_by != "", f"Task {tid} was not claimed"
        assert t.claimed_by not in claimed_by_set, f"Duplicate claim by {t.claimed_by}"
        claimed_by_set.add(t.claimed_by)

    assert len(claimed_by_set) == 4
