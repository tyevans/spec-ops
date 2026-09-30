"""BDD tests for US-0072: Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.backlog.worker import BacklogWorkerEngine
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0072_zero_dependency_native_git_hook_scaffolding.feature")


@pytest.fixture
def bdd_us72_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="NativeHooksApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Sasha"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "sasha@specops.test"], cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    config = load_config(root_dir=repo)

    return {
        "repo": repo,
        "config": config,
        "last_cmd_res": None,
        "worktree_dir": None,
        "last_commit_res": None,
    }


# --- Scenario 1: Scaffolding native git pre-commit and pre-push hooks ---


@given("a git repository initialized with SpecOps")
def git_repo_initialized(bdd_us72_context: dict[str, Any]):
    repo = bdd_us72_context["repo"]
    assert (repo / ".git").is_dir()
    assert (repo / "specops.toml").is_file()


@when(parsers.parse('the security officer runs "{command_str}"'))
def run_scaffold_hooks_command(bdd_us72_context: dict[str, Any], command_str: str):
    repo = bdd_us72_context["repo"]
    cmd_parts = command_str.split()
    cmd = [sys.executable, "-m", "spec_ops.cli.main"] + cmd_parts[1:]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    bdd_us72_context["last_cmd_res"] = res


@then(parsers.parse('executable shell scripts are installed directly into "{pre_commit}" and "{pre_push}"'))
def verify_hooks_installed(bdd_us72_context: dict[str, Any], pre_commit: str, pre_push: str):
    repo = bdd_us72_context["repo"]
    pre_commit_file = repo / pre_commit.removeprefix("./")
    pre_push_file = repo / pre_push.removeprefix("./")

    assert pre_commit_file.is_file(), f"{pre_commit_file} not found"
    assert pre_push_file.is_file(), f"{pre_push_file} not found"

    assert os.access(pre_commit_file, os.X_OK), f"{pre_commit_file} is not executable"
    assert os.access(pre_push_file, os.X_OK), f"{pre_push_file} is not executable"


@then(parsers.parse('the pre-commit hook runs "{health_cmd}" verifying file length limits (<500 lines) and staged file invariants'))
def verify_pre_commit_runs_health(bdd_us72_context: dict[str, Any], health_cmd: str):
    repo = bdd_us72_context["repo"]
    content = (repo / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert health_cmd in content or "spec-ops health" in content
    assert "<500 lines" in content or "file length" in content.lower()


@then("does not require third-party python pre-commit tooling.")
def verify_no_third_party_tooling(bdd_us72_context: dict[str, Any]):
    repo = bdd_us72_context["repo"]
    content = (repo / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert content.startswith("#!/bin/sh")


# --- Scenario 2: Enforcing strict backlog isolation on feature branches via hook ---


@given(parsers.parse('a developer or agent working on feature branch "{branch_name}"'))
def switch_to_feature_branch(bdd_us72_context: dict[str, Any], branch_name: str):
    repo = bdd_us72_context["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "hooks", "--native", "--force"]
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo, check=True, capture_output=True)


@when(parsers.parse('the worker attempts to stage and commit modifications to "{file_path}"'))
def attempt_backlog_commit(bdd_us72_context: dict[str, Any], file_path: str):
    repo = bdd_us72_context["repo"]
    target = repo / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Unauthorized backlog alteration\n", encoding="utf-8")

    subprocess.run(["git", "add", file_path], cwd=repo, check=True, capture_output=True)
    res = subprocess.run(
        ["git", "commit", "-m", "chore: illicit backlog change"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_us72_context["last_commit_res"] = res


@then("the native pre-commit hook intercepts the commit")
def pre_commit_intercepts(bdd_us72_context: dict[str, Any]):
    res = bdd_us72_context["last_commit_res"]
    assert res is not None


@then("aborts with exit code 1")
def verify_abort_exit_code(bdd_us72_context: dict[str, Any]):
    res = bdd_us72_context["last_commit_res"]
    assert res.returncode == 1


@then(parsers.parse('displays "{expected_message}"'))
def verify_display_message(bdd_us72_context: dict[str, Any], expected_message: str):
    res = bdd_us72_context["last_commit_res"]
    combined = res.stdout + res.stderr
    assert expected_message in combined


# --- Scenario 3: Propagating hooks automatically to autonomous worker worktrees ---


@given(parsers.parse('an autonomous task execution dispatched via "{dispatch_cmd}"'))
def autonomous_task_dispatched(bdd_us72_context: dict[str, Any], dispatch_cmd: str):
    repo = bdd_us72_context["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "hooks", "--native", "--force"]
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)

    task_file = repo / "docs" / "project" / "backlog" / "refined" / "0020-autonomous-task.md"
    task_file.write_text(
        "---\n"
        "id: '0020'\n"
        "title: Autonomous Task Execution\n"
        "status: Refined\n"
        "target_bc: worker\n"
        "---\n\n"
        "# TASK-0020\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: add task 0020"], cwd=repo, check=True, capture_output=True)


@when(parsers.parse('the worker engine provisions an isolated git worktree at "{wt_rel_path}"'))
def worker_engine_provisions_worktree(bdd_us72_context: dict[str, Any], wt_rel_path: str):
    repo = bdd_us72_context["repo"]
    config = bdd_us72_context["config"]
    worker = BacklogWorkerEngine(config)

    wt_dir = repo / wt_rel_path.removeprefix("./")
    branch = "task/TASK-0020"
    worker.create_worktree(branch, wt_dir)
    bdd_us72_context["worktree_dir"] = wt_dir


@then(parsers.parse('the hook scaffolder ensures "{hooks_path}" or shared git hooks remain active in the worktree'))
def verify_worktree_hooks_active(bdd_us72_context: dict[str, Any], hooks_path: str):
    repo = bdd_us72_context["repo"]
    wt_dir = bdd_us72_context["worktree_dir"]

    expected_hooks_dir = repo / hooks_path.removeprefix("./")
    assert expected_hooks_dir.exists() or expected_hooks_dir.is_symlink()

    res = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=wt_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    resolved = Path(res.stdout.strip())
    resolved_path = resolved if resolved.is_absolute() else (wt_dir / resolved).resolve()
    assert (resolved_path / "pre-commit").exists()


@then("blocks the autonomous agent from committing backdoor mocks or invalid lockfiles before creating a pull request.")
def verify_worktree_blocks_backdoor(bdd_us72_context: dict[str, Any]):
    wt_dir = bdd_us72_context["worktree_dir"]

    # Attempt to commit unauthorized backdoor mock
    test_file = wt_dir / "tests" / "test_backdoor.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("from unittest.mock import MagicMock\nm = MagicMock()\n", encoding="utf-8")

    subprocess.run(["git", "add", "tests/test_backdoor.py"], cwd=wt_dir, check=True, capture_output=True)
    res = subprocess.run(
        ["git", "commit", "-m", "feat: commit backdoor mock"],
        cwd=wt_dir,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert "Anti-Mock Violation" in (res.stdout + res.stderr)
