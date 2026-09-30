"""Comprehensive unit tests for incremental_runner.py to maximize mutant kill rate under mutmut."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from spec_ops.config.models import QualitySettings, SpecOpsConfig
from spec_ops.rescue.incremental_runner import (
    StepCacheData,
    StepRecord,
    _infer_name,
    clear_step_cache,
    execute_single_stage,
    file_matches_dependency,
    get_cache_path,
    get_dirty_files,
    get_step_dependencies,
    invalidate_dirty_step_caches,
    is_step_cache_valid,
    load_step_cache,
    match_stage,
    parse_prior_failures_from_prompt,
    record_pipeline_result,
    resolve_worktree_dir,
    run_incremental_rescue_test,
    save_step_cache,
)
from spec_ops.worker.preflight import PipelineResult, PreflightStage, StageResult


def test_get_cache_path(tmp_path: Path):
    p = get_cache_path(tmp_path)
    assert p == tmp_path / ".specops" / "step_cache.json"


def test_load_and_save_step_cache(tmp_path: Path):
    # Non-existent
    c0 = load_step_cache(tmp_path)
    assert c0.version == 1
    assert len(c0.steps) == 0

    # Save
    rec = StepRecord(
        name="test_step",
        command="pytest",
        passed=True,
        exit_code=0,
        output="passed",
        duration_seconds=1.5,
        timestamp=100.0,
        dependencies=["tests/"],
    )
    c1 = StepCacheData(version=1, steps={"test_step": rec})
    save_step_cache(tmp_path, c1)

    # Load back
    loaded = load_step_cache(tmp_path)
    assert loaded.version == 1
    assert "test_step" in loaded.steps
    s = loaded.steps["test_step"]
    assert s.name == "test_step"
    assert s.command == "pytest"
    assert s.passed is True
    assert s.exit_code == 0
    assert s.output == "passed"
    assert s.duration_seconds == 1.5
    assert s.timestamp == 100.0
    assert s.dependencies == ["tests/"]

    # Corrupt file
    cache_file = get_cache_path(tmp_path)
    cache_file.write_text("invalid json {{{", encoding="utf-8")
    corrupt = load_step_cache(tmp_path)
    assert corrupt.version == 1
    assert len(corrupt.steps) == 0


def test_clear_step_cache(tmp_path: Path):
    assert clear_step_cache(tmp_path) is False
    cache_file = get_cache_path(tmp_path)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{}", encoding="utf-8")
    assert clear_step_cache(tmp_path) is True
    assert not cache_file.exists()


def test_get_step_dependencies():
    assert "uv.lock" in get_step_dependencies("lockfile", "uv lock")
    assert "PRIORITY.md" in get_step_dependencies("health", "spec-ops health")
    assert ".ruff.toml" in get_step_dependencies("lint", "ruff check")
    assert "tests/" in get_step_dependencies("pytest", "uv run pytest")
    assert "tests/" in get_step_dependencies("custom", "other command")


def test_file_matches_dependency():
    assert file_matches_dependency("src/foo.py", "src/") is True
    assert file_matches_dependency("docs/bar.md", "src/") is False
    assert file_matches_dependency("uv.lock", "uv.lock") is True
    assert file_matches_dependency("other/uv.lock", "uv.lock") is True
    assert file_matches_dependency("pyproject.toml", "uv.lock") is False
    assert file_matches_dependency("./src/mod.py", "src/") is True


def test_is_step_cache_valid():
    step_passed = StepRecord(name="lint", command="ruff check", passed=True, dependencies=["src/"])
    step_failed = StepRecord(name="lint", command="ruff check", passed=False, dependencies=["src/"])

    assert is_step_cache_valid(step_failed, []) is False
    assert is_step_cache_valid(step_passed, []) is True
    assert is_step_cache_valid(step_passed, ["docs/readme.md"]) is True
    assert is_step_cache_valid(step_passed, ["src/main.py"]) is False


def test_invalidate_dirty_step_caches():
    steps = {
        "lock": StepRecord(name="lock", command="uv lock", passed=True, dependencies=["uv.lock"]),
        "lint": StepRecord(name="lint", command="ruff check", passed=True, dependencies=["src/"]),
        "failed": StepRecord(name="failed", command="fail", passed=False, dependencies=["src/"]),
    }
    cache = StepCacheData(version=1, steps=steps)

    # Invalidate with uv.lock modified
    inv = invalidate_dirty_step_caches(cache, ["uv.lock"])
    assert inv == ["lock"]
    assert cache.steps["lock"].passed is False
    assert cache.steps["lint"].passed is True

    # Isolated step immunity
    cache.steps["lint"].passed = True
    inv_iso = invalidate_dirty_step_caches(cache, ["src/a.py"], isolated_step="lint")
    assert "lint" not in inv_iso
    assert cache.steps["lint"].passed is True


def test_get_dirty_files(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)

    # Clean
    assert get_dirty_files(tmp_path) == []

    # Dirty untracked
    (tmp_path / "foo.py").write_text("print(1)", encoding="utf-8")
    dirty = get_dirty_files(tmp_path)
    assert "foo.py" in dirty

    # .specops should be ignored
    spec_dir = tmp_path / ".specops"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "step_cache.json").write_text("{}", encoding="utf-8")
    dirty_filtered = get_dirty_files(tmp_path)
    assert not any(".specops" in d for d in dirty_filtered)


def test_parse_prior_failures_from_prompt(tmp_path: Path):
    assert parse_prior_failures_from_prompt(tmp_path) is None

    prompt_file = tmp_path / ".task-prompt.md"
    prompt_file.write_text(
        "## Preflight Failure Feedback\n"
        "✓ 'uv lock --check' passed.\n"
        "✓ 'spec-ops health' passed.\n"
        "Command 'ruff check' failed (code 1):\n"
        "FAILED tests/test_unit.py::test_one\n",
        encoding="utf-8",
    )

    cache = parse_prior_failures_from_prompt(tmp_path)
    assert cache is not None
    assert cache.steps["lockfile"].passed is True
    assert cache.steps["health"].passed is True
    assert cache.steps["lint"].passed is False
    assert cache.steps["test"].passed is False


def test_infer_name():
    assert _infer_name("uv lock --check") == "lockfile"
    assert _infer_name("spec-ops health") == "health"
    assert _infer_name("ruff check") == "lint"
    assert _infer_name("flake8 src/") == "lint"
    assert _infer_name("pytest tests/") == "test"
    assert _infer_name("echo hello") == "stage"


def test_record_pipeline_result(tmp_path: Path):
    res = PipelineResult(
        success=True,
        stage_results=[
            StageResult(stage_name="lockfile", command="uv lock", success=True, exit_code=0, duration_seconds=0.2),
            StageResult(stage_name="test", command="pytest", success=False, exit_code=1, duration_seconds=1.1),
        ],
    )
    record_pipeline_result(tmp_path, res)
    loaded = load_step_cache(tmp_path)
    assert "lockfile" in loaded.steps
    assert loaded.steps["lockfile"].passed is True
    assert "test" in loaded.steps
    assert loaded.steps["test"].passed is False


def test_match_stage():
    stages = [
        PreflightStage(name="lockfile", command="uv lock --check"),
        PreflightStage(name="health", command="spec-ops health"),
        PreflightStage(name="lint", command="ruff check"),
        PreflightStage(name="test", command="pytest tests/"),
    ]

    assert match_stage(stages, "lockfile") == stages[0]
    assert match_stage(stages, "lock") == stages[0]
    assert match_stage(stages, "health") == stages[1]
    assert match_stage(stages, "lint") == stages[2]
    assert match_stage(stages, "ruff") == stages[2]
    assert match_stage(stages, "pytest") == stages[3]
    assert match_stage(stages, "test") == stages[3]
    assert match_stage(stages, "nonexistent") is None


def test_execute_single_stage(tmp_path: Path):
    stage = PreflightStage(name="echo", command="echo 'step executed'")
    cfg = SpecOpsConfig(root_dir=tmp_path)
    rec = execute_single_stage(stage, tmp_path, cfg)
    assert rec.name == "echo"
    assert rec.passed is True
    assert rec.exit_code == 0
    assert "step executed" in rec.output


def test_resolve_worktree_dir(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    wt_dir = tmp_path / ".worktrees" / "task-0025"
    wt_dir.mkdir(parents=True, exist_ok=True)

    # By task ID
    assert resolve_worktree_dir(cfg, "TASK-0025") == wt_dir
    assert resolve_worktree_dir(cfg, "0025") == wt_dir

    # Single worktree in parent
    assert resolve_worktree_dir(cfg) == wt_dir


def test_run_incremental_rescue_test_modes(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    cfg.quality.stages = [
        PreflightStage(name="step_a", command="echo 'A passed'"),
        PreflightStage(name="step_b", command="echo 'B passed'"),
    ]


    wt = tmp_path / ".worktrees" / "task-0099"
    wt.mkdir(parents=True, exist_ok=True)

    # 1. Nonexistent worktree
    ret_err = run_incremental_rescue_test(cfg, worktree_dir=tmp_path / "nonexistent")
    assert ret_err == 1

    # 2. Targeted step isolation
    ret_iso = run_incremental_rescue_test(cfg, step="step_a", worktree_dir=wt)
    assert ret_iso == 0
    cache = load_step_cache(wt)
    assert cache.steps["step_a"].passed is True

    # 3. Targeted step nonexistent
    ret_none = run_incremental_rescue_test(cfg, step="step_z", worktree_dir=wt)
    assert ret_none == 1

    # 4. Mode only-failed when none failed
    ret_no_failed = run_incremental_rescue_test(cfg, only_failed=True, worktree_dir=wt)
    assert ret_no_failed == 0

    # 5. Mode only-failed with a failed step
    cache.steps["step_b"] = StepRecord(name="step_b", command="echo 'B passed'", passed=False, exit_code=1)
    save_step_cache(wt, cache)
    ret_failed = run_incremental_rescue_test(cfg, only_failed=True, worktree_dir=wt)
    assert ret_failed == 0
    cache_reloaded = load_step_cache(wt)
    assert cache_reloaded.steps["step_b"].passed is True

    # 6. Mode full incremental with cached steps
    ret_incr = run_incremental_rescue_test(cfg, worktree_dir=wt)
    assert ret_incr == 0
