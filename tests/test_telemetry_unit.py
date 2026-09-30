"""Unit tests for telemetry_script.py to maximize mutant kill rate under mutmut (TASK-0070)."""

from __future__ import annotations

import json
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.telemetry_script import (
    WorkerTelemetryRecord,
    aggregate_fleet_telemetry,
    classify_worker_status,
    format_cpu_percent,
    format_elapsed_runtime,
    format_memory_mb,
    harvest_fleet_telemetry,
)


def test_classify_worker_status_completed():
    assert classify_worker_status({"completed": True}) == "completed"
    assert classify_worker_status({"status": "Complete"}) == "completed"
    assert classify_worker_status({"status": "completed"}) == "completed"
    assert classify_worker_status({"status": "Done"}) == "completed"
    assert classify_worker_status({"status": "shipped"}) == "completed"
    # Precedence: completed takes precedence over stalled/rescued
    assert classify_worker_status({"completed": True, "stalled": True, "rescued": True}) == "completed"


def test_classify_worker_status_rescued():
    assert classify_worker_status({"rescued": True}) == "rescued"
    assert classify_worker_status({"status": "Rescued"}) == "rescued"
    assert classify_worker_status({"status": "rescue_in_progress"}) == "rescued"
    assert classify_worker_status({"status": "human_takeover"}) == "rescued"
    assert classify_worker_status({"status": "taken_over"}) == "rescued"
    # Precedence: rescued takes precedence over stalled
    assert classify_worker_status({"rescued": True, "stalled": True}) == "rescued"


def test_classify_worker_status_stalled():
    assert classify_worker_status({"stalled": True}) == "stalled"
    assert classify_worker_status({"status": "Stalled"}) == "stalled"
    assert classify_worker_status({"status": "Stalled: Human Takeover Required"}) == "stalled"
    assert classify_worker_status({"status": "Failed"}) == "stalled"
    assert classify_worker_status({"status": "deadlocked"}) == "stalled"
    assert classify_worker_status({"attempt": "3/3"}) == "stalled"
    assert classify_worker_status({"retries": "3/3"}) == "stalled"


def test_classify_worker_status_active():
    assert classify_worker_status({"status": "Running"}) == "active"
    assert classify_worker_status({"status": "Executing"}) == "active"
    assert classify_worker_status({"status": "Self-Healing"}) == "active"
    assert classify_worker_status({}) == "active"
    assert classify_worker_status({"attempt": "1/3", "retries": "1/3"}) == "active"


def test_aggregate_fleet_telemetry_empty():
    res = aggregate_fleet_telemetry([])
    assert res["total"] == 0
    assert res["active"] == 0
    assert res["stalled"] == 0
    assert res["rescued"] == 0
    assert res["completed"] == 0
    assert res["partition_valid"] is True
    assert res["stalled_tasks"] == []
    assert res["total_memory_mb"] == 0.0
    assert res["avg_cpu_percent"] == 0.0
    assert res["records"] == []


def test_aggregate_fleet_telemetry_mixed():
    records = [
        {"task_id": "TASK-0001", "status": "Running", "memory_mb": 100.0, "cpu_percent": 10.0},
        {"task_id": "TASK-0002", "stalled": True, "memory_mb": 200.0, "cpu_percent": 20.0},
        {"task_id": "TASK-0003", "rescued": True, "memory_mb": 50.0, "cpu_percent": 0.0},
        {"task_id": "TASK-0004", "status": "Complete", "memory_mb": 0.0, "cpu_percent": 0.0},
        {"id": "TASK-0005", "attempt": "3/3", "memory_mb": None, "cpu_percent": None},
    ]
    res = aggregate_fleet_telemetry(records)
    assert res["total"] == 5
    assert res["active"] == 1
    assert res["stalled"] == 2
    assert res["rescued"] == 1
    assert res["completed"] == 1
    assert res["partition_valid"] is True
    assert res["stalled_tasks"] == ["TASK-0002", "TASK-0005"]
    assert res["total_memory_mb"] == 350.0
    assert res["avg_cpu_percent"] == 6.0  # (10 + 20) / 5


