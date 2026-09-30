"""BDD tests for US-0037: Local Pre-Commit Invariant Gate and Proactive Anti-Rot Warnings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.hooks import PreCommitHookEvaluator, install_pre_commit_hook, run_spec_ops_health_hook

scenarios("features/us_0037_pre_commit_invariant_gate.feature")


@pytest.fixture
def bdd_us37_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="HookApp", target_dir=repo)

    # Initialize Git repository
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@example.com"], cwd=repo, check=True, capture_output=True)

    # Clean initial commit
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    # Install native pre-commit hook
    install_pre_commit_hook(repo)

    config = load_config(root_dir=repo)

    return {
        "repo": repo,
        "config": config,
        "last_commit_res": None,
        "terminal_output": "",
        "eval_result": None,
    }


# --- Scenario 1: Blocking staged file that exceeds hard invariant limit ---


@given(parsers.parse('a staged source file "{file_path}" with {lines:d} lines'))
def staged_violating_file(bdd_us37_context: dict[str, Any], file_path: str, lines: int):
    repo = bdd_us37_context["repo"]
    target = repo / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join([f"# parser line {i}" for i in range(1, lines + 1)]) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", file_path], cwd=repo, check=True, capture_output=True)


@when(parsers.parse('the engineer executes "{commit_cmd}"'))
def engineer_executes_git_commit(bdd_us37_context: dict[str, Any], commit_cmd: str):
    repo = bdd_us37_context["repo"]
    import shlex
    args = shlex.split(commit_cmd)
    res = subprocess.run(args, cwd=repo, capture_output=True, text=True)
    bdd_us37_context["last_commit_res"] = res
    bdd_us37_context["terminal_output"] = res.stdout + ("\n" + res.stderr if res.stderr else "")


@then('the "spec-ops-health" pre-commit hook aborts the commit')
def verify_pre_commit_hook_aborts(bdd_us37_context: dict[str, Any]):
    res = bdd_us37_context["last_commit_res"]
    assert res.returncode != 0


@then(parsers.parse('the terminal displays "{expected_text}"'))
def verify_terminal_displays_text(bdd_us37_context: dict[str, Any], expected_text: str):
    output = bdd_us37_context["terminal_output"]
    assert expected_text in output


@then("the commit is rejected until the file is decomposed into modular submodules.")
def verify_commit_rejected_until_fixed(bdd_us37_context: dict[str, Any]):
    repo = bdd_us37_context["repo"]
    # Check that git status still has staged file
    st = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    assert "parser.py" in st.stdout


# --- Scenario 2: Proactive warning on files approaching limit without blocking commit ---


@given("no source files exceed the hard 500-line invariant limit")
def no_files_exceed_hard_limit(bdd_us37_context: dict[str, Any]):
    evaluator = PreCommitHookEvaluator(root_dir=bdd_us37_context["repo"])
    res = evaluator.evaluate()
    assert res.violations_count == 0


@then('the "spec-ops-health" pre-commit hook allows the commit to proceed')
def verify_pre_commit_hook_allows_commit(bdd_us37_context: dict[str, Any]):
    res = bdd_us37_context["last_commit_res"]
    assert res.returncode == 0


@then(parsers.parse('the terminal displays a warning: "{expected_warning}".'))
def verify_terminal_displays_warning(bdd_us37_context: dict[str, Any], expected_warning: str):
    output = bdd_us37_context["terminal_output"]
    assert expected_warning in output


# --- Scenario 3: Verifying PRIORITY.md and disk state synchronization ---


@given(parsers.parse('"{priority_path}" is synchronized with tasks on disk'))
def priority_md_synchronized(bdd_us37_context: dict[str, Any], priority_path: str):
    repo = bdd_us37_context["repo"]
    p_file = repo / priority_path
    assert p_file.is_file()
    evaluator = PreCommitHookEvaluator(root_dir=repo)
    res = evaluator.evaluate()
    assert "PRIORITY.md is synchronized with disk state." in res.output


@when('the pre-commit hook runs "spec-ops health"')
def pre_commit_hook_runs_spec_ops_health(bdd_us37_context: dict[str, Any]):
    repo = bdd_us37_context["repo"]
    res = run_spec_ops_health_hook(repo)
    bdd_us37_context["eval_result"] = res
    bdd_us37_context["terminal_output"] = res.output


@then(parsers.parse('the check passes with "{expected_msg}".'))
def verify_check_passes_with_message(bdd_us37_context: dict[str, Any], expected_msg: str):
    eval_res = bdd_us37_context["eval_result"]
    assert eval_res.success is True
    assert eval_res.exit_code == 0
    assert expected_msg in eval_res.output
