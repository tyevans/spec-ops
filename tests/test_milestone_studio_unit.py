"""Unit tests for Milestone Planning Studio and Feasibility Simulation.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0025.
Deals strictly with public frontdoors and keeps source under 400 lines (ADR-0002).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from spec_ops.backlog.milestone_studio import (
    FeasibilitySimulation,
    MilestoneStudio,
    TaskAllocation,
)
from spec_ops.backlog.milestone_studio_sync import (
    sync_roadmap_milestone,
    update_task_frontmatter_milestone,
)
from spec_ops.config.loader import load_config
from spec_ops.core.migration import parse_frontmatter_and_body
from spec_ops.scaffold.init import init_project


@pytest.fixture
def studio_workspace(tmp_path: Path) -> Path:
    """Sets up a realistic test workspace with tasks across milestones and stages."""
    repo = tmp_path / "studio_repo"
    init_project(repo, name="StudioTestWorkspace")
    backlog_dir = repo / "docs" / "project" / "backlog"
    for p in backlog_dir.rglob("*.md"):
        p.unlink()

    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"
    complete_dir = backlog_dir / "complete"

    refined_dir.mkdir(parents=True, exist_ok=True)
    proposed_dir.mkdir(parents=True, exist_ok=True)
    complete_dir.mkdir(parents=True, exist_ok=True)

    # Completed task
    (complete_dir / "0001-initial-setup.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Initial Setup\n"
        "status: Complete\n"
        "milestone: M1-MVP\n"
        "execution_lane: agent-autonomous\n"
        "dependencies: []\n"
        "---\n"
        "# Initial Setup\n",
        encoding="utf-8",
    )

    # Refined task in M2 with deep dependencies
    (refined_dir / "0010-chain-c.md").write_text(
        "---\n"
        "id: '0010'\n"
        "title: Chain C\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: agent-autonomous\n"
        "dependencies:\n"
        "  - TASK-0009\n"
        "---\n"
        "# Chain C\n",
        encoding="utf-8",
    )
    (refined_dir / "0009-chain-b.md").write_text(
        "---\n"
        "id: '0009'\n"
        "title: Chain B\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: human-lead\n"
        "dependencies:\n"
        "  - TASK-0008\n"
        "---\n"
        "# Chain B\n",
        encoding="utf-8",
    )
    (refined_dir / "0008-chain-a.md").write_text(
        "---\n"
        "id: '0008'\n"
        "title: Chain A\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: agent-autonomous\n"
        "dependencies:\n"
        "  - TASK-0007\n"
        "---\n"
        "# Chain A\n",
        encoding="utf-8",
    )
    (refined_dir / "0007-chain-root.md").write_text(
        "---\n"
        "id: '0007'\n"
        "title: Chain Root\n"
        "status: Refined\n"
        "milestone: M2-Q4-Release\n"
        "execution_lane: agent-autonomous\n"
        "dependencies: []\n"
        "---\n"
        "# Chain Root\n",
        encoding="utf-8",
    )

    # Unassigned task in proposed
    (proposed_dir / "0045-unassigned-task.md").write_text(
        "---\n"
        "id: '0045'\n"
        "title: Unassigned Work Item\n"
        "status: Proposed\n"
        "target_bc: backlog\n"
        "dependencies:\n"
        "  - TASK-0001\n"
        "---\n"
        "# Unassigned Work Item\n",
        encoding="utf-8",
    )

    # Velocity snapshot
    metrics_dir = repo / ".spec-ops" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "velocity.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "hybrid_total": {
                        "tasks_per_week": 4.0,
                        "tasks_delivered": 8,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    return repo


def test_collect_tasks_and_allocation_matrix(studio_workspace: Path):
    """Verifies task scanning, milestone categorization, and execution lane breakdown."""
    config = load_config(studio_workspace)
    studio = MilestoneStudio(config)
    tasks = studio.collect_tasks()

    assert len(tasks) == 6
    task_ids = {t.task_id for t in tasks}
    assert "TASK-0001" in task_ids
    assert "TASK-0010" in task_ids
    assert "TASK-0045" in task_ids

    res = studio.execute(simulate=False, non_interactive=True)
    assert "M1-MVP" in res.milestones
    assert "M2-Q4-Release" in res.milestones
    assert len(res.unassigned) == 1
    assert res.unassigned[0].task_id == "TASK-0045"

    assert len(res.execution_lanes["agent-autonomous"]) >= 3
    assert len(res.execution_lanes["human-lead"]) >= 1


def test_feasibility_simulation_confidence_and_bottlenecks(studio_workspace: Path):
    """Verifies capacity confidence intervals and prerequisite depth bottleneck flagging."""
    config = load_config(studio_workspace)
    studio = MilestoneStudio(config)
    tasks = studio.collect_tasks()

    vel = studio.load_rolling_velocity()
    assert vel == 4.0

    # Milestone 2 has a 4-level chain: TASK-0007 -> TASK-0008 -> TASK-0009 -> TASK-0010
    sim = studio.simulate_feasibility("M2-Q4-Release", tasks, vel)
    assert sim.total_tasks == 4
    assert sim.remaining_tasks == 4
    assert sim.completed_tasks == 0
    assert sim.dependency_depth == 4

    # Bottleneck detection for chain depth >= 4
    assert len(sim.bottlenecks) >= 1
    assert any("depth of 4 levels" in b for b in sim.bottlenecks)
    assert sim.is_feasible is False

    # Confidence intervals
    assert sim.confidence_intervals["p50"]["days"] > 0
    assert sim.confidence_intervals["p80"]["days"] >= sim.confidence_intervals["p50"]["days"]
    assert sim.confidence_intervals["p95"]["days"] >= sim.confidence_intervals["p80"]["days"]


def test_atomic_assignment_and_save(studio_workspace: Path):
    """Verifies in-memory vs persisted reallocation to task frontmatter and ROADMAP.md."""
    config = load_config(studio_workspace)
    studio = MilestoneStudio(config)

    # 1. Preview without save: disk remains unchanged
    res_dry = studio.execute(
        assignments=["TASK-0045=M2-Q4-Release:hybrid-pair"],
        save=False,
        non_interactive=True,
    )
    assert res_dry.saved is False
    target_f = studio_workspace / "docs" / "project" / "backlog" / "proposed" / "0045-unassigned-task.md"
    assert "milestone: M2-Q4-Release" not in target_f.read_text(encoding="utf-8")

    # 2. Persist with save: updates frontmatter and ROADMAP.md
    res_save = studio.execute(
        assignments=["TASK-0045=M2-Q4-Release:hybrid-pair"],
        save=True,
        non_interactive=True,
    )
    assert res_save.saved is True
    assert "TASK-0045" in res_save.updated_tasks
    assert res_save.updated_roadmap is True

    # Verify task frontmatter
    saved_meta, _, _ = parse_frontmatter_and_body(target_f.read_text(encoding="utf-8"))
    assert saved_meta.get("milestone") == "M2-Q4-Release"
    assert saved_meta.get("execution_profile") == "hybrid-pair"
    assert saved_meta.get("target_bc") == "backlog"
    assert "TASK-0001" in saved_meta.get("dependencies", [])

    # Verify ROADMAP.md
    roadmap_f = studio_workspace / "docs" / "project" / "backlog" / "ROADMAP.md"
    assert roadmap_f.exists()
    content_rm = roadmap_f.read_text(encoding="utf-8")
    assert "TASK-0045" in content_rm


def test_cli_milestone_plan_frontdoor(studio_workspace: Path):
    """Tests CLI invocation via subprocess frontdoor."""
    cli_env = {
        **os.environ,
        "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
    }

    # Run JSON inspection
    p_json = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "milestone", "plan", "--json", "--non-interactive"],
        cwd=studio_workspace,
        capture_output=True,
        text=True,
        env=cli_env,
    )
    assert p_json.returncode == 0
    payload = json.loads(p_json.stdout)
    assert "matrix" in payload
    assert "M1-MVP" in payload["matrix"]["milestones"]

    # Run assign with save
    p_assign = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "milestone",
            "plan",
            "--assign",
            "TASK-0045=M1-MVP:agent-autonomous",
            "--save",
            "--simulate",
            "--json",
            "--non-interactive",
        ],
        cwd=studio_workspace,
        capture_output=True,
        text=True,
        env=cli_env,
    )
    assert p_assign.returncode == 0
    assign_payload = json.loads(p_assign.stdout)
    assert assign_payload["saved"] is True
    assert "TASK-0045" in assign_payload["updated_tasks"]
    assert "M1-MVP" in assign_payload["simulations"]
