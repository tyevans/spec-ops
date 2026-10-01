"""Executable BDD acceptance tests for US-0025: Milestone Planning Studio.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0006, ADR-0007, ADR-0009; PRD-0005; US-0025.
Deals strictly with public frontdoors and keeps source under 400 lines (ADR-0002).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.migration import parse_frontmatter_and_body
from spec_ops.scaffold.init import init_project

scenarios("features/us_0025_interactive_milestone_planning_and_workload_studio.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def bdd_workspace(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "bdd_repo"
    init_project(repo, name="BDDStudioWorkspace")

    backlog_dir = repo / "docs" / "project" / "backlog"
    for p in backlog_dir.rglob("*.md"):
        p.unlink()

    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"
    complete_dir = backlog_dir / "complete"

    refined_dir.mkdir(parents=True, exist_ok=True)
    proposed_dir.mkdir(parents=True, exist_ok=True)
    complete_dir.mkdir(parents=True, exist_ok=True)

    # Base task in complete
    (complete_dir / "0001-setup.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Setup\n"
        "status: Complete\n"
        "milestone: M1-MVP\n"
        "execution_lane: agent-autonomous\n"
        "---\n"
        "# Setup\n",
        encoding="utf-8",
    )

    # Unassigned task in proposed
    (proposed_dir / "0045-unassigned.md").write_text(
        "---\n"
        "id: '0045'\n"
        "title: Dynamic Planning Engine\n"
        "status: Proposed\n"
        "target_bc: backlog\n"
        "dependencies:\n"
        "  - TASK-0001\n"
        "---\n"
        "# Dynamic Planning Engine\n",
        encoding="utf-8",
    )

    # 4-level dependency chain for M2
    (refined_dir / "0010-chain-d.md").write_text(
        "---\n"
        "id: '0010'\n"
        "title: Chain D\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: agent-autonomous\n"
        "dependencies:\n"
        "  - TASK-0009\n"
        "---\n"
        "# Chain D\n",
        encoding="utf-8",
    )
    (refined_dir / "0009-chain-c.md").write_text(
        "---\n"
        "id: '0009'\n"
        "title: Chain C\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: agent-autonomous\n"
        "dependencies:\n"
        "  - TASK-0008\n"
        "---\n"
        "# Chain C\n",
        encoding="utf-8",
    )
    (refined_dir / "0008-chain-b.md").write_text(
        "---\n"
        "id: '0008'\n"
        "title: Chain B\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: agent-autonomous\n"
        "dependencies:\n"
        "  - TASK-0007\n"
        "---\n"
        "# Chain B\n",
        encoding="utf-8",
    )
    (refined_dir / "0007-chain-a.md").write_text(
        "---\n"
        "id: '0007'\n"
        "title: Chain A\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: agent-autonomous\n"
        "dependencies: []\n"
        "---\n"
        "# Chain A\n",
        encoding="utf-8",
    )

    # ROADMAP.md
    roadmap = backlog_dir / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone 1: MVP (Complete)\n"
        "- Setup (`TASK-0001`).\n\n"
        "## Milestone 2: Q4 Release (Active)\n"
        "- Chain A (`TASK-0007`).\n"
        "- Chain B (`TASK-0008`).\n"
        "- Chain C (`TASK-0009`).\n"
        "- Chain D (`TASK-0010`).\n",
        encoding="utf-8",
    )

    return {"repo": repo, "output": "", "json_data": {}}


@given('a repository with unassigned backlog tasks and milestones in "docs/project/backlog/ROADMAP.md"')
def given_repo_with_tasks_and_roadmap(bdd_workspace: dict[str, Any]):
    repo = bdd_workspace["repo"]
    assert (repo / "docs" / "project" / "backlog" / "ROADMAP.md").exists()
    assert (repo / "docs" / "project" / "backlog" / "proposed" / "0045-unassigned.md").exists()


@given('a repository with unassigned backlog tasks')
def given_repo_with_unassigned_tasks(bdd_workspace: dict[str, Any]):
    repo = bdd_workspace["repo"]
    assert (repo / "docs" / "project" / "backlog" / "proposed" / "0045-unassigned.md").exists()


@given('milestone "M2-Q4-Release" has assigned tasks with a dependency chain of 4 levels')
def given_milestone_with_deep_dependencies(bdd_workspace: dict[str, Any]):
    repo = bdd_workspace["repo"]
    ref_dir = repo / "docs" / "project" / "backlog" / "refined"
    assert (ref_dir / "0010-chain-d.md").exists()


@when(parsers.parse('the lead runs "{command_str}"'))
def when_lead_runs_command(bdd_workspace: dict[str, Any], command_str: str):
    tokens = command_str.split()
    assert tokens[0] == "spec-ops"
    cmd_args = tokens[1:]
    res = run_spec_ops(bdd_workspace["repo"], cmd_args)
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    bdd_workspace["output"] = res.stdout
    if "--json" in cmd_args:
        bdd_workspace["json_data"] = json.loads(res.stdout)


@then(parsers.parse('the planning matrix reports task "{task_id}" assigned to milestone "{milestone}"'))
def then_matrix_reports_assignment(bdd_workspace: dict[str, Any], task_id: str, milestone: str):
    data = bdd_workspace["json_data"]
    ms_map = data.get("matrix", {}).get("milestones", {})
    assert milestone in ms_map, f"Milestone '{milestone}' missing from matrix: {list(ms_map.keys())}"
    task_ids = [t["task_id"] for t in ms_map[milestone]]
    assert task_id in task_ids, f"Task '{task_id}' not found in milestone '{milestone}'"


@then(parsers.parse('the execution lane is designated as "{lane}"'))
def then_execution_lane_designated(bdd_workspace: dict[str, Any], lane: str):
    data = bdd_workspace["json_data"]
    lane_map = data.get("matrix", {}).get("execution_lanes", {})
    assert lane in lane_map, f"Lane '{lane}' missing from lanes: {list(lane_map.keys())}"
    task_ids = [t["task_id"] for t in lane_map[lane]]
    assert "TASK-0045" in task_ids


@then("the simulation computes delivery confidence intervals for P50, P80, and P95")
def then_simulation_computes_confidence_intervals(bdd_workspace: dict[str, Any]):
    data = bdd_workspace["json_data"]
    sims = data.get("simulations", {})
    assert len(sims) > 0, "No simulations found in output"
    for ms, sim in sims.items():
        ci = sim.get("confidence_intervals", {})
        assert "p50" in ci and "p80" in ci and "p95" in ci
        assert ci["p50"]["days"] <= ci["p80"]["days"] <= ci["p95"]["days"]


@then(parsers.parse('flags dependency depth bottlenecks for milestone "{milestone}"'))
def then_flags_bottlenecks(bdd_workspace: dict[str, Any], milestone: str):
    data = bdd_workspace["json_data"]
    sims = data.get("simulations", {})
    matched_sim = None
    for ms_key, sim in sims.items():
        if milestone in ms_key or ms_key in milestone:
            matched_sim = sim
            break
    assert matched_sim is not None, f"No simulation for milestone '{milestone}'"
    assert matched_sim["dependency_depth"] >= 4
    bottlenecks = matched_sim.get("bottlenecks", [])
    assert len(bottlenecks) > 0
    assert any("depth of 4 levels" in b for b in bottlenecks)


@then(parsers.parse('task "{task_id}" frontmatter is atomically updated with milestone "{milestone}"'))
def then_task_frontmatter_updated(bdd_workspace: dict[str, Any], task_id: str, milestone: str):
    repo = bdd_workspace["repo"]
    task_f = repo / "docs" / "project" / "backlog" / "proposed" / "0045-unassigned.md"
    assert task_f.exists()
    meta, _, _ = parse_frontmatter_and_body(task_f.read_text(encoding="utf-8"))
    assert meta.get("milestone") == milestone


@then(parsers.parse('"{roadmap_path}" is synchronized with task "{task_id}"'))
def then_roadmap_synchronized(bdd_workspace: dict[str, Any], roadmap_path: str, task_id: str):
    repo = bdd_workspace["repo"]
    rm = repo / roadmap_path
    assert rm.exists()
    content = rm.read_text(encoding="utf-8")
    assert task_id in content
