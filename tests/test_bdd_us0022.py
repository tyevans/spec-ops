"""BDD step definitions for US-0022: Hybrid Team Velocity and Autonomous Agent Rescue Analytics."""

from __future__ import annotations

import io
import json
import shlex
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.rescue.memory import append_failure_record

scenarios("features/us_0022_hybrid_velocity_rescue_analytics.feature")


@pytest.fixture
def repo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialize minimal git repository
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)

    # Backlog structure
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"
    complete_dir = backlog_dir / "complete"
    refined_dir.mkdir(parents=True)
    proposed_dir.mkdir(parents=True)
    complete_dir.mkdir(parents=True)

    # Initial commit so HEAD exists
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    (repo / "specops.toml").write_text("[project]\nname = 'TestRepo'\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    monkeypatch.chdir(repo)
    cfg = load_config(repo)
    return {"repo": repo, "backlog_dir": backlog_dir, "config": cfg, "stdout": ""}


@given("a project with completed tasks delivered across multiple sprints or milestones")
def setup_completed_tasks(repo_env: dict[str, Any]):
    repo = repo_env["repo"]
    complete_dir = repo_env["backlog_dir"] / "complete"

    t1_content = """---
id: '0001'
title: Autonomous Core Feature
status: Complete
claimed_at: '2026-09-30T10:00:00Z'
completed_at: '2026-09-30T10:05:00Z'
---
# TASK-0001
"""
    (complete_dir / "0001-auto-feat.md").write_text(t1_content, encoding="utf-8")

    t2_content = """---
id: '0002'
title: Human Architecture Refactor
status: Complete
claimed_at: '2026-09-30T08:00:00Z'
completed_at: '2026-09-30T12:00:00Z'
---
# TASK-0002
"""
    (complete_dir / "0002-human-refactor.md").write_text(t2_content, encoding="utf-8")

    # Commit 1: Agent worker
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    msg_agent = "feat(0001): autonomous feature\n\nSpecOps-Task: TASK-0001\nSpecOps-Worker: auto-worker-1\nProvenance: autonomous\nVerification: pass\n"
    subprocess.run(["git", "commit", "-m", msg_agent], cwd=repo, check=True, capture_output=True)

    # Commit 2: Human developer
    (repo / "human_change.txt").write_text("done\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    msg_human = "refactor(0002): human refactoring\n\nSpecOps-Task: TASK-0002\n"
    subprocess.run(["git", "commit", "-m", msg_human], cwd=repo, check=True, capture_output=True)


@given('multiple autonomous worker runs required human rescue via "spec-ops rescue"')
def setup_rescued_tasks(repo_env: dict[str, Any]):
    setup_completed_tasks(repo_env)
    backlog_dir = repo_env["backlog_dir"]
    t1_path = backlog_dir / "complete" / "0001-auto-feat.md"

    # Add failure records to t1
    append_failure_record(
        t1_path,
        reason="Preflight test verification failed due to pytest assertion error under ADR-0004",
        failed_invariants=["ADR-0004"],
        attempt_date="2026-09-30",
    )
    append_failure_record(
        t1_path,
        reason="Source file length exceeded 500 lines violating ADR-0002",
        failed_invariants=["ADR-0002"],
        attempt_date="2026-09-30",
    )


@when(parsers.parse('the lead runs "{cmd}"'))
def run_cli_command(repo_env: dict[str, Any], cmd: str):
    tokens = shlex.split(cmd)
    if tokens[0] == "spec-ops":
        tokens = tokens[1:]

    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            main(tokens)
        except SystemExit as exc:
            assert exc.code == 0 or exc.code is None

    repo_env["stdout"] = buf.getvalue()


@then("the system calculates and prints hybrid delivery KPIs:")
def verify_hybrid_kpi_table(repo_env: dict[str, Any]):
    out = repo_env["stdout"]
    assert "Hybrid Delivery Velocity" in out
    assert "Agent Workers" in out
    assert "Human Developers" in out
    assert "Hybrid Total" in out
    assert "Tasks Delivered" in out
    assert "Average Task Cycle Time" in out


@then(parsers.parse('saves a structured historical snapshot to "{snapshot_path}".'))
def verify_snapshot_saved(repo_env: dict[str, Any], snapshot_path: str):
    repo = repo_env["repo"]
    clean_path = snapshot_path.removeprefix("./")
    target = repo / clean_path
    assert target.exists(), f"Expected snapshot file at {target}"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "metrics" in data
    assert "agent_workers" in data["metrics"]
    assert "human_developers" in data["metrics"]
    assert "hybrid_total" in data["metrics"]


@then("the report identifies recurring failure clusters and computes rescue burden telemetry")
def verify_failure_clusters_and_burden(repo_env: dict[str, Any]):
    out = repo_env["stdout"]
    assert "Autonomous Agent Rescue & Failure Telemetry" in out
    assert "Rescue Burden Ratio" in out
    assert "Mean Time to Unblock" in out


@then("lists the top failure reasons including preflight test failures and file length violations.")
def verify_top_failure_reasons(repo_env: dict[str, Any]):
    out = repo_env["stdout"]
    assert "Preflight Test Failures" in out
    assert "File Length Violations" in out
    assert "ADR-0004" in out or "ADR-0002" in out


@then("the command outputs valid JSON containing contributor velocity and throughput metrics.")
def verify_valid_json_output(repo_env: dict[str, Any]):
    out = repo_env["stdout"].strip()
    data = json.loads(out)
    assert "metrics" in data
    assert "window" in data
    assert data["metrics"]["hybrid_total"]["tasks_delivered"] >= 1
