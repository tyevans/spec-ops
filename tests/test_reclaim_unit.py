"""Unit tests for stalled worker claim reclamation and lease heartbeat engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0077.
Target Bounded Context: backlog. Frontdoor blackbox verification without private mocks.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.backlog.reclaim import (
    StalledClaimInfo,
    StalledClaimReclamationResult,
    StalledClaimReclaimer,
    _parse_iso_time,
    reclaim_stalled_claims,
)
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project


def test_parse_iso_time_matrix():
    """Verifies parsing of diverse timestamp representations."""
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    ts = now_utc.timestamp()

    # Numeric int / float
    dt_float = _parse_iso_time(ts)
    assert dt_float is not None
    assert abs((dt_float - now_utc).total_seconds()) < 1.0

    # Numeric string
    dt_str_num = _parse_iso_time(str(ts))
    assert dt_str_num is not None
    assert abs((dt_str_num - now_utc).total_seconds()) < 1.0

    # ISO string
    iso_str = now_utc.isoformat()
    dt_iso = _parse_iso_time(iso_str)
    assert dt_iso is not None
    assert dt_iso.year == now_utc.year

    # Date only string YYYY-MM-DD
    dt_date = _parse_iso_time("2026-09-30")
    assert dt_date is not None
    assert dt_date.year == 2026 and dt_date.month == 9 and dt_date.day == 30

    # Invalid values
    assert _parse_iso_time(None) is None
    assert _parse_iso_time("") is None
    assert _parse_iso_time("   ") is None
    assert _parse_iso_time("not-a-date") is None


def test_stalled_claim_reclamation_basic(tmp_path: Path):
    """Verifies expired claims are safely revoked and active claims preserved."""
    repo = tmp_path / "repo"
    init_project(repo, name="ReclaimBasic")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    complete_dir = backlog_dir / "complete"
    refined_dir.mkdir(parents=True, exist_ok=True)
    complete_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime(2026, 9, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # 1. Stalled task (claimed 5 hours ago)
    t1_file = refined_dir / "0081-stalled.md"
    t1 = Task(
        id="0081",
        title="Stalled Task",
        status="In-Progress",
        claimed_by="worker-a",
        claimed_at=(now - datetime.timedelta(hours=5)).isoformat(),
        file_path=t1_file,
    )
    write_task_file(t1)

    # 2. Fresh task (claimed 2 hours ago)
    t2_file = refined_dir / "0082-fresh.md"
    t2 = Task(
        id="0082",
        title="Fresh Task",
        status="In-Progress",
        claimed_by="worker-b",
        claimed_at=(now - datetime.timedelta(hours=2)).isoformat(),
        file_path=t2_file,
    )
    write_task_file(t2)

    # 3. Task with old claim (10h ago) but fresh heartbeat (30m ago)
    t3_file = refined_dir / "0083-heartbeat.md"
    t3 = Task(
        id="0083",
        title="Heartbeat Task",
        status="In-Progress",
        claimed_by="worker-c",
        claimed_at=(now - datetime.timedelta(hours=10)).isoformat(),
        heartbeat_at=(now - datetime.timedelta(minutes=30)).isoformat(),
        file_path=t3_file,
    )
    write_task_file(t3)

    # 4. Completed task with stale timestamp (should never be reclaimed)
    t4_file = complete_dir / "0084-complete.md"
    t4 = Task(
        id="0084",
        title="Complete Task",
        status="Complete",
        claimed_by="worker-d",
        claimed_at=(now - datetime.timedelta(hours=48)).isoformat(),
        file_path=t4_file,
    )
    write_task_file(t4)

    # Write PRIORITY.md
    pfile = backlog_dir / "PRIORITY.md"
    pfile.write_text(
        "# Backlog Priority Index\n\n"
        "- **TASK-0081 (In-Progress)**: [`0081-stalled`](refined/0081-stalled.md)\n"
        "- **TASK-0082 (In-Progress)**: [`0082-fresh`](refined/0082-fresh.md)\n"
        "- **TASK-0083 (In-Progress)**: [`0083-heartbeat`](refined/0083-heartbeat.md)\n"
        "- **TASK-0084 (Complete)**: [`0084-complete`](complete/0084-complete.md)\n",
        encoding="utf-8",
    )

    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo, now=now)
    result = reclaimer.reclaim(timeout_hours=4.0, dry_run=False)

    assert result.reclaimed_count == 1
    assert result.reclaimed_ids == ["TASK-0081"]
    assert result.active_count == 2  # TASK-0082 and TASK-0083
    assert len(result.audit_trail) == 1
    assert "TASK-0081" in result.audit_trail[0]

    # Verify disk mutations for reclaimed task
    parsed_1 = parse_task(t1_file)
    assert parsed_1.claimed_by == ""
    assert parsed_1.claimed_at == ""
    assert parsed_1.status == "Refined"

    # Verify active tasks were NOT modified
    parsed_2 = parse_task(t2_file)
    assert parsed_2.claimed_by == "worker-b"
    assert parsed_2.status == "In-Progress"

    parsed_3 = parse_task(t3_file)
    assert parsed_3.claimed_by == "worker-c"
    assert parsed_3.status == "In-Progress"

    # Verify PRIORITY.md updated
    p_content = pfile.read_text(encoding="utf-8")
    assert "TASK-0081 (Refined)" in p_content
    assert "TASK-0082 (In-Progress)" in p_content


def test_stalled_claim_dry_run(tmp_path: Path):
    """Verifies dry-run returns proposed actions without modifying disk."""
    repo = tmp_path / "repo"
    init_project(repo, name="ReclaimDryRun")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    t_file = refined_dir / "0010-stalled.md"
    task = Task(
        id="0010",
        title="Stalled Dry Run Task",
        status="In-Progress",
        claimed_by="worker-dry",
        claimed_at=(now - datetime.timedelta(hours=10)).isoformat(),
        file_path=t_file,
    )
    write_task_file(task)

    pfile = backlog_dir / "PRIORITY.md"
    pfile.write_text("- **TASK-0010 (In-Progress)**: [`0010-stalled`](refined/0010-stalled.md)\n", encoding="utf-8")

    result = reclaim_stalled_claims(repo, timeout_hours=4.0, dry_run=True, now=now)
    assert result.dry_run is True
    assert result.reclaimed_count == 1
    assert result.reclaimed_ids == ["TASK-0010"]
    assert any("[DRY RUN]" in a for a in result.audit_trail)

    # Disk state should remain untouched
    parsed = parse_task(t_file)
    assert parsed.claimed_by == "worker-dry"
    assert parsed.status == "In-Progress"
    assert "TASK-0010 (In-Progress)" in pfile.read_text(encoding="utf-8")


def test_worktree_heartbeat_file_detection(tmp_path: Path):
    """Verifies .heartbeat and heartbeat.json files inside worktree are detected."""
    repo = tmp_path / "repo"
    init_project(repo, name="ReclaimWorktree")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    wt_dir = repo / ".worktrees" / "task-0030"
    wt_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    t_file = refined_dir / "0030-worker.md"
    task = Task(
        id="0030",
        title="Worktree Heartbeat Task",
        status="In-Progress",
        claimed_by="worker-wt",
        claimed_at=(now - datetime.timedelta(hours=8)).isoformat(),
        file_path=t_file,
    )
    write_task_file(task)

    # 1. Without heartbeat file: claim is stalled (8h > 4h)
    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo, now=now)
    is_stalled, info = reclaimer.evaluate_task_claim(task, timeout_hours=4.0)
    assert is_stalled is True

    # 2. Add heartbeat.json in worktree (active 10 mins ago)
    hb_json = wt_dir / "heartbeat.json"
    hb_json.write_text(json.dumps({"heartbeat": (now - datetime.timedelta(minutes=10)).isoformat()}), encoding="utf-8")

    is_stalled2, info2 = reclaimer.evaluate_task_claim(task, timeout_hours=4.0)
    assert is_stalled2 is False
    assert info2.status == "Active"
    assert "heartbeat.json" in info2.last_activity_source


def test_future_timestamp_handling(tmp_path: Path):
    """Verifies future timestamps or minor clock drift do not cause reclamation."""
    repo = tmp_path / "repo"
    init_project(repo, name="ReclaimClockDrift")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    t_file = refined_dir / "0040-future.md"
    task = Task(
        id="0040",
        title="Future Task",
        status="In-Progress",
        claimed_by="worker-future",
        claimed_at=(now + datetime.timedelta(minutes=5)).isoformat(),
        file_path=t_file,
    )
    write_task_file(task)

    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo, now=now)
    is_stalled, info = reclaimer.evaluate_task_claim(task, timeout_hours=4.0)
    assert is_stalled is False
    assert info.inactive_hours == 0.0


def test_console_render_and_serialization(tmp_path: Path):
    """Verifies render_console and to_dict work cleanly for both zero and non-zero claims."""
    info = StalledClaimInfo(
        task_id="TASK-0050",
        title="Test Console Task",
        claimed_by="worker-test",
        claimed_at="2026-09-30T10:00:00Z",
        inactive_hours=5.5,
        status="Stalled",
    )
    res = StalledClaimReclamationResult(
        reclaimed_count=1,
        reclaimed_ids=["TASK-0050"],
        reclaimed_tasks=[info],
        active_count=0,
        active_tasks=[],
        timeout_hours=4.0,
        dry_run=False,
        audit_trail=["Reclaimed TASK-0050"],
    )

    data = res.to_dict()
    assert data["reclaimed_count"] == 1
    assert data["reclaimed_ids"] == ["TASK-0050"]

    console = Console(file=open(os.devnull, "w"))
    res.render_console(console)

    empty_res = StalledClaimReclamationResult(
        reclaimed_count=0,
        reclaimed_ids=[],
        reclaimed_tasks=[],
        active_count=0,
        active_tasks=[],
        timeout_hours=4.0,
        dry_run=True,
    )
    empty_res.render_console(console)
