"""Executable BDD scenarios using pytest-bdd for lockfile verification (US-0053, US-0111)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.worker import BacklogWorkerEngine
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
    "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
}

scenarios(
    "features/us_0053_immutable_supply_chain_lockfile_verification.feature",
    "features/us_0111_immutable_supply_chain_lockfile_verification_defense.feature",
)


@pytest.fixture
def bdd_lock_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="LockfileApp", target_dir=repo, profiles=["core", "bdd", "ddd", "security"])

    # Provide minimal pyproject.toml and generate valid uv.lock
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "lockfile-app"\nversion = "0.1.0"\nrequires-python = ">=3.13"\ndependencies = []\n',
        encoding="utf-8",
    )
    subprocess.run(["uv", "lock", "--offline"], cwd=repo, check=True, capture_output=True)

    # Initialize git repository
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Security Officer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "security@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    cfg.quality.preflight = []  # isolate lockfile checks
    cfg.execution.agent_command = "echo 'agent ran'"

    return {
        "repo": repo,
        "config": cfg,
        "queue": BacklogQueue(cfg.backlog_dir),
        "worker": BacklogWorkerEngine(cfg),
        "task": None,
        "worktree": None,
        "branch": None,
        "preflight_ok": None,
        "preflight_log": "",
        "worker_res": None,
        "cli_res": None,
    }


# ==============================================================================
# Shared Given Steps
# ==============================================================================


@given('a backlog task whose frontmatter does not declare "allows_dependencies: true"')
def task_without_dependencies_permission(bdd_lock_context: dict[str, Any]):
    queue: BacklogQueue = bdd_lock_context["queue"]
    task_file = queue.refined_dir / "0040-standard-feature.md"
    task = Task(
        id="0040",
        title="Standard Feature",
        status="Refined",
        target_bc="security",
        allows_dependencies=False,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_lock_context["task"] = task


@given(
    parsers.re(
        r'a backlog task with "allows_dependencies: true" explicitly approved in (?:its )?frontmatter'
    )
)
def task_with_dependencies_permission(bdd_lock_context: dict[str, Any]):
    queue: BacklogQueue = bdd_lock_context["queue"]
    task_file = queue.refined_dir / "0041-dependency-upgrade.md"
    task = Task(
        id="0041",
        title="Dependency Upgrade",
        status="Refined",
        target_bc="security",
        allows_dependencies=True,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_lock_context["task"] = task


@given("an autonomous feature branch submitted for completion")
def autonomous_feature_branch_submitted(bdd_lock_context: dict[str, Any]):
    repo: Path = bdd_lock_context["repo"]
    queue: BacklogQueue = bdd_lock_context["queue"]
    task_file = queue.refined_dir / "0042-gated-feature.md"
    task = Task(
        id="0042",
        title="Gated Feature",
        status="Refined",
        target_bc="security",
        allows_dependencies=False,
        branch="feat/task-0042",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_lock_context["task"] = task

    # Create branch and worktree
    wt_dir = repo / ".worktrees" / "task-0042"
    bdd_lock_context["worker"].create_worktree("feat/task-0042", wt_dir)
    # Touch pyproject.toml without permission
    (wt_dir / "pyproject.toml").write_text(
        '[project]\nname = "lockfile-app"\nversion = "0.1.0"\ndependencies = ["malicious-slop==1.0.0"]\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0042): unauthorized dependency addition"], cwd=wt_dir, check=True, capture_output=True)


# ==============================================================================
# When Steps
# ==============================================================================


@when('an autonomous coding agent modifies "pyproject.toml" or "uv.lock" to add an unapproved package')
def agent_modifies_pyproject_unapproved(bdd_lock_context: dict[str, Any]):
    repo: Path = bdd_lock_context["repo"]
    task: Task = bdd_lock_context["task"]
    wt_dir = repo / ".worktrees" / f"task-{task.id}"
    branch = f"feat/task-{task.id}"
    bdd_lock_context["worktree"] = wt_dir
    bdd_lock_context["branch"] = branch

    worker: BacklogWorkerEngine = bdd_lock_context["worker"]
    worker.create_worktree(branch, wt_dir)

    # Configure agent command to perform unapproved modification when worker executes
    agent_cmd = (
        f'{sys.executable} -c "'
        "open('pyproject.toml', 'w').write('[project]\\nname = \\\"lockfile-app\\\"\\nversion = \\\"0.1.0\\\"\\ndependencies = [\\\"unapproved-hallucinated-package==0.1.0\\\"]\\n')\""
    )
    bdd_lock_context["config"].execution.agent_command = agent_cmd

    # Also apply directly to worktree for direct preflight check
    (wt_dir / "pyproject.toml").write_text(
        '[project]\nname = "lockfile-app"\nversion = "0.1.0"\ndependencies = ["unapproved-hallucinated-package==0.1.0"]\n',
        encoding="utf-8",
    )


@when("the worker updates dependencies")
@when("the worker updates dependencies and executes preflight verification")
def worker_updates_dependencies_and_verifies(bdd_lock_context: dict[str, Any]):
    repo: Path = bdd_lock_context["repo"]
    task: Task = bdd_lock_context["task"]
    wt_dir = repo / ".worktrees" / f"task-{task.id}"
    branch = f"feat/task-{task.id}"
    bdd_lock_context["worktree"] = wt_dir
    bdd_lock_context["branch"] = branch

    worker: BacklogWorkerEngine = bdd_lock_context["worker"]
    worker.create_worktree(branch, wt_dir)

    # Modify pyproject.toml and add unpinned / drifted package to uv.lock
    (wt_dir / "pyproject.toml").write_text(
        '[project]\nname = "lockfile-app"\nversion = "0.1.0"\ndependencies = ["slopsquatting-pkg"]\n',
        encoding="utf-8",
    )
    # Corrupt or unpin uv.lock
    (wt_dir / "uv.lock").write_text(
        'version = 1\nrevision = 1\nrequires-python = ">=3.13"\n\n[[package]]\nname = "slopsquatting-pkg"\nversion = "*"\n',
        encoding="utf-8",
    )

    ok, log = worker.run_preflight(wt_dir, task=task)
    bdd_lock_context["preflight_ok"] = ok
    bdd_lock_context["preflight_log"] = log


@when(parsers.parse('the orchestrator executes "spec-ops queue complete <task-id>" under merge lock'))
def orchestrator_executes_queue_complete(bdd_lock_context: dict[str, Any]):
    repo: Path = bdd_lock_context["repo"]
    task: Task = bdd_lock_context["task"]

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "queue", "complete", task.canonical_id],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_lock_context["cli_res"] = res


# ==============================================================================
# Then Steps
# ==============================================================================


@then('"spec-ops worker" preflight detects the unauthorized lockfile alteration')
def preflight_detects_unauthorized_alteration(bdd_lock_context: dict[str, Any]):
    worker: BacklogWorkerEngine = bdd_lock_context["worker"]
    wt_dir: Path = bdd_lock_context["worktree"]
    task: Task = bdd_lock_context["task"]

    ok, log = worker.run_preflight(wt_dir, task=task)
    bdd_lock_context["preflight_ok"] = ok
    bdd_lock_context["preflight_log"] = log

    assert ok is False
    assert "Unauthorized Dependency Modification" in log


@then('the worker halts execution with an "Unauthorized Dependency Modification" violation')
def worker_halts_execution_with_violation(bdd_lock_context: dict[str, Any]):
    worker: BacklogWorkerEngine = bdd_lock_context["worker"]
    task: Task = bdd_lock_context["task"]

    res = worker.execute_task(task, local_merge=True, dry_run=False)
    bdd_lock_context["worker_res"] = res

    assert res.success is False
    assert "Unauthorized Dependency Modification" in res.message


@then('the task is flagged for human triage and not merged into "main".')
@then('the task is flagged for human triage and blocked from merging into "main".')
def verify_flagged_for_triage_not_merged(bdd_lock_context: dict[str, Any]):
    repo: Path = bdd_lock_context["repo"]
    task: Task = bdd_lock_context["task"]
    wt_dir = repo / ".worktrees" / f"task-{task.id}"

    # Worktree preserved for human triage
    assert wt_dir.exists()
    assert (wt_dir / "pyproject.toml").exists()

    # Main branch did not absorb changes
    main_pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "unapproved-hallucinated-package" not in main_pyproject


@then('"uv lock --check" executes to verify all package hashes match upstream cryptographic hashes')
def verify_uv_lock_check_executes(bdd_lock_context: dict[str, Any]):
    log = bdd_lock_context["preflight_log"]
    assert any(needle in log.lower() for needle in ("lockfile verification failed", "uv lock", "unpinned"))


@then("any untrusted or unpinned package causes preflight to fail with returncode 1.")
@then("any untrusted, unpinned, or drifted package causes preflight to fail with returncode 1.")
def verify_preflight_fails_returncode_1(bdd_lock_context: dict[str, Any]):
    assert bdd_lock_context["preflight_ok"] is False

    # Also verify CLI spec-ops security verify-lock fails with returncode 1
    wt_dir: Path = bdd_lock_context["worktree"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "security", "verify-lock", "--path", str(wt_dir)],
        cwd=str(bdd_lock_context["repo"]),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 1
    assert "Lockfile Verification Failed" in res.stderr or "unpinned" in res.stderr or "failed" in res.stderr


@then('the engine verifies that the branch diff against "main" contains zero unstaged or unapproved lockfile alterations')
def verify_engine_checks_diff(bdd_lock_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_lock_context["cli_res"]
    # The queue complete command must fail because task does not allow dependencies
    assert res.returncode == 1
    assert "Unauthorized Dependency Modification" in res.stderr or "Integration gate failed" in res.stderr


@then("passes only when lockfile integrity is cryptographically validated.")
def verify_passes_only_when_validated(bdd_lock_context: dict[str, Any]):
    repo: Path = bdd_lock_context["repo"]
    queue: BacklogQueue = bdd_lock_context["queue"]

    # Now test a clean task with zero lockfile changes passes
    clean_task_file = queue.refined_dir / "0043-clean-feature.md"
    clean_task = Task(
        id="0043",
        title="Clean Feature",
        status="Refined",
        target_bc="security",
        file_path=clean_task_file,
    )
    write_task_file(clean_task)

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "queue", "complete", "TASK-0043"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "passed integration gate" in res.stdout
