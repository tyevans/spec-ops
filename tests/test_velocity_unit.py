"""Unit tests for hybrid team delivery velocity and rescue telemetry reporter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.backlog.velocity import (
    analyze_rescues,
    calculate_hybrid_velocity,
    classify_contributor,
    format_cycle_time,
    format_rescues_table,
    format_velocity_table,
    parse_window_days,
    save_velocity_snapshot,
)
from spec_ops.backlog.velocity_models import ContributorVelocity, VelocityReport
from spec_ops.core.models import Task
from spec_ops.core.provenance import CommitRecord


def test_parse_window_days():
    assert parse_window_days("14d") == 14
    assert parse_window_days("30d") == 30
    assert parse_window_days("2w") == 14
    assert parse_window_days("1m") == 30
    assert parse_window_days("1y") == 365
    assert parse_window_days("7") == 7
    assert parse_window_days(21) == 21
    assert parse_window_days("invalid") == 14
    assert parse_window_days(0) == 1


def test_format_cycle_time():
    assert format_cycle_time(4.2) == "4.2 minutes"
    assert format_cycle_time(59.9) == "59.9 minutes"
    assert format_cycle_time(60.0) == "1.0 hours"
    assert format_cycle_time(228.0) == "3.8 hours"
    assert format_cycle_time(2880.0) == "2.0 days"
    assert format_cycle_time(-5.0) == "0.0 minutes"


def test_classify_contributor():
    # Direct autonomous commit
    c1 = CommitRecord(
        full_hash="1" * 40, short_hash="1111111", author="Agent", email="bot@specops.test",
        date="2026-09-30", subject="feat: auto", body="SpecOps-Worker: worker-1\n",
        trailers={"SpecOps-Worker": "worker-1"}, is_autonomous=True,
    )
    assert classify_contributor(c1) == "Agent Workers"

    # Human commit with provenance
    c2 = CommitRecord(
        full_hash="2" * 40, short_hash="2222222", author="Jordan", email="jordan@specops.test",
        date="2026-09-30", subject="feat: human", body="",
        trailers={}, is_autonomous=False,
    )
    assert classify_contributor(c2) == "Human Developers"

    # Commit with autonomous provenance trailer
    c3 = CommitRecord(
        full_hash="3" * 40, short_hash="3333333", author="Someone", email="s@s.com",
        date="2026-09-30", subject="feat: prov", body="",
        trailers={"Provenance": "autonomous worker runner"}, is_autonomous=False,
    )
    assert classify_contributor(c3) == "Agent Workers"

    # Co-authored-by agent trailer
    c4 = CommitRecord(
        full_hash="4" * 40, short_hash="4444444", author="Dev", email="d@d.com",
        date="2026-09-30", subject="feat: pair", body="",
        trailers={"Co-authored-by": "SpecOps Agent <bot@agent.com>"}, is_autonomous=False,
    )
    assert classify_contributor(c4) == "Agent Workers"


def test_calculate_hybrid_velocity_synthetic(tmp_path: Path):
    tasks = [
        Task(id="TASK-0001", title="Task 1", status="Complete", claimed_at="2026-09-30T10:00:00Z", completed_at="2026-09-30T10:10:00Z"),
        Task(id="TASK-0002", title="Task 2", status="Complete", claimed_at="2026-09-30T10:00:00Z", completed_at="2026-09-30T10:20:00Z"),
        Task(id="TASK-0003", title="Task 3", status="Complete", claimed_at="2026-09-30T10:00:00Z", completed_at="2026-09-30T12:00:00Z"),
        Task(id="TASK-0004", title="Task 4", status="Proposed"),
    ]

    commits = [
        # 2 commits for TASK-0001 (Agent) - MUST NOT double count!
        CommitRecord(
            full_hash="a" * 40, short_hash="aaaaaaa", author="Agent", email="a@a",
            date="2026-09-30", subject="c1", body="SpecOps-Task: TASK-0001\nSpecOps-Worker: auto\n",
            trailers={"SpecOps-Worker": "auto"}, task_ids=["TASK-0001"], is_autonomous=True,
        ),
        CommitRecord(
            full_hash="b" * 40, short_hash="bbbbbbb", author="Agent", email="a@a",
            date="2026-09-30", subject="c2", body="SpecOps-Task: TASK-0001\nSpecOps-Worker: auto\n",
            trailers={"SpecOps-Worker": "auto"}, task_ids=["TASK-0001"], is_autonomous=True,
        ),
        # 1 commit for TASK-0002 (Agent)
        CommitRecord(
            full_hash="c" * 40, short_hash="ccccccc", author="Agent", email="a@a",
            date="2026-09-30", subject="c3", body="SpecOps-Task: TASK-0002\nProvenance: autonomous\n",
            trailers={"Provenance": "autonomous"}, task_ids=["TASK-0002"], is_autonomous=True,
        ),
        # 1 commit for TASK-0003 (Human)
        CommitRecord(
            full_hash="d" * 40, short_hash="ddddddd", author="Human Dev", email="h@h",
            date="2026-09-30", subject="c4", body="SpecOps-Task: TASK-0003\n",
            trailers={}, task_ids=["TASK-0003"], is_autonomous=False,
        ),
    ]

    report = calculate_hybrid_velocity(
        repo_root=tmp_path,
        window="14d",
        include_rescues=False,
        tasks=tasks,
        commits=commits,
    )

    # Invariant: 2 unique agent tasks, 1 unique human task, 3 total delivered tasks
    assert report.agent_metrics.tasks_delivered == 2
    assert report.human_metrics.tasks_delivered == 1
    assert report.hybrid_total.tasks_delivered == 3
    assert report.hybrid_total.tasks_delivered == (
        report.agent_metrics.tasks_delivered + report.human_metrics.tasks_delivered
    )

    # Merged commits
    assert report.agent_metrics.merged_commits == 3
    assert report.human_metrics.merged_commits == 1
    assert report.hybrid_total.merged_commits == 4

    # Cycle time averages
    # Agent tasks: 10.0 and 20.0 -> average 15.0 minutes
    assert report.agent_metrics.avg_cycle_time_minutes == 15.0
    # Human task: 120.0 minutes -> 2.0 hours
    assert report.human_metrics.avg_cycle_time_minutes == 120.0
    assert report.human_metrics.avg_cycle_time_formatted == "2.0 hours"


def test_analyze_rescues_failure_clustering():
    records = [
        {"reason": "Preflight failed due to pytest assertion error violating ADR-0004", "timestamp": "2026-09-30"},
        {"reason": "Preflight test runner timed out", "timestamp": "2026-09-30"},
        {"reason": "Source file exceeded 500 lines limit under ADR-0002", "timestamp": "2026-09-30"},
        {"reason": "Mock backdoor rejected by test gate violating ADR-0003", "timestamp": "2026-09-30"},
        {"reason": "Lockfile drift in uv.lock violating ADR-0018", "timestamp": "2026-09-30"},
        {"reason": "Lint failure with ruff code style check", "timestamp": "2026-09-30"},
    ]

    analytics = analyze_rescues(custom_records=records, total_agent_tasks=10)
    assert analytics.total_rescues == 6
    assert analytics.rescue_burden_ratio == 0.6

    clusters_by_name = {c.cluster: c for c in analytics.failure_clusters}
    assert "Preflight Test Failures" in clusters_by_name
    assert "File Length Violations" in clusters_by_name
    assert "Mock Backdoor Rejections" in clusters_by_name
    assert "Lockfile Drifts" in clusters_by_name
    assert "Lint & Style Errors" in clusters_by_name

    assert clusters_by_name["Preflight Test Failures"].incidents == 2
    assert "ADR-0004" in clusters_by_name["Preflight Test Failures"].top_invariants


def test_save_velocity_snapshot_and_tables(tmp_path: Path):
    agent_m = ContributorVelocity(contributor_class="Agent Workers", tasks_delivered=5, merged_commits=10)
    human_m = ContributorVelocity(contributor_class="Human Developers", tasks_delivered=2, merged_commits=4)
    hybrid_m = ContributorVelocity(contributor_class="Hybrid Total", tasks_delivered=7, merged_commits=14)

    report = VelocityReport(
        window="14d",
        window_days=14,
        generated_at="2026-09-30T12:00:00Z",
        agent_metrics=agent_m,
        human_metrics=human_m,
        hybrid_total=hybrid_m,
    )

    out_file = save_velocity_snapshot(report, tmp_path)
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["metrics"]["hybrid_total"]["tasks_delivered"] == 7

    # Verify formatting functions do not raise
    v_table = format_velocity_table(report)
    assert v_table.title is not None
    r_table = format_rescues_table(report)
    assert r_table.title is not None
