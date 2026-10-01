"""BDD tests for US-0054: Pre-commit git hook and supply-chain sentinel."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0054_precommit_hooks.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="HookApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Security Officer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "security@specops.test"], cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "last_cmd_res": None,
        "last_commit_res": None,
    }


# --- Scenario 1: Installing pre-commit hook in git repository ---


@given("an initialized SpecOps repository")
def specops_repo_initialized(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    assert (repo / ".git").is_dir()
    assert (repo / "specops.toml").is_file()


@when(parsers.parse('the user runs "{command_str}"'))
def run_cli_command(bdd_context: dict[str, Any], command_str: str):
    repo = bdd_context["repo"]
    cmd_parts = command_str.split()
    cmd = [sys.executable, "-m", "spec_ops.cli.main"] + cmd_parts[1:]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    bdd_context["last_cmd_res"] = res
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"


@then(parsers.parse('a pre-commit executable is created in "{hook_rel_path}"'))
def pre_commit_executable_created(bdd_context: dict[str, Any], hook_rel_path: str):
    repo = bdd_context["repo"]
    hook_file = repo / hook_rel_path.removeprefix("./")
    assert hook_file.is_file(), f"{hook_file} does not exist"
    assert os.access(hook_file, os.X_OK), f"{hook_file} is not executable"


@then("the hook invokes security and lockfile verification checks")
def hook_invokes_security_and_lockfile_checks(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    hook_file = repo / ".git" / "hooks" / "pre-commit"
    content = hook_file.read_text(encoding="utf-8")
    assert "security" in content
    assert "lockfile" in content or "uv.lock" in content
    assert "spec-ops security hook run" in content


# --- Scenario 2: Blocking commits with unapproved lockfile drift ---


@given("an active pre-commit hook installed")
def active_pre_commit_hook_installed(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "security", "hook", "install"]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    assert res.returncode == 0, f"Hook install failed: {res.stderr}\n{res.stdout}"

    hook_file = repo / ".git" / "hooks" / "pre-commit"
    assert hook_file.is_file()
    assert os.access(hook_file, os.X_OK)


@when(parsers.parse('a commit stages an unapproved change to "{lockfile_name}"'))
def commit_stages_unapproved_lockfile(bdd_context: dict[str, Any], lockfile_name: str):
    repo = bdd_context["repo"]
    lock_file = repo / lockfile_name
    lock_file.write_text("unapproved-dependency-mutation = '0.9.9'\n", encoding="utf-8")

    subprocess.run(["git", "add", lockfile_name], cwd=repo, check=True, capture_output=True)

    env = os.environ.copy()
    env["SPEC_OPS_PYTHON"] = sys.executable

    res = subprocess.run(
        ["git", "commit", "-m", "feat: unapproved lockfile drift"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    bdd_context["last_commit_res"] = res


@then("the pre-commit hook exits with code 1")
def pre_commit_hook_exits_code_1(bdd_context: dict[str, Any]):
    res = bdd_context["last_commit_res"]
    assert res is not None
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output: {res.stdout}\n{res.stderr}"
    combined = res.stdout + res.stderr
    assert "lockfile" in combined.lower() or "violation" in combined.lower()


@then("the git commit is aborted")
def git_commit_aborted(bdd_context: dict[str, Any]):
    repo = bdd_context["repo"]
    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    assert status_res.returncode == 0
    # uv.lock is still staged and uncommitted
    assert "uv.lock" in status_res.stdout
