"""Executable BDD acceptance tests for US-0080: Pluggable Agent Runners and Worktree Simulation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.config.loader import load_config
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.runners import AgentRunner, build_agent_cmd, prepare_runner_environment

scenarios("features/us_0080_pluggable_agent_runners.feature")

CLI_ENV = {**os.environ, "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}


@pytest.fixture
def us0080_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="RunnerTestApp")

    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_sample.py").write_text("def test_sample(): pass\n", encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    config = load_config(root_dir=repo)
    return {
        "repo": repo,
        "config": config,
        "task": None,
        "cmd_argv": None,
        "env_map": None,
        "cli_result": None,
        "worktree_dir": None,
        "main_head_before": None,
    }


# ==============================================================================
# Scenario: Configuring Custom Agent Runner with Template Placeholders
# ==============================================================================


@given('a SpecOps configuration defining "execution.agent_command" as "aider --message-file {prompt_file} --yes --auto-commits"')
def configure_custom_agent_command(us0080_context: dict[str, Any]):
    cfg: SpecOpsConfig = us0080_context["config"]
    cfg.execution.agent_command = "aider --message-file {prompt_file} --yes --auto-commits"


@given('a refined task "TASK-0014" targeting bounded context "worker"')
def create_refined_task_0014(us0080_context: dict[str, Any]):
    repo: Path = us0080_context["repo"]
    refined_dir = repo / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    task_file = refined_dir / "0014-pluggable-agent-runners.md"
    task = Task(
        id="0014",
        title="Pluggable Agent Runners",
        status="Refined",
        target_bc="worker",
        governing_adrs=["ADR-0001", "ADR-0002", "ADR-0003"],
        governing_prds=["PRD-0004"],
        file_path=task_file,
    )
    write_task_file(task)
    us0080_context["task"] = task


@when('the worker engine prepares the execution environment for "TASK-0014"')
def prepare_worker_execution_environment(us0080_context: dict[str, Any]):
    repo: Path = us0080_context["repo"]
    cfg: SpecOpsConfig = us0080_context["config"]
    task: Task = us0080_context["task"]

    wt_dir = repo / ".worktrees" / f"task-{task.id}"
    wt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = wt_dir / ".task-prompt.md"
    prompt_file.write_text("# Task Prompt\n\nContract details.", encoding="utf-8")

    runner = AgentRunner(cfg)
    argv = runner.build_command(prompt_file=prompt_file, worktree_dir=wt_dir)
    env_map = runner.prepare_environment(worktree_dir=wt_dir)

    us0080_context["worktree_dir"] = wt_dir
    us0080_context["prompt_file"] = prompt_file
    us0080_context["cmd_argv"] = argv
    us0080_context["env_map"] = env_map


@then('the worker interpolates "{prompt_file}" to the absolute path of ".worktrees/task-0014/.task-prompt.md"')
def verify_interpolated_prompt_file(us0080_context: dict[str, Any]):
    argv: list[str] = us0080_context["cmd_argv"]
    prompt_file: Path = us0080_context["prompt_file"]
    expected_path = str(prompt_file.resolve())

    assert argv[0] == "aider"
    assert "--message-file" in argv
    idx = argv.index("--message-file")
    assert argv[idx + 1] == expected_path


@then('sets environment variables "SPEC_OPS_WORKTREE" and "PWD" to the worktree directory')
def verify_environment_variables(us0080_context: dict[str, Any]):
    env_map: dict[str, str] = us0080_context["env_map"]
    wt_dir: Path = us0080_context["worktree_dir"]
    expected_wt = str(wt_dir.resolve())

    assert env_map["SPEC_OPS_WORKTREE"] == expected_wt
    assert env_map["PWD"] == expected_wt


@then('constructs the process argument list safely without shell quote mangling.')
def verify_process_argv_safety(us0080_context: dict[str, Any]):
    argv: list[str] = us0080_context["cmd_argv"]
    expected = [
        "aider",
        "--message-file",
        str(us0080_context["prompt_file"].resolve()),
        "--yes",
        "--auto-commits",
    ]
    assert argv == expected


# ==============================================================================
# Scenario: Zero-Cost Worktree Dry-Run Simulation
# ==============================================================================


@given('a refined task "TASK-0010" in "docs/project/backlog/refined/"')
def create_refined_task_0010(us0080_context: dict[str, Any]):
    repo: Path = us0080_context["repo"]
    refined_dir = repo / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    task_file = refined_dir / "0010-dry-run-task.md"
    task = Task(
        id="0010",
        title="Zero Cost Dry Run Simulation",
        status="Refined",
        target_bc="worker",
        governing_adrs=["ADR-0001", "ADR-0002", "ADR-0003"],
        governing_prds=["PRD-0004"],
        file_path=task_file,
    )
    write_task_file(task)
    us0080_context["task"] = task

    # Record HEAD on main before dry-run
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    us0080_context["main_head_before"] = res.stdout.strip()


@when('the user runs "spec-ops worker --task TASK-0010 --dry-run"')
def run_worker_dry_run(us0080_context: dict[str, Any]):
    repo: Path = us0080_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "worker", "--task", "TASK-0010", "--dry-run"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    us0080_context["cli_result"] = res


@then('an isolated worktree is created at ".worktrees/task-0010" on branch "feat/task-0010"')
def verify_worktree_creation_during_simulation(us0080_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = us0080_context["cli_result"]
    assert "Created isolated worktree at .worktrees/task-0010 on branch feat/task-0010" in res.stdout


@then('the task prompt is generated at ".worktrees/task-0010/.task-prompt.md" containing governing ADRs, PRDs, and preflight commands')
def verify_task_prompt_generation(us0080_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = us0080_context["cli_result"]
    assert "Task prompt generated at" in res.stdout
    assert ".worktrees/task-0010/.task-prompt.md" in res.stdout


@then("no external agent process is spawned")
def verify_no_external_agent_spawned(us0080_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = us0080_context["cli_result"]
    assert "Zero-cost dry-run simulation completed cleanly." in res.stdout or "Dry-run successful" in res.stdout
    assert "Agent attempt" not in res.stdout


@then('the worker cleans up the dry-run worktree and reports success without modifying git history on "main".')
def verify_dry_run_cleanup_and_zero_git_drift(us0080_context: dict[str, Any]):
    repo: Path = us0080_context["repo"]
    res: subprocess.CompletedProcess[str] = us0080_context["cli_result"]

    assert res.returncode == 0
    # Cleaned up worktree directory
    wt_dir = repo / ".worktrees" / "task-0010"
    assert not wt_dir.exists()

    # Git history on main is strictly unchanged
    head_after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    assert head_after == us0080_context["main_head_before"]
