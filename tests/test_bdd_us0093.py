"""BDD step definitions for US-0093: Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.cli.parser import build_parser
from spec_ops.cli.rescue_handler import handle_rescue_command
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.incremental_runner import (
    StepCacheData,
    StepRecord,
    get_cache_path,
    save_step_cache,
)
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.scaffold.init import init_project
from spec_ops.worker.preflight import PreflightStage

scenarios("features/us_0093_fast_incremental_in_worktree_preflight_runner.feature")


@pytest.fixture
def preflight_runner_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="IncrementalPreflightApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    # Executable shims for uv, spec-ops, ruff
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    uv_shim = bin_dir / "uv"
    uv_shim.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "lock" ]; then\n'
        '  echo "Resolved 47 packages in 0.88ms"\n'
        "  exit 0\n"
        "fi\n"
        'echo "tests/test_visualizer.py . [100%]"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    uv_shim.chmod(0o755)

    spec_ops_shim = bin_dir / "spec-ops"
    spec_ops_shim.write_text(
        "#!/usr/bin/env bash\n"
        'echo "0 file limit violations (<500 lines)"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    spec_ops_shim.chmod(0o755)

    ruff_shim = bin_dir / "ruff"
    ruff_shim.write_text(
        "#!/usr/bin/env bash\n"
        'echo "All checks passed!"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    ruff_shim.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")

    cfg = load_config(repo)
    # Configure preflight stages on cfg
    cfg.quality.stages = [
        PreflightStage(name="lockfile", command="uv lock --check", timeout_seconds=30.0),
        PreflightStage(name="health", command="spec-ops health", timeout_seconds=30.0),
        PreflightStage(name="lint", command="ruff check && ruff format --check", timeout_seconds=30.0),
        PreflightStage(name="test", command="uv run pytest tests/test_visualizer.py", timeout_seconds=60.0),
    ]

    return {"repo": repo, "config": cfg, "bin_dir": bin_dir}


@given(parsers.parse('a rescued worktree "{wt_path}" where "uv lock --check" and "spec-ops health" previously passed'))
def setup_rescued_worktree_with_passed_steps(preflight_runner_ctx: dict[str, Any], wt_path: str):
    repo = preflight_runner_ctx["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    create_worktree(repo, branch="feat/TASK-0010", worktree_dir=wt_dir)

    # Create task file in refined
    backlog_dir = repo / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    task_file = backlog_dir / "0010-visualizer-task.md"
    task = Task(id="0010", title="Visualizer Component", status="Refined", file_path=task_file)
    write_task_file(task)

    preflight_runner_ctx["wt_dir"] = wt_dir
    preflight_runner_ctx["task"] = task

    # Initialize cache with passed lockfile and health
    cache = StepCacheData(
        version=1,
        steps={
            "lockfile": StepRecord(
                name="lockfile",
                command="uv lock --check",
                passed=True,
                exit_code=0,
                output="Resolved 47 packages in 0.88ms",
                dependencies=["uv.lock", "pyproject.toml"],
            ),
            "health": StepRecord(
                name="health",
                command="spec-ops health",
                passed=True,
                exit_code=0,
                output="0 file limit violations",
                dependencies=["src/", "docs/", "pyproject.toml"],
            ),
        },
    )
    preflight_runner_ctx["cache"] = cache


@given(parsers.parse('only the unit test suite "{failed_cmd}" failed'))
def setup_failed_unit_test(preflight_runner_ctx: dict[str, Any], failed_cmd: str):
    wt_dir = preflight_runner_ctx["wt_dir"]
    cache = preflight_runner_ctx["cache"]
    cache.steps["test"] = StepRecord(
        name="test",
        command=failed_cmd,
        passed=False,
        exit_code=1,
        output=f"FAILED {failed_cmd}",
        dependencies=["src/", "tests/"],
    )
    save_step_cache(wt_dir, cache)

    # Prompt feedback
    prompt_file = wt_dir / ".task-prompt.md"
    prompt_file.write_text(
        "## Preflight Failure Feedback\n"
        "✓ 'uv lock --check' passed.\n"
        "✓ 'spec-ops health' passed.\n"
        f"Command '{failed_cmd}' failed (code 1):\n"
        "FAILED tests/test_visualizer.py::test_render\n",
        encoding="utf-8",
    )


@when(parsers.parse('the engineer is inside "{wt_path}" and executes "{cmd}"'))
def execute_test_inside_worktree(
    preflight_runner_ctx: dict[str, Any],
    wt_path: str,
    cmd: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
):
    repo = preflight_runner_ctx["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    monkeypatch.chdir(wt_dir)

    cfg = preflight_runner_ctx["config"]
    parser = build_parser()
    args_list = cmd.split()[1:]  # strip 'spec-ops'
    parsed_args = parser.parse_args(args_list)

    t0 = time.perf_counter()
    exit_code = handle_rescue_command(parsed_args, cfg)
    elapsed = time.perf_counter() - t0

    captured = capsys.readouterr()
    preflight_runner_ctx["exit_code"] = exit_code
    preflight_runner_ctx["stdout"] = captured.out
    preflight_runner_ctx["stderr"] = captured.err
    preflight_runner_ctx["elapsed"] = elapsed


@then(parsers.parse('only "{expected_cmd}" is re-executed'))
def verify_only_command_reexecuted(preflight_runner_ctx: dict[str, Any], expected_cmd: str):
    stdout = preflight_runner_ctx["stdout"]
    assert f"Re-executing failed step: {expected_cmd}" in stdout or expected_cmd in stdout
    assert "PASSED" in stdout or "succeeded" in stdout


@then("previously passed invariant checks and lockfile validations are skipped")
def verify_passed_checks_skipped(preflight_runner_ctx: dict[str, Any]):
    stdout = preflight_runner_ctx["stdout"]
    assert "Skipping cached step 'uv lock --check'" in stdout
    assert "Skipping cached step 'spec-ops health'" in stdout


@then(parsers.parse("the check completes in under {limit:d} seconds."))
def verify_duration_under_seconds(preflight_runner_ctx: dict[str, Any], limit: int):
    elapsed = preflight_runner_ctx["elapsed"]
    assert elapsed < float(limit), f"Expected under {limit}s, got {elapsed:.2f}s"


@given("the engineer edits a file inside the rescued worktree")
def engineer_edits_file_in_worktree(preflight_runner_ctx: dict[str, Any]):
    wt_dir = preflight_runner_ctx.get("wt_dir")
    if not wt_dir:
        repo = preflight_runner_ctx["repo"]
        wt_dir = repo / ".worktrees" / "task-0010"
        create_worktree(repo, branch="feat/TASK-0010", worktree_dir=wt_dir)
        preflight_runner_ctx["wt_dir"] = wt_dir

    edited_file = wt_dir / "src" / "visualizer.py"
    edited_file.parent.mkdir(parents=True, exist_ok=True)
    edited_file.write_text("# modified visualizer file\nx = 42\n", encoding="utf-8")


@when(parsers.parse('the engineer runs "{cmd}"'))
def engineer_runs_command(
    preflight_runner_ctx: dict[str, Any],
    cmd: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
):
    wt_dir = preflight_runner_ctx.get("wt_dir")
    if wt_dir:
        monkeypatch.chdir(wt_dir)

    cfg = preflight_runner_ctx["config"]
    parser = build_parser()
    args_list = cmd.split()[1:]
    parsed_args = parser.parse_args(args_list)

    t0 = time.perf_counter()
    exit_code = handle_rescue_command(parsed_args, cfg)
    elapsed = time.perf_counter() - t0

    captured = capsys.readouterr()
    preflight_runner_ctx["exit_code"] = exit_code
    preflight_runner_ctx["stdout"] = captured.out
    preflight_runner_ctx["stderr"] = captured.err
    preflight_runner_ctx["elapsed"] = elapsed


@then(parsers.parse('only the linting and formatting check ("{lint_cmd}") runs'))
def verify_only_lint_runs(preflight_runner_ctx: dict[str, Any], lint_cmd: str):
    stdout = preflight_runner_ctx["stdout"]
    assert f"Executing isolated step 'lint'" in stdout
    assert lint_cmd in stdout


@then("the terminal displays immediate pass/fail status without running integration tests.")
def verify_immediate_status_no_integration_tests(preflight_runner_ctx: dict[str, Any]):
    stdout = preflight_runner_ctx["stdout"]
    assert "PASSED: Step 'lint'" in stdout
    # Ensure integration / full test suite was not run
    assert "tests/test_visualizer.py" not in stdout or "pytest" not in stdout.lower()


@given("the engineer has iterated using targeted step checks")
def engineer_has_iterated_using_targeted_checks(preflight_runner_ctx: dict[str, Any]):
    repo = preflight_runner_ctx["repo"]
    wt_dir = preflight_runner_ctx.get("wt_dir")
    if not wt_dir:
        wt_dir = repo / ".worktrees" / "task-0010"
        create_worktree(repo, branch="feat/TASK-0010", worktree_dir=wt_dir)
        preflight_runner_ctx["wt_dir"] = wt_dir

    backlog_dir = repo / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    task_file = backlog_dir / "0010-visualizer-task.md"
    if not task_file.exists():
        task = Task(id="0010", title="Visualizer Component", status="Refined", file_path=task_file)
        write_task_file(task)
        preflight_runner_ctx["task"] = task

    # Seed cache as having targeted iterations
    cache = StepCacheData(
        version=1,
        steps={
            "lint": StepRecord(name="lint", command="ruff check && ruff format --check", passed=True, exit_code=0),
            "test": StepRecord(name="test", command="uv run pytest tests/test_visualizer.py", passed=True, exit_code=0),
        },
    )
    save_step_cache(wt_dir, cache)
    assert get_cache_path(wt_dir).exists()



@then("the rescue manager bypasses all caches and executes the complete, un-truncated preflight pipeline:")
def verify_bypasses_caches_full_pipeline(preflight_runner_ctx: dict[str, Any]):
    stdout = preflight_runner_ctx["stdout"]
    assert "Bypassing preflight caches" in stdout or "un-truncated preflight verification pipeline" in stdout
    assert "uv lock --check" in stdout
    assert "spec-ops health" in stdout
    assert "ruff check" in stdout
    assert "pytest" in stdout


@then('integration into "main" proceeds only when all preflight stages pass unconditionally.')
def verify_integration_into_main_proceeds(preflight_runner_ctx: dict[str, Any]):
    exit_code = preflight_runner_ctx["exit_code"]
    stdout = preflight_runner_ctx["stdout"]
    assert exit_code == 0
    assert "SUCCESS" in stdout or "Successfully verified, merged, and completed" in stdout
