"""Executable BDD scenarios for US-0106: Multi-Agent Collaborative Review Radar."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0106_review_radar.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


@pytest.fixture
def review_radar_bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "radar_repo"
    repo.mkdir()
    init_project(repo, name="RadarTestProject")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Baseline domain code
    domain_file = repo / "src" / "domain" / "service.py"
    domain_file.parent.mkdir(parents=True, exist_ok=True)
    domain_file.write_text("def compute_metrics(x: int) -> int:\n    return x * 2\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial baseline"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "cwd": repo, "res": None}


@given('an active worktree introducing an import from "infrastructure" into a pure "domain" module')
def setup_violating_worktree(review_radar_bdd_ctx: dict[str, Any]):
    repo: Path = review_radar_bdd_ctx["repo"]
    wt_dir = repo / ".worktrees" / "task-violating"
    wt_dir.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["git", "worktree", "add", "-b", "feat/violating-task", str(wt_dir)],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    violating_file = wt_dir / "src" / "domain" / "service.py"
    violating_file.write_text(
        "import infrastructure\n\n"
        "def compute_metrics(x: int) -> int:\n"
        "    infrastructure.send_telemetry(x)\n"
        "    return x * 2\n",
        encoding="utf-8",
    )
    review_radar_bdd_ctx["cwd"] = wt_dir


@given("a worktree modifying internal logic within a single bounded context without public API breaks")
def setup_compliant_worktree(review_radar_bdd_ctx: dict[str, Any]):
    repo: Path = review_radar_bdd_ctx["repo"]
    wt_dir = repo / ".worktrees" / "task-compliant"
    wt_dir.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["git", "worktree", "add", "-b", "feat/compliant-task", str(wt_dir)],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    clean_file = wt_dir / "src" / "domain" / "service.py"
    clean_file.write_text(
        "def _internal_helper(v: int) -> int:\n"
        "    return v + 1\n\n"
        "def compute_metrics(x: int) -> int:\n"
        "    return _internal_helper(x * 2)\n",
        encoding="utf-8",
    )
    review_radar_bdd_ctx["cwd"] = wt_dir


@when('the engineer runs "spec-ops review radar"')
def run_spec_ops_review_radar(review_radar_bdd_ctx: dict[str, Any]):
    cwd = review_radar_bdd_ctx["cwd"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "review", "radar"],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    review_radar_bdd_ctx["res"] = res


@then("an architectural boundary violation is reported citing ADR-0007")
def verify_violation_reported(review_radar_bdd_ctx: dict[str, Any]):
    res = review_radar_bdd_ctx["res"]
    combined = f"{res.stdout}\n{res.stderr}"
    assert "ADR-0007" in combined, f"ADR-0007 not cited in output:\n{combined}"
    assert "boundary violation" in combined.lower(), f"Boundary violation not flagged:\n{combined}"


@then("the review radar returns exit code 1")
def verify_exit_code_1(review_radar_bdd_ctx: dict[str, Any]):
    res = review_radar_bdd_ctx["res"]
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then("zero cross-context violations are reported")
def verify_zero_violations(review_radar_bdd_ctx: dict[str, Any]):
    res = review_radar_bdd_ctx["res"]
    combined = f"{res.stdout}\n{res.stderr}"
    assert "zero cross-context violations" in combined or "Violations: 0" in combined, (
        f"Expected zero violations in output:\n{combined}"
    )


@then("the radar returns exit code 0")
def verify_exit_code_0(review_radar_bdd_ctx: dict[str, Any]):
    res = review_radar_bdd_ctx["res"]
    assert res.returncode == 0, f"Expected returncode 0, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
