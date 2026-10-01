"""Executable BDD acceptance tests for US-0017: Modularity Debt Scoring and Source File Growth Proactive Telemetry."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0017_modularity_debt.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "modularity_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="ModularityDemoApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "result": None}


# Scenario 1: Computing modularity debt scores across project modules
@given("a project repository with source files of varying lengths")
def given_project_repo_varying_lengths(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    src_dir = repo / "src" / "demo"
    src_dir.mkdir(parents=True, exist_ok=True)

    # 1. Small file (50 lines)
    (src_dir / "small_module.py").write_text(
        "\n".join(f"# small comment line {i}" for i in range(50)) + "\n",
        encoding="utf-8",
    )

    # 2. Moderate file (220 lines)
    (src_dir / "moderate_module.py").write_text(
        "\n".join(f"# moderate comment line {i}" for i in range(220)) + "\n",
        encoding="utf-8",
    )

    # 3. Danger zone file approaching 400 lines (380 lines)
    danger_code = ["import os", "import sys"] + [f"def func_{i}(): pass" for i in range(378)]
    (src_dir / "danger_module.py").write_text(
        "\n".join(danger_code) + "\n",
        encoding="utf-8",
    )


@when('the engineer runs "spec-ops health --modularity"')
def when_engineer_runs_health_modularity(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["health", "--modularity"])
    repo_context["result"] = res


@then("a modularity debt report is displayed")
def then_modularity_debt_report_displayed(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res.returncode == 0, f"Expected returncode 0, got {res.returncode}. stderr: {res.stderr}"
    assert "Modularity Debt Report" in res.stdout
    assert "Overall Modularity Debt Score:" in res.stdout


@then("files approaching 400 lines are flagged with proactive decomposition warnings")
def then_files_approaching_400_flagged(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert "danger_module.py" in res.stdout
    assert "Proactive decomposition warning" in res.stdout or "proactive decomposition" in res.stdout.lower()


# Scenario 2: Structured JSON modularity telemetry export
@given("active codebase files analyzed for modularity health")
def given_active_codebase_files(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    src_dir = repo / "src" / "demo"
    src_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "core_service.py").write_text(
        "import os\n" + "\n".join(f"def action_{i}(): pass" for i in range(120)) + "\n",
        encoding="utf-8",
    )
    (src_dir / "danger_service.py").write_text(
        "import sys\n" + "\n".join(f"def handler_{i}(): pass" for i in range(375)) + "\n",
        encoding="utf-8",
    )


@when('the user executes "spec-ops health --modularity --json"')
def when_user_executes_health_modularity_json(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["health", "--modularity", "--json"])
    repo_context["result"] = res


@then("a valid JSON payload containing per-file risk scores and line counts is emitted")
def then_valid_json_payload_emitted(repo_context: dict[str, Any]):
    res = repo_context["result"]
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Emitted stdout is not valid JSON: {exc}\nStdout:\n{res.stdout}")

    assert "overall_debt_score" in data
    assert "files" in data
    assert isinstance(data["files"], list)
    assert len(data["files"]) > 0

    found_danger = False
    for file_entry in data["files"]:
        assert "file_path" in file_entry
        assert "line_count" in file_entry
        assert "risk_score" in file_entry
        assert "risk_level" in file_entry
        assert "recommended_action" in file_entry
        assert 0.0 <= file_entry["risk_score"] <= 100.0
        if "danger_service.py" in file_entry["file_path"]:
            found_danger = True
            assert file_entry["line_count"] >= 350
            assert file_entry["risk_level"] in ("high", "critical")

    assert found_danger, "Expected danger_service.py to be analyzed in JSON payload"


@then("returns exit code 0")
def then_returns_exit_code_zero(repo_context: dict[str, Any]):
    res = repo_context["result"]
    assert res.returncode == 0, f"Expected 0, got {res.returncode}. Stderr: {res.stderr}"
