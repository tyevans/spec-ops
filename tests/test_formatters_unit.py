"""Unit tests for CLI JSON formatters to maximize mutmut kill rate."""

from __future__ import annotations

import json
from pathlib import Path

from spec_ops.backlog.health import FileLengthViolation, FileLengthWarning, HealthCheckReport
from spec_ops.cli.formatters import format_health_json, format_profiles_info_json, format_task_json
from spec_ops.config.models import ArchitectureSettings, ExecutionSettings, QualitySettings, SecuritySettings, SpecOpsConfig
from spec_ops.core.models import Task


def test_format_task_json_none():
    res = format_task_json(None)
    data = json.loads(res)
    assert data["status"] == "empty"
    assert data["task"] is None
    assert "No ready" in data["message"]


def test_format_task_json_populated():
    t = Task(
        id="0014",
        title="Pluggable Runners",
        status="Refined",
        target_bc="worker",
        target_release="v1.0",
        dependencies=["TASK-0001", "TASK-0002"],
        governing_adrs=["ADR-0001", "ADR-0002"],
        governing_prds=["PRD-0004"],
        governing_stories=["US-0080"],
        priority_rank=42,
        allows_dependencies=True,
    )
    cfg = SpecOpsConfig(
        execution=ExecutionSettings(git_branch_prefix="task/"),
        architecture=ArchitectureSettings(file_length_limit=450),
        quality=QualitySettings(preflight=["pytest -v", "ruff check"], testing_style="blackbox"),
    )
    res = format_task_json(t, cfg)
    data = json.loads(res)

    assert data["id"] == "0014"
    assert data["canonical_id"] == "TASK-0014"
    assert data["title"] == "Pluggable Runners"
    assert data["status"] == "Refined"
    assert data["target_bc"] == "worker"
    assert data["target_release"] == "v1.0"
    assert data["branch_name"] == "task/task-0014"
    assert data["branch"] == "task/task-0014"
    assert data["dependencies"] == ["TASK-0001", "TASK-0002"]
    assert data["governing_adrs"] == ["ADR-0001", "ADR-0002"]
    assert data["governing_prds"] == ["PRD-0004"]
    assert data["governing_stories"] == ["US-0080"]
    assert data["priority_rank"] == 42

    meta = data["prompt_metadata"]
    assert meta["preflight"] == ["pytest -v", "ruff check"]
    assert meta["allows_dependencies"] is True
    assert meta["file_length_limit"] == 450
    assert meta["testing_style"] == "blackbox"


def test_format_task_json_default_config():
    t = Task(id="0005", title="Default Config Task", branch="custom/branch")
    res = format_task_json(t)
    data = json.loads(res)

    assert data["branch_name"] == "custom/branch"
    assert data["prompt_metadata"]["file_length_limit"] == 500
    assert data["prompt_metadata"]["preflight"] == ["pytest"]


def test_format_health_json_healthy():
    report = HealthCheckReport(
        violations=[],
        warnings=[],
        priority_sync_ok=True,
        sync_errors=[],
        completed_tasks=5,
        refined_tasks=10,
        proposed_tasks=2,
        buffer_status="OPTIMAL",
    )
    res = format_health_json(report)
    data = json.loads(res)

    assert data["status"] == "ok"
    assert data["healthy"] is True
    assert data["violations"] == []
    assert data["violation_count"] == 0
    assert data["warnings"] == []
    assert data["warning_count"] == 0
    assert data["priority_sync"]["ok"] is True
    assert data["priority_sync"]["mismatched_tasks"] == []
    assert data["backlog"]["completed_tasks"] == 5
    assert data["backlog"]["buffer_status"] == "OPTIMAL"


def test_format_health_json_unhealthy():
    v = FileLengthViolation(path=Path("src/big.py"), lines=550, limit=500)
    w = FileLengthWarning(path=Path("src/warn.py"), lines=450, threshold=400, limit=500)
    report = HealthCheckReport(
        violations=[v],
        warnings=[w],
        priority_sync_ok=False,
        sync_errors=[
            "TASK-0010 is in proposed/ on disk but referenced as refined/ in PRIORITY.md",
            "SPIKE-0002 is in complete/ on disk but referenced as proposed/ in PRIORITY.md",
        ],
        constitution_drift_warnings=["AGENTS.md is missing"],
        completed_tasks=3,
        refined_tasks=2,
        proposed_tasks=1,
        buffer_status="UNDER_BUFFERED",
    )
    res = format_health_json(report)
    data = json.loads(res)

    assert data["status"] == "error"
    assert data["healthy"] is False
    assert data["violation_count"] == 1
    assert data["violations"][0]["rule"] == "ADR-0002"
    assert data["violations"][0]["lines"] == 550
    assert data["warning_count"] == 1
    assert data["warnings"][0]["threshold"] == 400
    assert data["warnings"][0]["rule"] == "ADR-0002"
    assert data["priority_sync"]["ok"] is False
    assert "TASK-0010" in data["priority_sync"]["mismatched_tasks"]
    assert "SPIKE-0002" in data["priority_sync"]["mismatched_tasks"]
    assert "AGENTS.md is missing" in data["constitution_warnings"]


def test_format_profiles_info_json():
    cfg = SpecOpsConfig(
        quality=QualitySettings(require_bdd=True, preflight=["pytest", "spec-ops health"]),
        security=SecuritySettings(),
    )
    res = format_profiles_info_json(cfg)
    data = json.loads(res)

    assert "core" in data["active_profiles"]
    assert "bdd" in data["active_profiles"]
    assert "ddd" in data["active_profiles"]
    assert "security" in data["active_profiles"]

    invariants = data["invariants"]
    rule_names = {inv["name"] for inv in invariants}
    assert "file_length_limit" in rule_names
    assert "blackbox_verification" in rule_names
    assert "backlog_isolation" in rule_names
    assert "diataxis_documentation" in rule_names
    assert "property_mutation_testing" in rule_names
    assert "dependency_immutability" in rule_names

    assert data["preflight"]["commands"] == ["pytest", "spec-ops health"]
    assert data["preflight"]["chain"] == "uv run pytest && uv run spec-ops health"

    entrypoints = data["cli_entrypoints"]
    assert "queue_next" in entrypoints
    assert "worker_dry_run" in entrypoints
    assert "health_check" in entrypoints
    assert "profiles_info" in entrypoints


def test_format_profiles_info_json_no_bdd_no_sec(tmp_path: Path):
    cfg = SpecOpsConfig(
        quality=QualitySettings(require_bdd=False, preflight=[]),
        security=None,
        root_dir=tmp_path,
    )
    res = format_profiles_info_json(cfg)
    data = json.loads(res)

    assert "core" in data["active_profiles"]
    assert "bdd" not in data["active_profiles"]
    assert "security" not in data["active_profiles"]
    assert data["preflight"]["commands"] == ["pytest"]
