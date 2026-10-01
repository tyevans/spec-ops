"""BDD step definitions for US-0052: Team Delivery Velocity Engine and Cognitive Churn Heatmap."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0052_velocity_heatmap.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Invokes spec-ops CLI through public frontdoor entrypoint."""
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "velocity_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@specops.test"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="VelocityApp")

    # Author completed tasks
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)

    t1 = complete_dir / "0001-setup-engine.md"
    t1.write_text(
        "---\n"
        "id: '0001'\n"
        "title: Setup Core Engine\n"
        "status: Complete\n"
        "created: 2026-09-28\n"
        "completed: 2026-09-30\n"
        "target_bc: core\n"
        "---\n\n"
        "# TASK-0001\n",
        encoding="utf-8",
    )

    t2 = complete_dir / "0002-data-pipeline.md"
    t2.write_text(
        "---\n"
        "id: '0002'\n"
        "title: Build Data Pipeline\n"
        "status: Complete\n"
        "created: 2026-09-29\n"
        "completed: 2026-09-30\n"
        "target_bc: pipeline\n"
        "---\n\n"
        "# TASK-0002\n",
        encoding="utf-8",
    )

    # Commit files to create git log and numstat churn
    src_file = repo / "src" / "pipeline.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("# Initial pipeline\ndef run():\n    pass\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0001): initial setup"], cwd=repo, check=True, capture_output=True)

    # Second commit with modifications
    src_file.write_text("# Updated pipeline\ndef run():\n    print('executing')\n    return True\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/pipeline.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0002): pipeline execution"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "cli_result": None}


# Scenario 1 Steps


@given("a project repository with completed tasks and git commits")
def given_project_repo_with_tasks_and_commits(repo_context: dict[str, Any]):
    assert repo_context["repo"].exists()


@when('the engineering lead executes "spec-ops release velocity"')
def when_execute_release_velocity(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["release", "velocity"])
    repo_context["cli_result"] = res


@then("a delivery velocity report is generated")
def then_velocity_report_generated(repo_context: dict[str, Any]):
    res = repo_context["cli_result"]
    assert res.returncode == 0, f"Error: {res.stderr}"
    assert "# Team Delivery Velocity & Cognitive Churn Heatmap" in res.stdout


@then("displays task completion rates, lead time, and high-churn source files")
def then_displays_completion_rates_lead_time_churn(repo_context: dict[str, Any]):
    out = repo_context["cli_result"].stdout
    assert "Task Completion Rates" in out
    assert "Average Lead Time" in out
    assert "Cognitive Churn Heatmap" in out
    assert "src/pipeline.py" in out


# Scenario 2 Steps


@given("completed project delivery milestones")
def given_completed_project_delivery_milestones(repo_context: dict[str, Any]):
    assert repo_context["repo"].exists()


@when('the user runs "spec-ops release velocity --format html"')
def when_run_release_velocity_html(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["release", "velocity", "--format", "html"])
    repo_context["cli_result"] = res


@then("a standalone HTML heatmap report is generated")
def then_standalone_html_heatmap_generated(repo_context: dict[str, Any]):
    res = repo_context["cli_result"]
    assert res.returncode == 0, f"Error: {res.stderr}"
    assert "<!DOCTYPE html>" in res.stdout
    assert "<html" in res.stdout
    assert "</html>" in res.stdout
    assert "Team Delivery Velocity &amp; Cognitive Churn Heatmap" in res.stdout


@then("visualizes file modification churn without external CDN dependencies")
def then_visualizes_churn_without_cdn(repo_context: dict[str, Any]):
    out = repo_context["cli_result"].stdout
    # Zero external CDN / network dependencies
    assert "http://" not in out
    assert "https://" not in out
    assert "src/pipeline.py" in out
    assert "Cognitive Churn Heatmap" in out
