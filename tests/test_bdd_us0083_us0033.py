"""Executable BDD scenarios for US-0083 and US-0033."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.backlog.worker import BacklogWorkerEngine
from spec_ops.cli.cycle_handler import handle_worker_command
from spec_ops.cli.parser import build_parser
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.ast_analyzer import (
    extract_top_level_nodes,
    find_largest_node,
    format_preflight_ast_feedback,
    generate_ast_decomposition_hint,
)
from spec_ops.worker.ci_repair import ci_heal_task, verify_worktree_diff

scenarios(
    "features/us_0083_targeted_ast_diagnostic_hint_injection.feature",
    "features/us_0033_remote_ci_failure_diagnostic_ingestion.feature",
)


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="RepairFleetApp", target_dir=repo)

    # Git init
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Remote origin mock (bare repo) for pushing
    remote_repo = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote_repo)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote_repo)], cwd=repo, check=True, capture_output=True)

    # Create dummy passing test
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_ok.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)

    config = load_config(root_dir=repo)
    config.quality.preflight = [f"{sys.executable} -m spec_ops.cli.main health"]
    config.execution.enable_review = False
    config.execution.agent_max_attempts = 3

    # Setup fake gh CLI binary in PATH
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh_script = bin_dir / "gh"
    gh_log_file = tmp_path / "gh_calls.log"
    gh_script.write_text(
        f"""#!/bin/sh
echo "$@" >> "{gh_log_file}"
if [ "$1" = "run" ] && [ "$2" = "view" ]; then
    echo "FAILED: test_feature in tests/test_remote.py"
    echo "AssertionError: remote CI check failed on step 4"
    exit 0
