"""BDD tests for US-0082: Multi-Stage Extensible Preflight Validation Pipeline with Early Fast-Fail."""

from __future__ import annotations

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
from spec_ops.worker.preflight import PreflightPipeline, PreflightStage

scenarios("features/us_0082_preflight_pipeline.feature")


@pytest.fixture
def bdd_us82_context(tmp_path: Path) -> dict[str, Any]:
    worktree = tmp_path / "worktree"
    worktree.mkdir(parents=True, exist_ok=True)
    init_project(name="PreflightApp", target_dir=worktree)

    # Initialize a clean git repo inside worktree
    subprocess.run(["git", "init", "-b", "main"], cwd=worktree, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=worktree, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=worktree, check=True, capture_output=True)

    # Create dummy compliant source and test files
    src = worktree / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "app.py").write_text("# compliant source file\ndef run():\n    return 42\n", encoding="utf-8")
    tests = worktree / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_app.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    # Add and commit
    subprocess.run(["git", "add", "-A"], cwd=worktree, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=worktree, check=True, capture_output=True)

    config = load_config(root_dir=worktree)
    engine = BacklogWorkerEngine(config)

    return {
        "worktree": worktree,
        "config": config,
        "engine": engine,
        "pipeline": None,
        "result": None,
    }


@given(parsers.parse('a worker executing "{task_id}" in an isolated worktree'))
def setup_worker_executing_task(bdd_us82_context: dict[str, Any], task_id: str):
    wt = bdd_us82_context["worktree"]
    clean_id = task_id.replace("TASK-", "")
    task = Task(
        id=clean_id,
        title=f"Task {task_id}",
        status="Refined",
        file_path=wt / "docs" / "project" / "backlog" / "refined" / f"{clean_id}-task.md",
    )
    write_task_file(task)
    bdd_us82_context["task"] = task


@given(parsers.parse('the preflight configuration defines sequential stages: "lockfile", "health", and "tests"'))
def configure_sequential_stages(bdd_us82_context: dict[str, Any]):
    wt = bdd_us82_context["worktree"]
    pipeline = PreflightPipeline(
        stages=[
            PreflightStage(name="lockfile", command="uv lock --check", required=True, timeout_seconds=30.0),
            PreflightStage(
                name="health",
                command=f"{sys.executable} -m spec_ops.cli.main health",
                required=True,
                timeout_seconds=30.0,
            ),
            PreflightStage(
                name="tests",
                command=f"{sys.executable} -m pytest tests/test_app.py -q",
                required=True,
                timeout_seconds=60.0,
            ),
        ],
        cwd=wt,
    )
    bdd_us82_context["pipeline"] = pipeline


@when('an agent updates "pyproject.toml" but fails to update "uv.lock"')
def simulate_lockfile_drift(bdd_us82_context: dict[str, Any]):
    wt = bdd_us82_context["worktree"]
    pyproject = wt / "pyproject.toml"
    current = pyproject.read_text(encoding="utf-8") if pyproject.exists() else "[project]\nname='test'\nversion='0.1.0'\n"
    pyproject.write_text(current + "\n# Modified dependency\ndependencies = ['unlocked-package>=9.9.9']\n", encoding="utf-8")
    (wt / "uv.lock").write_text("# stale lockfile\nversion = 1\n", encoding="utf-8")


@when("the worker runs the preflight pipeline")
def execute_preflight_pipeline(bdd_us82_context: dict[str, Any]):
    pipeline = bdd_us82_context["pipeline"]
    result = pipeline.run()
    bdd_us82_context["result"] = result


@then(parsers.parse('stage "lockfile" executes "uv lock --check" and fails with an out-of-sync error'))
def verify_lockfile_stage_failed(bdd_us82_context: dict[str, Any]):
    result = bdd_us82_context["result"]
    assert result.failed_stage is not None
    assert result.failed_stage.stage_name == "lockfile"
    assert result.failed_stage.command == "uv lock --check"
    assert result.failed_stage.success is False
    assert result.failed_stage.exit_code != 0


@then(parsers.parse('the preflight pipeline immediately halts without executing subsequent "{stage1}" or "{stage2}" stages'))
def verify_downstream_stages_halted(bdd_us82_context: dict[str, Any], stage1: str, stage2: str):
    result = bdd_us82_context["result"]
    # Only 1 stage actually executed
    assert len(result.stage_results) == 1
    executed_names = [r.stage_name for r in result.stage_results]
    assert stage1 not in executed_names
    assert stage2 not in executed_names
    assert stage1 in result.aborted_stages
    assert stage2 in result.aborted_stages


@then("the failure output isolates the lockfile drift as the specific stage-1 failure.")
def verify_failure_isolation(bdd_us82_context: dict[str, Any]):
    result = bdd_us82_context["result"]
    assert result.success is False
    logs = result.logs.lower()
    assert "stage 1" in logs or "stage-1" in logs or "lockfile" in logs
    assert "drift" in logs or "lock" in logs or "halted" in logs


# --- Scenario 2: Complete Pipeline Execution Across All Configured Gates ---


@given("an isolated worktree with valid lockfiles and clean file limits")
def clean_worktree_valid_lockfiles(bdd_us82_context: dict[str, Any]):
    wt = bdd_us82_context["worktree"]
    # Ensure PRIORITY.md and backlog files exist and match
    assert (wt / "src" / "app.py").is_file()
    assert (wt / "docs" / "project" / "backlog" / "PRIORITY.md").is_file()


@when("the worker executes the full preflight pipeline")
def execute_full_preflight_pipeline(bdd_us82_context: dict[str, Any]):
    wt = bdd_us82_context["worktree"]
    pipeline = PreflightPipeline(
        stages=[
            PreflightStage(name="lockfile", command=f"{sys.executable} -c 'import sys; sys.exit(0)'", required=True, timeout_seconds=10.0),
            PreflightStage(name="health", command=f"{sys.executable} -m spec_ops.cli.main health", required=True, timeout_seconds=30.0),
            PreflightStage(name="test", command=f"{sys.executable} -m pytest tests/test_app.py -q", required=True, timeout_seconds=60.0),
        ],
        cwd=wt,
    )
    bdd_us82_context["pipeline"] = pipeline
    result = pipeline.run()
    bdd_us82_context["result"] = result


@then("the worker executes:")
def verify_worker_executes_table(bdd_us82_context: dict[str, Any]):
    result = bdd_us82_context["result"]
    assert len(result.stage_results) == 3
    executed_names = [r.stage_name for r in result.stage_results]
    assert executed_names == ["lockfile", "health", "test"]
    assert all(r.success for r in result.stage_results)


@then("each stage executes within its dedicated timeout limit")
def verify_stages_within_timeout(bdd_us82_context: dict[str, Any]):
    pipeline = bdd_us82_context["pipeline"]
    result = bdd_us82_context["result"]
    for res, stage in zip(result.stage_results, pipeline.stages):
        assert not res.timeout
        assert res.duration_seconds < stage.timeout_seconds


@then("the worker logs a structured pipeline summary confirming all gates passed.")
def verify_pipeline_summary_logged(bdd_us82_context: dict[str, Any]):
    result = bdd_us82_context["result"]
    assert result.success is True
    assert "summary" in result.logs.lower()
    assert "all configured preflight gates passed successfully" in result.logs.lower()
