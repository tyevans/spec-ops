"""Frontdoor blackbox CLI tests for 'spec-ops worker --telemetry' (TASK-0070, US-0104)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from spec_ops.cli.main import main
from spec_ops.scaffold.init import init_project


def test_cli_worker_telemetry_json_output(tmp_path: Path, capsys, monkeypatch):
    """Verify that 'spec-ops worker --telemetry --json' outputs structured JSON."""
    init_project(tmp_path, name="CliTelemProject")
    monkeypatch.chdir(tmp_path)

    # Create worktree
    wt = tmp_path / ".worktrees" / "task-0021"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".specops").mkdir(parents=True, exist_ok=True)
    (wt / ".specops" / "worker.json").write_text(
        json.dumps({
            "task_id": "TASK-0021",
            "title": "Build AST parser seam",
            "branch": "feat/task-0021",
            "status": "Self-Healing",
            "attempt": "2/3",
            "active_preflight_check": "spec-ops health",
            "elapsed_seconds": 180,
            "memory_mb": 256.0,
            "cpu_percent": 24.5,
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["spec-ops", "worker", "--telemetry", "--json"])
    exit_code = main()
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["total"] == 1
    assert data["active"] == 1
    assert data["stalled"] == 0
    assert data["partition_valid"] is True
    assert data["total_memory_mb"] == 256.0
    rec = data["records"][0]
    assert rec["task_id"] == "TASK-0021"
    assert rec["status"] == "Self-Healing"
    assert rec["rescue_cmd"] == "spec-ops rescue TASK-0021"


def test_cli_worker_telemetry_table_output(tmp_path: Path, capsys, monkeypatch):
    """Verify that 'spec-ops worker --telemetry' outputs formatted table with alerts."""
    init_project(tmp_path, name="CliTelemTableProject")
    monkeypatch.chdir(tmp_path)

    # Create stalled worktree
    wt = tmp_path / ".worktrees" / "task-0022"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".specops").mkdir(parents=True, exist_ok=True)
    (wt / ".specops" / "worker.json").write_text(
        json.dumps({
            "task_id": "TASK-0022",
            "title": "Prune stale worktree",
            "branch": "feat/task-0022",
            "status": "Stalled",
            "attempt": "3/3",
            "stalled": True,
            "failure_log": "Preflight error",
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["spec-ops", "worker", "--telemetry"])
    exit_code = main()
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "SpecOps Worker Fleet Telemetry" in captured.out
    assert "TASK-0022" in captured.out
    assert "Stalled: Human Takeover Required" in captured.out
    assert "spec-ops rescue TASK-0022" in captured.out
    assert "Total: 1" in captured.out
    assert "Stalled: 1" in captured.out
    assert "Alert: 1 worker(s) stalled" in captured.out
