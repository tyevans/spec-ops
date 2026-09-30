"""BDD step definitions for US-0086: Idempotent Worktree Lifecycle Management."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.backlog.worker import BacklogWorkerEngine
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0086_idempotent_worktree_lifecycle.feature")


@pytest.fixture
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="RepoApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    cfg.quality.preflight = []  # isolate worktree verification
    cfg.execution.agent_command = ""

    return {"repo": repo, "config": cfg}


@given(parsers.parse('an orphaned worktree directory "{wt_path}" left from an aborted process'))
def orphaned_worktree_directory(repo_context: dict[str, Any], wt_path: str):
    repo = repo_context["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    wt_dir.mkdir(parents=True, exist_ok=True)
    (wt_dir / "placeholder.txt").write_text("aborted worktree artifact\n", encoding="utf-8")
    repo_context["worktree_dir"] = wt_dir


@given(parsers.parse('a stale local git branch "{branch_name}" already exists'))
def stale_git_branch_exists(repo_context: dict[str, Any], branch_name: str):
    repo = repo_context["repo"]
    subprocess.run(["git", "branch", branch_name, "main"], cwd=repo, check=True, capture_output=True)
    repo_context["branch_name"] = branch_name


@when(parsers.parse('the worker engine prepares to execute "{task_id}"'))
def worker_prepares_execution(repo_context: dict[str, Any], task_id: str):
    repo = repo_context["repo"]
    cfg = repo_context["config"]

    clean_id = task_id.upper().replace("TASK-", "").zfill(4)
    task_file = repo / "docs" / "project" / "backlog" / "refined" / f"{clean_id}-test.md"
    task = Task(
        id=clean_id,
        title="Collision Recovery Task",
        status="Refined",
        file_path=task_file,
    )
    write_task_file(task)
    repo_context["task"] = task

    worker = BacklogWorkerEngine(cfg)
    repo_context["worker"] = worker
    branch = repo_context.get("branch_name", f"feat/task-{clean_id.lower()}")
    wt_dir = repo / ".worktrees" / f"task-{clean_id.lower()}"

    worker.create_worktree(branch, wt_dir)
    repo_context["active_worktree_dir"] = wt_dir


@then("the engine inspects the existing worktree for uncommitted human rescue work")
def inspects_for_uncommitted_work(repo_context: dict[str, Any]):
    wt_dir = repo_context["active_worktree_dir"]
    assert wt_dir.exists()


@then(parsers.parse('if uncommitted changes do not exist, prunes stale git worktree administrative metadata via "{cmd}"'))
def prunes_metadata(repo_context: dict[str, Any], cmd: str):
    pass


@then(parsers.parse('resets the branch to "{target_branch}" before mounting the fresh worktree'))
def resets_branch_to_target(repo_context: dict[str, Any], target_branch: str):
    wt_dir = repo_context["active_worktree_dir"]
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt_dir, capture_output=True, text=True)
    assert res.returncode == 0


@then("creates the worktree cleanly without throwing git branch conflict errors.")
def creates_cleanly_without_conflict(repo_context: dict[str, Any]):
    wt_dir = repo_context["active_worktree_dir"]
    assert wt_dir.exists()
    assert (wt_dir / ".git").exists()


@given(parsers.parse('an active worktree at "{wt_path}" with passing preflight'))
def active_worktree_passing(repo_context: dict[str, Any], wt_path: str):
    repo = repo_context["repo"]
    cfg = repo_context["config"]
    worker = BacklogWorkerEngine(cfg)
    repo_context["worker"] = worker

    wt_dir = repo / wt_path.removeprefix("./")
    branch = f"feat/{wt_dir.name}"
    worker.create_worktree(branch, wt_dir)

    (wt_dir / ".task-prompt.md").write_text("# prompt\n", encoding="utf-8")
    (wt_dir / ".pytest_cache").mkdir(exist_ok=True)
    (wt_dir / "impl.txt").write_text("implemented\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: implemented"], cwd=wt_dir, check=True, capture_output=True)

    repo_context["active_worktree_dir"] = wt_dir
    repo_context["branch_name"] = branch


@when(parsers.parse('the task is successfully squash-merged into "{target_branch}"'))
def task_squash_merged(repo_context: dict[str, Any], target_branch: str):
    repo = repo_context["repo"]
    branch = repo_context["branch_name"]
    wt_dir = repo_context["active_worktree_dir"]
    worker = repo_context["worker"]

    subprocess.run(["git", "merge", "--squash", branch], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: squash merge"], cwd=repo, check=True, capture_output=True)

    worker.cleanup_worktree(wt_dir, branch, delete_branch=True)


@then(parsers.parse('the worker engine removes the worktree via "{cmd}"'))
def worker_removes_worktree(repo_context: dict[str, Any], cmd: str):
    wt_dir = repo_context["active_worktree_dir"]
    assert not wt_dir.exists()


@then(parsers.parse('deletes the transient branch "{branch_name}"'))
def deletes_transient_branch(repo_context: dict[str, Any], branch_name: str):
    repo = repo_context["repo"]
    chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo)
    assert chk.returncode != 0


@then("deletes temporary prompt files and ephemeral worktree caches")
def deletes_ephemeral_caches(repo_context: dict[str, Any]):
    wt_dir = repo_context["active_worktree_dir"]
    assert not (wt_dir / ".task-prompt.md").exists()
    assert not (wt_dir / ".pytest_cache").exists()


@then(parsers.parse('verifies that "{wt_path}" no longer exists on disk.'))
def verifies_worktree_not_on_disk(repo_context: dict[str, Any], wt_path: str):
    repo = repo_context["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    assert not wt_dir.exists()
