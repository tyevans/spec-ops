"""BDD tests for US-0042: One-Command Developer Environment Doctor and Workspace Onboarding."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0042_workspace_doctor.feature")


@pytest.fixture
def bdd_us42_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(target_dir=repo, name="DoctorApp")

    # Initialize Git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@example.com"], cwd=repo, check=True, capture_output=True)

    # Initialize synchronized pyproject.toml and uv.lock
    (repo / "pyproject.toml").write_text('[project]\nname = "doctor-app"\nversion = "0.1.0"\n', encoding="utf-8")
    subprocess.run(["uv", "lock"], cwd=repo, check=True, capture_output=True)

    # Ensure .worktrees/ in .gitignore
    gi = repo / ".gitignore"
    gi_content = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    if ".worktrees/" not in gi_content:
        gi.write_text(gi_content + "\n.worktrees/\n", encoding="utf-8")

    # Initial commit
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    # Remove any pre-commit hook so it starts as FAIL
    hook_file = repo / ".git" / "hooks" / "pre-commit"
    if hook_file.exists():
        hook_file.unlink()

    return {
        "repo": repo,
        "last_res": None,
        "output": "",
    }


# --- Scenario 1: Diagnostic audit of local developer tooling and workspace health ---


@given("an engineer has cloned a SpecOps repository")
def engineer_cloned_repo(bdd_us42_context: dict[str, Any]):
    repo = bdd_us42_context["repo"]
    assert (repo / ".git").is_dir()
    assert (repo / ".gitignore").is_file()
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


@when(parsers.parse('the engineer executes "{command_str}"'))
def engineer_executes_doctor_cmd(bdd_us42_context: dict[str, Any], command_str: str):
    repo = bdd_us42_context["repo"]
    cmd_parts = shlex.split(command_str)
    if cmd_parts[0] == "spec-ops":
        cmd_args = [sys.executable, "-m", "spec_ops.cli.main", *cmd_parts[1:]]
    else:
        cmd_args = cmd_parts

    res = subprocess.run(cmd_args, cwd=repo, capture_output=True, text=True)
    bdd_us42_context["last_res"] = res
    bdd_us42_context["output"] = res.stdout + ("\n" + res.stderr if res.stderr else "")


@then("the command verifies:")
def verify_audit_table_results(bdd_us42_context: dict[str, Any]):
    output = bdd_us42_context["output"]
    assert "UV Package Manager" in output
    assert "Git Worktree Setup" in output
    assert "Pre-Commit Hooks" in output
    assert "Line Limit Health" in output
    assert "PASS" in output
    assert "FAIL" in output


@then(parsers.parse('the CLI indicates that {count:d} issue requires resolution.'))
def verify_cli_issue_count(bdd_us42_context: dict[str, Any], count: int):
    output = bdd_us42_context["output"]
    expected_phrase = f"{count} issue requires resolution"
    assert expected_phrase in output, f"Expected '{expected_phrase}' in output:\n{output}"


# --- Scenario 2: Automated repair of missing hooks and configuration ---


@given("the pre-commit hook is uninstalled")
def pre_commit_hook_is_uninstalled(bdd_us42_context: dict[str, Any]):
    repo = bdd_us42_context["repo"]
    hook_file = repo / ".git" / "hooks" / "pre-commit"
    if hook_file.exists():
        hook_file.unlink()
    assert not hook_file.exists()


@then("the command installs the git pre-commit hook")
def verify_pre_commit_hook_installed(bdd_us42_context: dict[str, Any]):
    repo = bdd_us42_context["repo"]
    hook_file = repo / ".git" / "hooks" / "pre-commit"
    assert hook_file.is_file()
    assert os.access(hook_file, os.X_OK)
    content = hook_file.read_text(encoding="utf-8")
    assert "spec-ops health" in content


@then("verifies the complete toolchain")
def verify_complete_toolchain(bdd_us42_context: dict[str, Any]):
    res = bdd_us42_context["last_res"]
    assert res.returncode == 0
    output = bdd_us42_context["output"]
    assert "FAIL" not in output


@then(parsers.parse('outputs "{expected_output}".'))
def verify_final_doctor_output(bdd_us42_context: dict[str, Any], expected_output: str):
    output = bdd_us42_context["output"]
    assert expected_output in output, f"Expected '{expected_output}' in output:\n{output}"