def test_formatting_helpers():
    # format_elapsed_runtime
    assert format_elapsed_runtime(None) == "0s"
    assert format_elapsed_runtime(-5) == "0s"
    assert format_elapsed_runtime(0) == "0s"
    assert format_elapsed_runtime(45) == "45s"
    assert format_elapsed_runtime(60) == "1m 0s"
    assert format_elapsed_runtime(125) == "2m 5s"

    # format_memory_mb
    assert format_memory_mb(None) == "0 MB"
    assert format_memory_mb(-1) == "0 MB"
    assert format_memory_mb(0) == "0 MB"
    assert format_memory_mb(256.4) == "256.4 MB"
    assert format_memory_mb(1024) == "1.0 GB"
    assert format_memory_mb(2048.5) == "2.0 GB"

    # format_cpu_percent
    assert format_cpu_percent(None) == "0.0%"
    assert format_cpu_percent(-1.0) == "0.0%"
    assert format_cpu_percent(0.0) == "0.0%"
    assert format_cpu_percent(15.75) == "15.8%"


def test_worker_telemetry_record_to_dict():
    rec = WorkerTelemetryRecord(
        task_id="TASK-0042",
        worktree_path=".worktrees/task-0042",
        branch="feat/task-0042",
        status="Executing",
        retries="1/3",
        current_preflight_hook="uv run pytest",
        elapsed_runtime="2m 30s",
        memory_usage="150 MB",
        cpu_usage="5.0%",
        stalled=False,
    )
    d = rec.to_dict()
    assert d["task_id"] == "TASK-0042"
    assert d["id"] == "TASK-0042"
    assert d["worktree_path"] == ".worktrees/task-0042"
    assert d["rescue_cmd"] == "spec-ops rescue TASK-0042"
    assert d["attempt"] == "1/3"
    assert d["active_preflight_check"] == "uv run pytest"


def test_harvest_fleet_telemetry_no_worktrees(tmp_path: Path):
    init_project(tmp_path, name="NoWorktreesProject")
    config = load_config(root_dir=tmp_path)
    res = harvest_fleet_telemetry(config)
    assert res == []


def test_harvest_fleet_telemetry_with_worktrees(tmp_path: Path):
    init_project(tmp_path, name="WorktreesProject")
    config = load_config(root_dir=tmp_path)

    wt_dir = tmp_path / ".worktrees"
    wt_dir.mkdir(parents=True, exist_ok=True)

    # 1. Non-directory file
    (wt_dir / "random.txt").write_text("ignore", encoding="utf-8")

    # 2. Non-task directory
    (wt_dir / "other-dir").mkdir()

    # 3. task-0010 with .specops/worker.json
    wt1 = wt_dir / "task-0010"
    (wt1 / ".specops").mkdir(parents=True, exist_ok=True)
    (wt1 / ".specops" / "worker.json").write_text(
        json.dumps({
            "status": "Self-Healing",
            "attempt": "2/3",
            "active_preflight_check": "spec-ops health",
            "stalled": False,
            "title": "Custom Task 10",
            "memory_mb": 256.0,
            "cpu_percent": 18.0,
            "elapsed_seconds": 120.0,
        }),
        encoding="utf-8",
    )

    # 4. task-0011 with .telemetry.json
    wt2 = wt_dir / "task-0011"
    wt2.mkdir(parents=True, exist_ok=True)
    (wt2 / ".telemetry.json").write_text(
        json.dumps({
            "status": "Stalled",
            "retries": "3/3",
            "stalled": True,
            "failure_log": "Invariant check failed",
            "memory_mb": 512.0,
        }),
        encoding="utf-8",
    )

    # 5. task-0012 with .task-prompt.md
    wt3 = wt_dir / "task-0012"
    wt3.mkdir(parents=True, exist_ok=True)
    (wt3 / ".task-prompt.md").write_text(
        "Working on TASK-0012 (Attempt 3)\nfile limit violation\n## Preflight Failure Feedback\nFile exceeds 500 lines",
        encoding="utf-8",
    )

    telemetry = harvest_fleet_telemetry(config)
    assert len(telemetry) == 3

    t10 = next(t for t in telemetry if t["task_id"] == "TASK-0010")
    assert t10["status"] == "Self-Healing"
    assert t10["attempt"] == "2/3"
    assert t10["memory_usage"] == "256.0 MB"
    assert t10["title"] == "Custom Task 10"

    t11 = next(t for t in telemetry if t["task_id"] == "TASK-0011")
    assert t11["stalled"] is True
    assert t11["status"] == "Stalled: Human Takeover Required"
    assert t11["failure_log"] == "Invariant check failed"

    t12 = next(t for t in telemetry if t["task_id"] == "TASK-0012")
    assert t12["stalled"] is True
    assert t12["status"] == "Stalled: Human Takeover Required"
    assert "File exceeds 500 lines" in t12["failure_log"]
    assert t12["active_preflight_check"] == "Fixing file limit"