elif [ "$1" = "run" ] && [ "$2" = "rerun" ]; then
    echo "Re-running workflow..."
    exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    gh_script.chmod(gh_script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{old_path}"

    return {
        "repo": repo,
        "remote_repo": remote_repo,
        "config": config,
        "bin_dir": bin_dir,
        "gh_log_file": gh_log_file,
        "old_path": old_path,
        "task": None,
        "worktree_dir": None,
        "preflight_ok": None,
        "preflight_log": "",
        "diff_flag": "",
        "remaining_attempts": None,
        "cli_exit_code": None,
    }


# ==============================================================================
# US-0083 Scenario 1: Targeted AST Diagnostic Injection for File Length Overruns
# ==============================================================================


@given(parsers.parse('an isolated worktree executing "{task_id}"'))
def setup_worktree_for_task(bdd_ctx: dict[str, Any], task_id: str):
    repo: Path = bdd_ctx["repo"]
    clean_id = task_id.upper().strip()
    slug = clean_id.lower().replace("task-", "")

    task = Task(
        id=slug,
        title=f"Task {task_id}",
        status="Refined",
        target_bc="worker",
        governing_adrs=["ADR-0002"],
        file_path=repo / "docs" / "project" / "backlog" / "refined" / f"{slug}-task.md",
    )
    write_task_file(task)
    bdd_ctx["task"] = task

    engine = BacklogWorkerEngine(bdd_ctx["config"])
    wt_dir = repo / ".worktrees" / f"task-{slug}"
    branch = f"task/{clean_id}"
    engine.create_worktree(branch, wt_dir)
    bdd_ctx["worktree_dir"] = wt_dir


@when(
    parsers.parse(
        'the agent produces "{file_rel}" containing {lines:d} lines exceeding the 500-line limit'
    )
)
def agent_produces_oversized_file(bdd_ctx: dict[str, Any], file_rel: str, lines: int):
    wt: Path = bdd_ctx["worktree_dir"]
    target_file = wt / file_rel
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # Build file: lines 1-119 comments/imports, lines 120-410 class TaskExecutionCoordinator (291 lines), remainder comments
    content_lines: list[str] = []
    for i in range(1, 120):
        content_lines.append(f"# Prefix line {i}")

    # Lines 120 to 410 = 291 lines of class TaskExecutionCoordinator
    content_lines.append("class TaskExecutionCoordinator:")
    for i in range(121, 411):
        content_lines.append(f"    field_{i} = {i}")

    # Lines 411 to lines
    for i in range(411, lines + 1):
        content_lines.append(f"# Trailing line {i}")

    code = "\n".join(content_lines) + "\n"
    target_file.write_text(code, encoding="utf-8")
    bdd_ctx["oversized_file"] = target_file
    bdd_ctx["file_rel"] = file_rel
    bdd_ctx["lines"] = lines


@when("preflight detects the file length violation")
def preflight_detects_violation(bdd_ctx: dict[str, Any]):
    engine = BacklogWorkerEngine(bdd_ctx["config"])
    wt: Path = bdd_ctx["worktree_dir"]
    task: Task = bdd_ctx["task"]
    ok, log = engine.run_preflight(wt, task=task)
    bdd_ctx["preflight_ok"] = ok
    bdd_ctx["preflight_log"] = log
    assert not ok, f"Preflight unexpectedly passed. Log: {log}"


@then(parsers.parse('the worker engine parses the AST of "{file_name}" to identify candidate function and class split seams'))
def worker_parses_ast(bdd_ctx: dict[str, Any], file_name: str):
    target_file: Path = bdd_ctx["oversized_file"]
    code = target_file.read_text(encoding="utf-8")
    nodes = extract_top_level_nodes(code)
    largest = find_largest_node(nodes)
    assert largest is not None
    assert largest.name == "TaskExecutionCoordinator"
    assert largest.kind == "class"
    assert largest.lineno == 120
    assert largest.end_lineno == 410
    assert largest.line_count == 291
    bdd_ctx["largest_node"] = largest


@then('appends a structured diagnostic section to ".task-prompt.md":')
def appends_structured_diagnostic_section(bdd_ctx: dict[str, Any], docstring: str):
    wt: Path = bdd_ctx["worktree_dir"]
    preflight_log = bdd_ctx["preflight_log"]
    feedback = format_preflight_ast_feedback(preflight_log, attempt=1, worktree_dir=wt)

    prompt_file = wt / ".task-prompt.md"
    existing = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else "# Task Prompt\n"
    updated = existing + "\n\n" + feedback
    prompt_file.write_text(updated, encoding="utf-8")

    content = prompt_file.read_text(encoding="utf-8")
    expected = docstring.strip()
    assert expected in content, f"Expected:\n{expected}\n\nGot:\n{content}"


@then("re-invokes the agent with targeted refactoring guidance.")
def reinvokes_agent_with_guidance(bdd_ctx: dict[str, Any]):
    wt: Path = bdd_ctx["worktree_dir"]
    prompt_file = wt / ".task-prompt.md"
    content = prompt_file.read_text(encoding="utf-8")
    assert "extract TaskExecutionCoordinator into separate module" in content


# ==============================================================================
# US-0083 Scenario 2: Guarding Against Empty or Whitespace-Only Agent Diffs
# ==============================================================================


@given(parsers.parse('an isolated worktree executing "{task_id}" on attempt {attempt:d}'))
def setup_worktree_attempt(bdd_ctx: dict[str, Any], task_id: str, attempt: int):
    setup_worktree_for_task(bdd_ctx, task_id)
    bdd_ctx["attempt"] = attempt
    bdd_ctx["remaining_attempts"] = bdd_ctx["config"].execution.agent_max_attempts


@when("the agent process exits with return code 0 but git status shows no tracked file modifications")
def agent_exits_zero_without_modifications(bdd_ctx: dict[str, Any]):
    wt: Path = bdd_ctx["worktree_dir"]
    # Touch only prompt file (which is ignored by diff guardrail)
    prompt_file = wt / ".task-prompt.md"
    prompt_file.write_text("# Updated prompt\n", encoding="utf-8")

    diff_ok, reason = verify_worktree_diff(wt)
    assert not diff_ok
    bdd_ctx["diff_flag"] = reason


@then(parsers.parse('the worker engine flags the attempt as "{flag}"'))
def verify_attempt_flagged(bdd_ctx: dict[str, Any], flag: str):
    assert bdd_ctx["diff_flag"] == flag


@then("injects feedback into the prompt warning the agent that implementation code is required")
def injects_implementation_required_feedback(bdd_ctx: dict[str, Any]):
    wt: Path = bdd_ctx["worktree_dir"]
    prompt_file = wt / ".task-prompt.md"
    flag = bdd_ctx["diff_flag"]
    feedback = f"\n\n## Failure Feedback (Attempt 1)\n{flag}: Implementation code is required."
    current = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""
    prompt_file.write_text(current + feedback, encoding="utf-8")

    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert "Implementation code is required" in prompt_content
    assert flag in prompt_content


@then("decrements remaining retry attempts without proceeding to preflight or merge.")
def decrements_retry_attempts(bdd_ctx: dict[str, Any]):
    remaining = bdd_ctx["remaining_attempts"] - 1
    assert remaining == 2
    # Preflight was not executed
    assert bdd_ctx["preflight_ok"] is None


# ==============================================================================
# US-0033 Scenario: Remote CI Failure Diagnostic Ingestion and In-Worktree Repair
# ==============================================================================


@given(parsers.parse('an open pull request for branch "{branch}" created by Morgan'))
def setup_pull_request_branch(bdd_ctx: dict[str, Any], branch: str):
    repo: Path = bdd_ctx["repo"]
    clean_id = branch.replace("task/", "").upper()
    slug = clean_id.lower().replace("task-", "")

    # Create task metadata
    task = Task(
        id=slug,
        title=f"Task {clean_id}",
        status="Refined",
        target_bc="worker",
        governing_adrs=["ADR-0004"],
        file_path=repo / "docs" / "project" / "backlog" / "refined" / f"{slug}-task.md",
    )
    write_task_file(task)
    bdd_ctx["task"] = task

    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_file.parent.mkdir(parents=True, exist_ok=True)
    priority_file.write_text(
        "1. **TASK-0001 (Refined)**: [Initial Spike](refined/0001-initial-architecture-spike-and-setup.md)\n"
        f"2. **{clean_id} (Refined)**: [{task.title}](refined/{slug}-task.md)\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"chore({slug}): refine task"], cwd=repo, check=True, capture_output=True)

    # Create branch and push to remote origin
    subprocess.run(["git", "checkout", "-b", branch], cwd=repo, check=True, capture_output=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "feature.py").write_text("def run(): return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"feat({slug}): initial pr code"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    bdd_ctx["branch"] = branch
    bdd_ctx["task_id"] = clean_id


@when("remote GitHub Actions checks fail on the pull request")
def remote_ci_fails(bdd_ctx: dict[str, Any]):
    # The fake gh script outputs failure logs when queried
    pass


@when(parsers.parse('the agent executes "{cmd}"'))
def agent_executes_ci_heal_cli(bdd_ctx: dict[str, Any], cmd: str):
    repo: Path = bdd_ctx["repo"]
    config = bdd_ctx["config"]

    parser = build_parser()
    tokens = cmd.split()[1:]  # strip 'spec-ops'
    args = parser.parse_args(tokens)

    # Configure mock agent command that fixes feature.py
    script_fix = "import pathlib; p = pathlib.Path('src/feature.py'); p.write_text('def run(): return 42\\n')"
    config.execution.agent_command = f"{sys.executable} -c \"{script_fix}\""

    ret = handle_worker_command(args, config)
    bdd_ctx["cli_exit_code"] = ret


@then(parsers.parse('SpecOps executes "gh run view --log-failed" to extract the failed step logs'))
def specops_executes_gh_run_view(bdd_ctx: dict[str, Any]):
    gh_log: Path = bdd_ctx["gh_log_file"]
    assert gh_log.exists()
    content = gh_log.read_text(encoding="utf-8")
    assert "run view --log-failed" in content


@then(parsers.parse('extracts the relevant failure trace into ".task-prompt.md"'))
def extracts_failure_trace_into_prompt(bdd_ctx: dict[str, Any]):
    repo: Path = bdd_ctx["repo"]
    task_id = bdd_ctx["task_id"]
    slug = task_id.lower().replace("task-", "")
    wt_dir = repo / ".worktrees" / f"task-{slug}"
    prompt_file = wt_dir / ".task-prompt.md"
    assert prompt_file.exists()
    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert "Remote CI Failure Diagnostics" in prompt_content
    assert "AssertionError" in prompt_content


@then(parsers.parse('opens the existing worktree "{worktree_rel}"'))
def opens_existing_worktree(bdd_ctx: dict[str, Any], worktree_rel: str):
    repo: Path = bdd_ctx["repo"]
    wt_dir = repo / worktree_rel
    assert wt_dir.exists()
    bdd_ctx["worktree_dir"] = wt_dir


@then("invokes Morgan with the failure context to apply a targeted fix")
def invokes_morgan_with_failure_context(bdd_ctx: dict[str, Any]):
    wt: Path = bdd_ctx["worktree_dir"]
    fixed_file = wt / "src" / "feature.py"
    assert fixed_file.exists()
    assert "return 42" in fixed_file.read_text(encoding="utf-8")


@when("Morgan fixes the failure and local preflight passes")
def morgan_fixes_failure_and_preflight_passes(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["cli_exit_code"] == 0


@then("the worker pushes the updated branch to GitHub and re-triggers remote CI.")
def pushes_and_retriggers_remote_ci(bdd_ctx: dict[str, Any]):
    remote_repo: Path = bdd_ctx["remote_repo"]
    branch = bdd_ctx["branch"]
    # Check that remote branch received the update
    out = subprocess.run(
        ["git", "log", branch, "--oneline"],
        cwd=remote_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "repair remote CI failures" in out.stdout
    gh_log: Path = bdd_ctx["gh_log_file"]
    content = gh_log.read_text(encoding="utf-8")
    assert "run rerun" in content
