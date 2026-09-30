"""Unit tests for PreflightPipeline, PreflightStage, and stage runner orchestration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.config.models import QualitySettings, SpecOpsConfig
from spec_ops.worker.preflight import (
    PipelineResult,
    PreflightPipeline,
    PreflightStage,
    StageResult,
    run_worktree_preflight,
)


def test_empty_pipeline():
    pipeline = PreflightPipeline(stages=[])
    res = pipeline.run()
    assert res.success is True
    assert res.failed_stage is None
    assert res.stage_results == []
    assert res.aborted_stages == []
    assert "passed" in res.summary.lower()


def test_add_stage():
    pipeline = PreflightPipeline()
    s = PreflightStage(name="lint", command="true")
    pipeline.add_stage(s)
    assert len(pipeline.stages) == 1
    assert pipeline.stages[0].name == "lint"


def test_pipeline_success_all_stages():
    s1 = PreflightStage(name="s1", command=f"{sys.executable} -c 'print(\"hello s1\")'")
    s2 = PreflightStage(name="s2", command=f"{sys.executable} -c 'print(\"hello s2\")'")
    pipeline = PreflightPipeline(stages=[s1, s2])
    res = pipeline.run()
    assert res.success is True
    assert len(res.stage_results) == 2
    assert res.stage_results[0].stage_name == "s1"
    assert res.stage_results[0].success is True
    assert res.stage_results[0].exit_code == 0
    assert "hello s1" in res.stage_results[0].output
    assert res.stage_results[1].stage_name == "s2"
    assert res.stage_results[1].success is True
    assert res.stage_results[1].exit_code == 0
    assert "hello s2" in res.stage_results[1].output
    assert res.failed_stage is None
    assert res.aborted_stages == []
    assert "summary" in res.logs.lower()
    assert "passed" in res.summary.lower()


def test_pipeline_fast_fail_first_stage():
    s1 = PreflightStage(name="s1", command=f"{sys.executable} -c 'import sys; sys.exit(7)'")
    s2 = PreflightStage(name="s2", command=f"{sys.executable} -c 'print(\"never reached\")'")
    pipeline = PreflightPipeline(stages=[s1, s2])
    res = pipeline.run()
    assert res.success is False
    assert len(res.stage_results) == 1
    assert res.failed_stage is not None
    assert res.failed_stage.stage_name == "s1"
    assert res.failed_stage.exit_code == 7
    assert res.failed_stage.success is False
    assert res.aborted_stages == ["s2"]
    assert "never reached" not in res.logs
    assert "Stage 1 ('s1') failed" in res.logs
    assert "code 7" in res.logs
    assert "aborted" in res.summary.lower()


def test_pipeline_timeout_handling():
    s1 = PreflightStage(
        name="slow",
        command=f"{sys.executable} -c 'import time; time.sleep(5)'",
        timeout_seconds=0.3,
    )
    pipeline = PreflightPipeline(stages=[s1])
    res = pipeline.run()
    assert res.success is False
    assert res.failed_stage is not None
    assert res.failed_stage.timeout is True
    assert res.failed_stage.exit_code == 124
    assert "timed out after 0.3s" in res.failed_stage.output


def test_pipeline_custom_environment():
    custom_env = {"MY_TEST_VAR": "SPEC_OPS_SECRET_123", "PATH": os.environ.get("PATH", "")}
    s1 = PreflightStage(
        name="env_check",
        command=f"{sys.executable} -c 'import os; print(os.environ.get(\"MY_TEST_VAR\", \"\"))'",
    )
    pipeline = PreflightPipeline(stages=[s1], env=custom_env)
    res = pipeline.run()
    assert res.success is True
    assert "SPEC_OPS_SECRET_123" in res.stage_results[0].output


def test_pipeline_from_config_explicit_stages(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    cfg.quality.stages = [
        {"name": "custom_lock", "command": "echo lock", "timeout_seconds": 15.0},
        {"name": "custom_test", "command": "echo test", "timeout_seconds": 25.0},
    ]
    pipeline = PreflightPipeline.from_config(cfg, cwd=tmp_path)
    assert len(pipeline.stages) == 2
    assert pipeline.stages[0].name == "custom_lock"
    assert pipeline.stages[0].timeout_seconds == 15.0
    assert pipeline.stages[1].name == "custom_test"


def test_pipeline_from_config_defaults(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    cfg.quality.preflight = ["pytest", "spec-ops health"]
    (tmp_path / "uv.lock").write_text("lockfile", encoding="utf-8")
    pipeline = PreflightPipeline.from_config(cfg, cwd=tmp_path)
    assert any(s.name == "lockfile" for s in pipeline.stages)
    assert any(s.name == "health" for s in pipeline.stages)
    assert any(s.name == "test" for s in pipeline.stages)


def test_pipeline_from_config_initial_skips_tests(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    cfg.quality.preflight = ["pytest", "spec-ops health"]
    (tmp_path / "uv.lock").write_text("lockfile", encoding="utf-8")
    pipeline = PreflightPipeline.from_config(cfg, cwd=tmp_path, initial=True)
    assert any(s.name == "lockfile" for s in pipeline.stages)
    assert any(s.name == "health" for s in pipeline.stages)
    assert not any(s.name == "test" for s in pipeline.stages)


def test_pipeline_sandbox_execution(tmp_path: Path):
    class DummySandbox:
        def run_preflight_suite(self, commands, cwd=None):
            return True, "sandbox executed commands cleanly"

    pipeline = PreflightPipeline(
        stages=[PreflightStage(name="sandboxed", command="uv run pytest")],
        cwd=tmp_path,
        sandbox=DummySandbox(),
    )
    res = pipeline.run()
    assert res.success is True
    assert res.stage_results[0].success is True
    assert "sandbox executed" in res.stage_results[0].output


def test_pipeline_exception_handling():
    s2 = PreflightStage(name="invalid_cmd", command="command_that_definitely_does_not_exist_xyz_123")
    pipeline = PreflightPipeline(stages=[s2])
    res = pipeline.run()
    assert res.success is False
    assert res.failed_stage is not None
    assert res.failed_stage.exit_code != 0


def test_pipeline_non_required_stage():
    s1 = PreflightStage(name="opt", command=f"{sys.executable} -c 'import sys; sys.exit(3)'", required=False)
    s2 = PreflightStage(name="req", command=f"{sys.executable} -c 'print(\"reached\")'", required=True)
    pipeline = PreflightPipeline(stages=[s1, s2])
    res = pipeline.run()
    assert res.success is True
    assert len(res.stage_results) == 2
    assert res.stage_results[0].success is False
    assert res.stage_results[1].success is True
    assert res.failed_stage is None
    assert "reached" in res.stage_results[1].output


def test_format_summary_and_logs_with_lockfile_failure():
    pipeline = PreflightPipeline()
    r1 = StageResult(stage_name="lockfile", command="uv lock --check", success=False, exit_code=1, output="lock mismatch")
    summary = pipeline.format_summary([r1], r1, ["health", "test"])
    logs = pipeline.format_logs([r1], r1, ["health", "test"])
    assert "lockfile" in summary
    assert "aborted 2 downstream stages" in summary
    assert "lockfile drift out-of-sync" in logs
    assert "subsequent stage(s): health, test" in logs


def test_pipeline_from_config_with_preflight_stage_objects(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    stage_obj = PreflightStage(name="direct", command="true", required=True, timeout_seconds=12.0)
    cfg.quality.stages = [stage_obj]
    pipeline = PreflightPipeline.from_config(cfg, cwd=tmp_path)
    assert len(pipeline.stages) == 1
    assert pipeline.stages[0].name == "direct"
    assert pipeline.stages[0].timeout_seconds == 12.0


def test_pipeline_from_config_security_active(tmp_path: Path):
    from spec_ops.config.models import SecuritySettings
    cfg = SpecOpsConfig(root_dir=tmp_path)
    cfg.security = SecuritySettings(secret_scanning=True)
    cfg.quality.preflight = ["pytest"]
    pipeline = PreflightPipeline.from_config(cfg, cwd=tmp_path)
    assert any(s.name == "security" for s in pipeline.stages)


def test_run_worktree_preflight_unauthorized_dependencies(tmp_path: Path):
    from spec_ops.core.models import Task
    (tmp_path / "pyproject.toml").write_text('[project]\nname="t"\ndependencies=["unauthorized"]\n', encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Modify pyproject.toml
    (tmp_path / "pyproject.toml").write_text('[project]\nname="t"\ndependencies=["unauthorized", "bad>=1.0"]\n', encoding="utf-8")
    cfg = SpecOpsConfig(root_dir=tmp_path)
    task = Task(id="0019", title="Test", allows_dependencies=False)
    ok, log = run_worktree_preflight(cfg, tmp_path, task=task)
    assert ok is False
    assert "Unauthorized Dependency Modification" in log

