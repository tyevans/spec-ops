"""Executable BDD acceptance tests for US-0077: Milestone Scope Transition and Rollover Engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0006, ADR-0007, ADR-0009; PRD-0005; US-0077.
Target Bounded Context: backlog. Frontdoor blackbox verification without private mocks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.core.migration import parse_frontmatter_and_body
from spec_ops.scaffold.init import init_project

scenarios("features/us_0077_milestone_rollover.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops_cmd(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Frontdoor CLI invoker via subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def rollover_repo(tmp_path: Path) -> Path:
    """Sets up a realistic test workspace with completed and uncompleted tasks across milestones."""
    repo = tmp_path / "rollover_workspace"
    init_project(repo, name="MilestoneRolloverTest")
    backlog_dir = repo / "docs" / "project" / "backlog"
    complete_dir = backlog_dir / "complete"
    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"

    complete_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)
    proposed_dir.mkdir(parents=True, exist_ok=True)

    # 1. Completed task in complete/ (assigned to M1)
    (complete_dir / "0001-initial-architecture.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Initial Architecture Spike\n"
        "status: Complete\n"
        "target_release: M1\n"
        "target_bc: backlog\n"
        "---\n\n"
        "# TASK-0001: Initial Architecture Spike\n"
        "Body content for completed task.\n",
        encoding="utf-8",
    )

    # 2. Unfinished task in refined/ (assigned to M1 via target_release)
    (refined_dir / "0002-unfinished-refined.md").write_text(
        "---\n"
        "id: '0002'\n"
        "title: Unfinished Refined Feature\n"
        "status: Refined\n"
        "target_release: M1\n"
        "target_bc: backlog\n"
        "---\n\n"
        "# TASK-0002: Unfinished Refined Feature\n"
        "Body content for refined task.\n",
        encoding="utf-8",
    )

    # 3. Unfinished task in proposed/ (assigned to M1 via milestone tag)
    (proposed_dir / "0003-unfinished-proposed.md").write_text(
        "---\n"
        "id: '0003'\n"
        "title: Unfinished Proposed Feature\n"
        "status: Proposed\n"
        "milestone: M1\n"
        "target_bc: backlog\n"
        "---\n\n"
        "# TASK-0003: Unfinished Proposed Feature\n"
        "Body content for proposed task.\n",
        encoding="utf-8",
    )

    # 4. Other milestone task in proposed/ (assigned to M3, must NOT be modified)
    (proposed_dir / "0004-other-milestone.md").write_text(
        "---\n"
        "id: '0004'\n"
        "title: Future Scope Feature\n"
        "status: Proposed\n"
        "target_release: M3\n"
        "target_bc: backlog\n"
        "---\n\n"
        "# TASK-0004: Future Scope Feature\n"
        "Body content for future milestone task.\n",
        encoding="utf-8",
    )

    return repo


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


@given('a repository with completed tasks in "complete/" and unfinished tasks in "refined/" and "proposed/" assigned to milestone "M1"')
def setup_milestone_repo(rollover_repo: Path, context: dict[str, Any]) -> None:
    context["repo"] = rollover_repo
    context["complete_file"] = rollover_repo / "docs" / "project" / "backlog" / "complete" / "0001-initial-architecture.md"
    context["refined_file"] = rollover_repo / "docs" / "project" / "backlog" / "refined" / "0002-unfinished-refined.md"
    context["proposed_file"] = rollover_repo / "docs" / "project" / "backlog" / "proposed" / "0003-unfinished-proposed.md"
    context["other_file"] = rollover_repo / "docs" / "project" / "backlog" / "proposed" / "0004-other-milestone.md"

    context["initial_complete_content"] = context["complete_file"].read_text(encoding="utf-8")
    context["initial_refined_content"] = context["refined_file"].read_text(encoding="utf-8")
    context["initial_proposed_content"] = context["proposed_file"].read_text(encoding="utf-8")
    context["initial_other_content"] = context["other_file"].read_text(encoding="utf-8")


@when('the lead runs "spec-ops milestone rollover --from M1 --to M2"')
def run_rollover_standard(context: dict[str, Any]) -> None:
    res = run_spec_ops_cmd(context["repo"], ["milestone", "rollover", "--from", "M1", "--to", "M2"])
    context["last_result"] = res


@when('the lead runs "spec-ops milestone rollover --from M1 --to M2 --dry-run"')
def run_rollover_dry_run(context: dict[str, Any]) -> None:
    res = run_spec_ops_cmd(context["repo"], ["milestone", "rollover", "--from", "M1", "--to", "M2", "--dry-run"])
    context["last_result"] = res


@when('the lead runs "spec-ops milestone rollover --from M1 --to M2 --json"')
def run_rollover_json(context: dict[str, Any]) -> None:
    res = run_spec_ops_cmd(context["repo"], ["milestone", "rollover", "--from", "M1", "--to", "M2", "--json"])
    context["last_result"] = res


@then('unfinished tasks are reassigned to milestone "M2"')
def verify_tasks_reassigned(context: dict[str, Any]) -> None:
    res = context["last_result"]
    assert res.returncode == 0, f"Command failed with {res.stderr}"

    refined_meta, _, _ = parse_frontmatter_and_body(context["refined_file"].read_text(encoding="utf-8"))
    assert refined_meta.get("target_release") == "M2"

    proposed_meta, _, _ = parse_frontmatter_and_body(context["proposed_file"].read_text(encoding="utf-8"))
    assert proposed_meta.get("milestone") == "M2"

    other_meta, _, _ = parse_frontmatter_and_body(context["other_file"].read_text(encoding="utf-8"))
    assert other_meta.get("target_release") == "M3"


@then("milestone tags in frontmatter are atomically updated")
def verify_frontmatter_tags_updated(context: dict[str, Any]) -> None:
    content_refined = context["refined_file"].read_text(encoding="utf-8")
    assert "target_release: M2" in content_refined
    assert "# TASK-0002: Unfinished Refined Feature" in content_refined

    content_proposed = context["proposed_file"].read_text(encoding="utf-8")
    assert "milestone: M2" in content_proposed
    assert "# TASK-0003: Unfinished Proposed Feature" in content_proposed


@then('completed tasks in "complete/" remain untouched.')
def verify_completed_tasks_untouched(context: dict[str, Any]) -> None:
    current_complete_content = context["complete_file"].read_text(encoding="utf-8")
    assert current_complete_content == context["initial_complete_content"], "Complete task was modified!"

    complete_meta, _, _ = parse_frontmatter_and_body(current_complete_content)
    assert complete_meta.get("target_release") == "M1"


@then("candidate tasks are listed in the output")
def verify_dry_run_output(context: dict[str, Any]) -> None:
    res = context["last_result"]
    assert res.returncode == 0
    assert "=== Milestone Rollover (Dry Run) ===" in res.stdout
    assert "TASK-0002" in res.stdout
    assert "TASK-0003" in res.stdout


@then("no task files on disk are modified.")
def verify_disk_untouched(context: dict[str, Any]) -> None:
    assert context["refined_file"].read_text(encoding="utf-8") == context["initial_refined_content"]
    assert context["proposed_file"].read_text(encoding="utf-8") == context["initial_proposed_content"]
    assert context["complete_file"].read_text(encoding="utf-8") == context["initial_complete_content"]
    assert context["other_file"].read_text(encoding="utf-8") == context["initial_other_content"]


@then("the output is valid JSON reporting the transitioned tasks and count")
def verify_json_output(context: dict[str, Any]) -> None:
    res = context["last_result"]
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["from_milestone"] == "M1"
    assert data["to_milestone"] == "M2"
    assert data["transitioned_count"] == 2
    assert "TASK-0002" in data["transitioned_tasks"]
    assert "TASK-0003" in data["transitioned_tasks"]
    assert len(data["details"]) == 2
