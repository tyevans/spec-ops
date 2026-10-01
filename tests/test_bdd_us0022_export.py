"""BDD step definitions for US-0022: Hybrid Team Velocity and Executive Forecast Exporter."""

from __future__ import annotations

import io
import shlex
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config

scenarios("features/us_0022_velocity_export.feature")


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


@then("a standalone, zero-dependency HTML dashboard is generated with interactive charts and throughput forecasts.")
def verify_html_dashboard_generated(repo_env: dict[str, Any]):
    repo = repo_env["repo"]
    out_file = repo / "dist" / "velocity-report.html"
    assert out_file.exists(), f"Expected HTML report at {out_file}"
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<svg" in content
    assert "Hybrid Delivery Velocity" in content
    assert "Throughput Breakdown" in content
    assert "Milestone Delivery Forecast" in content


@then("the HTML artifact operates entirely offline without external CDN script references.")
def verify_offline_html_artifact(repo_env: dict[str, Any]):
    repo = repo_env["repo"]
    out_file = repo / "dist" / "velocity-report.html"
    content = out_file.read_text(encoding="utf-8")
    assert "<script" not in content, "HTML report should contain zero <script> tags"
    assert "http://" not in content, "HTML report should contain zero external HTTP URLs"
    assert "https://" not in content, "HTML report should contain zero external HTTPS URLs"
    assert "<link rel=\"stylesheet\"" not in content, "HTML report should contain zero external stylesheets"


@then(parsers.parse('a standalone, zero-dependency HTML dashboard is generated at "{target_path}"'))
def verify_html_dashboard_at_path(repo_env: dict[str, Any], target_path: str):
    repo = repo_env["repo"]
    out_file = repo / target_path
    assert out_file.exists(), f"Expected HTML report at {out_file}"
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<svg" in content
    assert "Hybrid Delivery Velocity" in content
