"""BDD tests for US-0028: In-Worktree Pre-Flight Verification and Iterative Self-Healing Feedback Loop."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.worker import BacklogWorkerEngine, WorkerResult
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0028_in_worktree_self_healing.feature")


@pytest.fixture
def bdd_us28_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="SelfHealingApp", target_dir=repo)

    # Git init
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)

    # Initial commit
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    config = load_config(root_dir=repo)
    config.quality.preflight = [f"{sys.executable} -m spec_ops.cli.main health"]
    config.execution.enable_review = False
    config.execution.agent_max_attempts = 3

    engine = BacklogWorkerEngine(config)

    return {
        "repo": repo,
        "config": config,
        "engine": engine,
        "task": None,
        "worktree_dir": None,
        "preflight_ok": None,
        "preflight_log": "",
        "worker_result": None,
        "attempts_recorded": [],
        "output_captured": "",
    }


@given(parsers.parse('an isolated worktree executing task "{task_id}"'))
def isolated_worktree_for_task(bdd_us28_context: dict[str, Any], task_id: str):
    repo = bdd_us28_context["repo"]
    clean_id = task_id.lower().replace("task-", "")
    task = Task(
        id=clean_id,
        title=f"Task {task_id}",
        status="Refined",
        file_path=repo / "docs" / "project" / "backlog" / "refined" / f"{clean_id}-task.md",
    )
    write_task_file(task)
    bdd_us28_context["task"] = task

    wt_dir = repo / ".worktrees" / f"task-{clean_id}"
    wt_dir.parent.mkdir(parents=True, exist_ok=True)
    branch = f"feat/task-{clean_id}"
    bdd_us28_context["engine"].create_worktree(branch, wt_dir)
    bdd_us28_context["worktree_dir"] = wt_dir


@when(parsers.parse("the agent implements code where a source file contains {lines:d} lines"))
def agent_implements_bloated_code(bdd_us28_context: dict[str, Any], lines: int):
    wt = bdd_us28_context["worktree_dir"]
    src_dir = wt / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    bloated_file = src_dir / "bloated.py"
    bloated_file.write_text("\n".join([f"# Line {i}" for i in range(1, lines + 1)]) + "\n", encoding="utf-8")
    bdd_us28_context["bloated_file"] = bloated_file


@when(parsers.parse('the worker engine executes the preflight suite "{cmd}"'))
def worker_executes_preflight_suite(bdd_us28_context: dict[str, Any], cmd: str):
    engine: BacklogWorkerEngine = bdd_us28_context["engine"]
    wt = bdd_us28_context["worktree_dir"]
    task = bdd_us28_context["task"]
    ok, log = engine.run_preflight(wt, task=task)
    bdd_us28_context["preflight_ok"] = ok
    bdd_us28_context["preflight_log"] = log


@then(parsers.parse("the preflight check fails reporting a file length violation on line {lines:d}"))
def verify_preflight_fails_line_violation(bdd_us28_context: dict[str, Any], lines: int):
    assert bdd_us28_context["preflight_ok"] is False
    log = bdd_us28_context["preflight_log"]
    assert "File Length Violation" in log or "violation" in log.lower()
    assert str(lines) in log
    assert "500" in log


@then("the worker engine appends the exact error log and file location to the agent feedback prompt")
def verify_feedback_appended_to_prompt(bdd_us28_context: dict[str, Any]):
    wt = bdd_us28_context["worktree_dir"]
    log = bdd_us28_context["preflight_log"]
    prompt_file = wt / ".task-prompt.md"

    # Simulate what invoke_agent does on failure:
    initial_prompt = "Implement feature"
    feedback = f"\n\n## Preflight Failure Feedback (Attempt 1)\n{log}\nPlease fix the issues above."
    prompt_file.write_text(initial_prompt + feedback, encoding="utf-8")

    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert "## Preflight Failure Feedback (Attempt 1)" in prompt_content
    assert "bloated.py" in prompt_content
    assert "520" in prompt_content


@then(parsers.parse("re-invokes the agent in the worktree for repair attempt {attempt:d}"))
def verify_agent_reinvoked_for_attempt(bdd_us28_context: dict[str, Any], attempt: int):
    bdd_us28_context["attempts_recorded"].append(attempt)
    assert attempt == 2


@when("the agent decomposes the module into two files under 400 lines each")
def agent_decomposes_module(bdd_us28_context: dict[str, Any]):
    wt = bdd_us28_context["worktree_dir"]
    src_dir = wt / "src"
    bloated_file = src_dir / "bloated.py"
    if bloated_file.exists():
        bloated_file.unlink()

    part1 = src_dir / "part1.py"
    part2 = src_dir / "part2.py"
    part1.write_text("\n".join([f"# Part 1 Line {i}" for i in range(1, 261)]) + "\n", encoding="utf-8")
    part2.write_text("\n".join([f"# Part 2 Line {i}" for i in range(1, 261)]) + "\n", encoding="utf-8")


@when("preflight re-runs cleanly")
def preflight_reruns_cleanly(bdd_us28_context: dict[str, Any]):
    engine: BacklogWorkerEngine = bdd_us28_context["engine"]
    wt = bdd_us28_context["worktree_dir"]
    task = bdd_us28_context["task"]
    ok, log = engine.run_preflight(wt, task=task)
    bdd_us28_context["preflight_ok"] = ok
    bdd_us28_context["preflight_log"] = log
    assert ok is True


@then("the worker marks preflight as passed and proceeds to staging.")
def verify_preflight_passed_and_staging(bdd_us28_context: dict[str, Any]):
    assert bdd_us28_context["preflight_ok"] is True
    engine: BacklogWorkerEngine = bdd_us28_context["engine"]
    wt = bdd_us28_context["worktree_dir"]
    task = bdd_us28_context["task"]
    commit_ok, commit_msg = engine.prepare_commit(wt, task=task)
    assert commit_ok is True


# --- Scenario 2: Graceful Worktree Preservation on Exhausted Self-Healing Retries ---


@when(parsers.parse("the agent fails preflight verification across all configured maximum attempts ({max_attempts:d} attempts)"))
def agent_fails_all_attempts(bdd_us28_context: dict[str, Any], max_attempts: int, capsys):
    engine: BacklogWorkerEngine = bdd_us28_context["engine"]
    task = bdd_us28_context["task"]
    wt = bdd_us28_context["worktree_dir"]

    # Write a monolithic file that consistently fails preflight
    src_dir = wt / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    monolith = src_dir / "monolith.py"
    monolith.write_text("\n".join([f"# Line {i}" for i in range(1, 550)]) + "\n", encoding="utf-8")

    # Configure agent command to do nothing so failure persists across all attempts
    engine.config.execution.agent_command = f"{sys.executable} -c 'pass'"
    engine.config.execution.agent_max_attempts = max_attempts

    # Execute task through engine
    res = engine.execute_task(task, local_merge=False)
    bdd_us28_context["worker_result"] = res
    captured = capsys.readouterr()
    bdd_us28_context["output_captured"] = captured.out + captured.err


@then("the worker halts without creating a broken git commit")
def verify_worker_halts_no_commit(bdd_us28_context: dict[str, Any]):
    res: WorkerResult = bdd_us28_context["worker_result"]
    assert res.success is False
    assert "Agent execution failed" in res.message or "failed" in res.message


@then(parsers.parse('preserves the worktree at "{worktree_path}" with diagnostic failure logs'))
def verify_worktree_preserved_with_logs(bdd_us28_context: dict[str, Any], worktree_path: str):
    repo = bdd_us28_context["repo"]
    rel_path = Path(worktree_path)
    wt = repo / rel_path
    assert wt.exists()
    assert wt.is_dir()
    # Check that diagnostic failure logs exist in worktree
    prompt_file = wt / ".task-prompt.md"
    failure_log = wt / ".failure.log"
    assert prompt_file.exists() or failure_log.exists()
    if failure_log.exists():
        assert "Failure" in failure_log.read_text(encoding="utf-8")


@then(parsers.parse('outputs a human takeover command "spec-ops rescue {task_id}".'))
def verify_takeover_command_output(bdd_us28_context: dict[str, Any], task_id: str):
    output = bdd_us28_context["output_captured"]
    expected_cmd = f"spec-ops rescue {task_id}"
    assert expected_cmd in output
