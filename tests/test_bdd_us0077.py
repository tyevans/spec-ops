"""Executable BDD acceptance tests for US-0077: Daily Curation Standup Digest.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009; PRD-0005; US-0077.
Target Bounded Context: backlog. Frontdoor blackbox verification without private mocks.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.blockers import block_task
from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import BlockerInfo, Task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0077_daily_standup_digest.feature")

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
def digest_repo(tmp_path: Path) -> Path:
    """Sets up a realistic test repository with completed tasks, claims, blockers, and buffer."""
    repo = tmp_path / "digest_workspace"
    init_project(repo, name="StandupDigestTest")
    backlog_dir = repo / "docs" / "project" / "backlog"
    complete_dir = backlog_dir / "complete"
    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"
    worktrees_dir = repo / ".worktrees"

    complete_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)
    proposed_dir.mkdir(parents=True, exist_ok=True)
    worktrees_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    recent_ts = (now - datetime.timedelta(hours=2)).isoformat()
    stalled_ts = (now - datetime.timedelta(hours=48)).isoformat()

    # 1. Three completed tasks within last 24h
    for i in range(1, 4):
        cid = f"{i:04d}"
        t = Task(
            id=cid,
            title=f"Completed Feature {i}",
            status="Complete",
            target_bc="backlog",
            file_path=complete_dir / f"{cid}-completed-{i}.md",
        )
        setattr(t, "completed_at", recent_ts)
        write_task_file(t)

    # 2. Six tasks in ready buffer (refined/)
    for i in range(4, 10):
        cid = f"{i:04d}"
        t = Task(
            id=cid,
            title=f"Ready Feature {i}",
            status="Refined",
            target_bc="backlog",
            file_path=refined_dir / f"{cid}-ready-{i}.md",
        )
        write_task_file(t)

    # 3. One claimed task in refined/ with 48h stalled claim
    t_stalled = Task(
        id="0013",
        title="Stalled Autonomous Feature",
        status="Refined",
        claimed_by="agent-01",
        branch="feat/task-0013",
        file_path=refined_dir / "0013-stalled.md",
    )
    setattr(t_stalled, "claimed_at", stalled_ts)
    setattr(t_stalled, "timestamp", stalled_ts)
    write_task_file(t_stalled)

    wt_13 = worktrees_dir / "task-0013"
    wt_13.mkdir(parents=True, exist_ok=True)

    # 4. One blocked proposed item
    t_blocked = Task(
        id="0014",
        title="Blocked Storage Migration",
        status="Blocked",
        target_bc="core",
        blocker=BlockerInfo(
            type="unknown",
            question="Which database engine should be used?",
            raised_by="human-lead",
            raised_at=recent_ts,
        ),
        file_path=proposed_dir / "0014-blocked.md",
    )
    write_task_file(t_blocked)

    # 5. Candidate proposed task with satisfied dependencies
    t_candidate = Task(
        id="0015",
        title="Next Up Candidate Feature",
        status="Proposed",
        dependencies=["TASK-0001"],
        target_bc="backlog",
        file_path=proposed_dir / "0015-candidate.md",
    )
    write_task_file(t_candidate)

    # Priority index
    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Index\n\n"
        "- **TASK-0001 (Complete)**: [`0001-completed-1`](complete/0001-completed-1.md)\n"
        "- **TASK-0002 (Complete)**: [`0002-completed-2`](complete/0002-completed-2.md)\n"
        "- **TASK-0003 (Complete)**: [`0003-completed-3`](complete/0003-completed-3.md)\n"
        "- **TASK-0004 (Refined)**: [`0004-ready-4`](refined/0004-ready-4.md)\n"
        "- **TASK-0005 (Refined)**: [`0005-ready-5`](refined/0005-ready-5.md)\n"
        "- **TASK-0006 (Refined)**: [`0006-ready-6`](refined/0006-ready-6.md)\n"
        "- **TASK-0007 (Refined)**: [`0007-ready-7`](refined/0007-ready-7.md)\n"
        "- **TASK-0008 (Refined)**: [`0008-ready-8`](refined/0008-ready-8.md)\n"
        "- **TASK-0009 (Refined)**: [`0009-ready-9`](refined/0009-ready-9.md)\n"
        "- **TASK-0013 (In-Progress)**: [`0013-stalled`](refined/0013-stalled.md)\n"
        "- **TASK-0014 (Blocked)**: [`0014-blocked`](proposed/0014-blocked.md)\n"
        "- **TASK-0015 (Proposed)**: [`0015-candidate`](proposed/0015-candidate.md)\n",
        encoding="utf-8",
    )

    return repo


@pytest.fixture
def bdd_state() -> dict[str, Any]:
    return {}


@given("a repository with completed tasks in the last 24 hours, active in-progress worktree claims, and blocked proposed items")
def setup_digest_environment(digest_repo: Path, bdd_state: dict[str, Any]):
    bdd_state["repo"] = digest_repo


@when('the engineering lead runs "spec-ops queue digest"')
def run_default_digest(bdd_state: dict[str, Any]):
    res = run_spec_ops_cmd(bdd_state["repo"], ["queue", "digest"])
    bdd_state["res"] = res


@then("the command outputs a formatted Markdown standup digest highlighting completed throughput, active worker leases, blocker bottlenecks, and ready buffer capacity.")
def verify_markdown_digest_output(bdd_state: dict[str, Any]):
    res = bdd_state["res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    stdout = res.stdout

    # Verify Executive Summary table and rows
    assert "| Ready Buffer Level" in stdout
    assert "6/10 (Under-buffered)" in stdout
    assert "Promote 4 proposed tasks" in stdout

    assert "| Velocity (24h)" in stdout
    assert "3 tasks completed" in stdout
    assert "On track" in stdout

    assert "| Stalled Worktrees" in stdout
    assert "TASK-0013 (48h no activity)" in stdout
    assert "Trigger human rescue" in stdout

    assert "| Blocker Bottlenecks" in stdout
    assert "1 active blockers" in stdout

    # Verify detail sections
    assert "## Completed Throughput (24h)" in stdout
    assert "TASK-0001" in stdout
    assert "TASK-0002" in stdout
    assert "TASK-0003" in stdout

    assert "## Active Worker Leases" in stdout
    assert "TASK-0013" in stdout
    assert "agent-01" in stdout

    assert "## Blocker Bottlenecks" in stdout
    assert "TASK-0014" in stdout
    assert "Which database engine should be used?" in stdout

    assert "## Ready Buffer & Refinement Candidates" in stdout
    assert "Candidate Proposed Tasks Ready for Immediate Refinement" in stdout
    assert "TASK-0015" in stdout


@when('the engineering lead runs "spec-ops queue digest --format json"')
def run_json_digest(bdd_state: dict[str, Any]):
    res = run_spec_ops_cmd(bdd_state["repo"], ["queue", "digest", "--format", "json"])
    bdd_state["res"] = res


@then("the output is valid JSON containing metrics, completed throughput, active worker leases, blocker bottlenecks, and ready buffer health.")
def verify_json_digest_output(bdd_state: dict[str, Any]):
    res = bdd_state["res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    data = json.loads(res.stdout)

    assert data["window"] == "24h"
    assert data["window_hours"] == 24.0

    metrics = data["metrics"]
    assert metrics["completed_in_window"] == 3
    assert metrics["ready_buffer_count"] == 6
    assert metrics["target_buffer"] == 10
    assert metrics["buffer_status"] == "Under-buffered"
    assert metrics["stalled_leases_count"] == 1
    assert metrics["blockers_count"] == 1
    assert metrics["candidate_proposed_count"] == 1

    completed_ids = [c["task_id"] for c in data["completed_throughput"]]
    assert "TASK-0001" in completed_ids
    assert "TASK-0002" in completed_ids
    assert "TASK-0003" in completed_ids

    lease_ids = [l["task_id"] for l in data["active_worker_leases"]]
    assert "TASK-0013" in lease_ids
    assert data["active_worker_leases"][0]["is_stalled"] is True

    blocker_ids = [b["task_id"] for b in data["blocker_bottlenecks"]]
    assert "TASK-0014" in blocker_ids

    candidate_ids = [c["task_id"] for c in data["ready_buffer"]["candidate_proposed_tasks"]]
    assert "TASK-0015" in candidate_ids


@when('the engineering lead runs "spec-ops queue digest --window 48h"')
def run_window_digest(bdd_state: dict[str, Any]):
    res = run_spec_ops_cmd(bdd_state["repo"], ["queue", "digest", "--window", "48h"])
    bdd_state["res"] = res


@then("the standup digest reflects the 48h analysis window.")
def verify_window_digest_output(bdd_state: dict[str, Any]):
    res = bdd_state["res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}"
    stdout = res.stdout
    assert "Velocity (48h)" in stdout
    assert "Completed Throughput (48h)" in stdout
