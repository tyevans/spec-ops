"""Comprehensive unit tests for SDLC provenance and traceability audit engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009; PRD-0005; US-0019.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Persona, PRD, ProjectData, Task, UserStory
from spec_ops.core.provenance import (
    CommitRecord,
    ContributorStats,
    audit_provenance,
    build_provenance_lineage,
    compute_contributor_stats,
    extract_commit_records,
    extract_task_ids_from_trailers,
    extract_trailers_from_text,
    format_contributions_table,
    format_traceability_matrix_table,
    is_autonomous_contributor,
    parse_commit_from_raw,
    run_provenance_audit,
)


def test_extract_trailers_from_text_variants():
    """Tests trailer parsing with various formats and delimiters."""
    assert extract_trailers_from_text("") == {}
    assert extract_trailers_from_text("   \n\n  ") == {}

    text = """feat(core): new capability

Here is some body description.

SpecOps-Task: TASK-0042
Governing-ADRs: ADR-0001, ADR-0003
Provenance: spec-ops autonomous worker
Verification: pass
"""
    trailers = extract_trailers_from_text(text)
    assert trailers["SpecOps-Task"] == "TASK-0042"
    assert trailers["Governing-ADRs"] == "ADR-0001, ADR-0003"
    assert trailers["Provenance"] == "spec-ops autonomous worker"
    assert trailers["Verification"] == "pass"


def test_extract_task_ids_from_trailers_keys_and_values():
    """Tests canonical task ID extraction from various trailer keys and syntax."""
    # Key variants
    assert extract_task_ids_from_trailers({"SpecOps-Task": "TASK-0001"}) == ["TASK-0001"]
    assert extract_task_ids_from_trailers({"specops-task": "TASK-0002"}) == ["TASK-0002"]
    assert extract_task_ids_from_trailers({"Task-ID": "TASK-0003"}) == ["TASK-0003"]
    assert extract_task_ids_from_trailers({"task_id": "TASK-0004"}) == ["TASK-0004"]
    assert extract_task_ids_from_trailers({"Task": "TASK-0005"}) == ["TASK-0005"]
    assert extract_task_ids_from_trailers({"taskid": "TASK-0006"}) == ["TASK-0006"]

    # Number normalization and spike support
    assert extract_task_ids_from_trailers({"SpecOps-Task": "18"}) == ["TASK-0018"]
    assert extract_task_ids_from_trailers({"SpecOps-Task": "task-7"}) == ["TASK-0007"]
    assert extract_task_ids_from_trailers({"SpecOps-Task": "SPIKE-0002"}) == ["SPIKE-0002"]

    # Multiple and deduplication
    multi = extract_task_ids_from_trailers({"SpecOps-Task": "TASK-0001, TASK-0002, TASK-0001"})
    assert multi == ["TASK-0001", "TASK-0002"]

    # Irrelevant trailers ignored
    assert extract_task_ids_from_trailers({"Governing-ADRs": "ADR-0001", "Author": "Dev"}) == []


def test_is_autonomous_contributor():
    """Tests autonomous agent attribution rules."""
    assert is_autonomous_contributor({"Provenance": "spec-ops autonomous worker"}) is True
    assert is_autonomous_contributor({"provenance": "autonomous"}) is True
    assert is_autonomous_contributor({"Provenance": "spec-ops-worker"}) is True
    assert is_autonomous_contributor({"Provenance": "agent-runner"}) is True
    assert is_autonomous_contributor({"Provenance": "bot-service"}) is True

    # Author heuristics
    assert is_autonomous_contributor({}, author="dependabot[bot]") is True
    assert is_autonomous_contributor({}, author="spec-ops-worker") is True
    assert is_autonomous_contributor({}, email="autonomous@specops.dev") is True
    assert is_autonomous_contributor({}, email="ci@agent-runner.org") is True

    # Human developers
    assert is_autonomous_contributor({}, author="Jordan Lead", email="jordan@company.com") is False
    assert is_autonomous_contributor({"Provenance": "human developer"}, author="Riley") is False


def test_parse_commit_from_raw():
    """Tests raw git log fields mapping to structured CommitRecord."""
    rec = parse_commit_from_raw(
        full_hash="1111222233334444555566667777888899990000",
        short_hash="1111222",
        author="Agent",
        email="agent@specops.dev",
        date="2026-09-30",
        subject="feat(task-0075): provenance",
        body="SpecOps-Task: TASK-0075\nProvenance: autonomous\nVerification: pass\n",
    )
    assert rec.full_hash == "1111222233334444555566667777888899990000"
    assert rec.short_hash == "1111222"
    assert rec.task_ids == ["TASK-0075"]
    assert rec.is_autonomous is True
    assert rec.verification_status == "pass"


def test_extract_commit_records_nonexistent_repo(tmp_path: Path):
    """Tests graceful fallback when directory is not a git repository."""
    assert extract_commit_records(tmp_path / "not_git") == []


def test_build_provenance_lineage():
    """Tests multi-column lineage graph assembly and orphaned story detection."""
    data = ProjectData(
        personas=[Persona(id="jordan", name="Jordan (Lead)")],
        prds=[PRD(id="PRD-0005", title="Graph PRD", target_persona="Jordan (Lead)")],
        stories=[
            UserStory(id="US-0019", title="Traceability Story", persona="Jordan (Lead)", governing_prd="PRD-0005"),
            UserStory(id="US-0099", title="Orphan Story", governing_prd="PRD-9999"),
        ],
        tasks=[
            Task(id="TASK-0075", title="Audit Engine", status="Complete", governing_stories=["US-0019"]),
            Task(id="TASK-0076", title="Visualizer Filter", status="Refined", governing_stories=["US-0019"]),
        ],
    )
    c75 = CommitRecord(
        full_hash="a" * 40, short_hash="aaaaaaa", author="Dev", email="d@d", date="2026-09-30",
        subject="feat: task 75", body="SpecOps-Task: TASK-0075", task_ids=["TASK-0075"],
    )
    commits_by_task = {"TASK-0075": [c75]}

    rows, orphaned_stories = build_provenance_lineage(data, commits_by_task)

    assert "US-0099" in orphaned_stories
    assert len(rows) == 2
    row75 = next(r for r in rows if r["task"] == "TASK-0075")
    assert row75["persona"] == "Jordan (Lead)"
    assert row75["prd"] == "PRD-0005"
    assert row75["story"] == "US-0019"
    assert row75["commit"] == "aaaaaaa"
    assert row75["status"] == "Complete"

    row76 = next(r for r in rows if r["task"] == "TASK-0076")
    assert row76["commit"] == "—"


def test_compute_contributor_stats():
    """Tests delivery velocity aggregation and verification pass rates."""
    tasks = [
        Task(id="TASK-0001", title="T1", status="Complete"),
        Task(id="TASK-0002", title="T2", status="Complete"),
        Task(id="TASK-0003", title="T3", status="Complete"),
        Task(id="TASK-0004", title="T4", status="Proposed"),
    ]
    commits = [
        CommitRecord(
            full_hash="1" * 40, short_hash="1111111", author="Agent", email="a@a", date="2026-09-30",
            subject="c1", body="SpecOps-Task: TASK-0001\nProvenance: autonomous\nVerification: pass\n",
            trailers={"Provenance": "autonomous", "Verification": "pass"},
            task_ids=["TASK-0001"], is_autonomous=True, verification_status="pass",
        ),
        CommitRecord(
            full_hash="2" * 40, short_hash="2222222", author="Agent", email="a@a", date="2026-09-30",
            subject="c2", body="SpecOps-Task: TASK-0001\nProvenance: autonomous\nVerification: pass\n",
            trailers={"Provenance": "autonomous", "Verification": "pass"},
            task_ids=["TASK-0001"], is_autonomous=True, verification_status="pass",
        ),
        CommitRecord(
            full_hash="3" * 40, short_hash="3333333", author="Human", email="h@h", date="2026-09-30",
            subject="c3", body="SpecOps-Task: TASK-0003\n",
            trailers={}, task_ids=["TASK-0003"], is_autonomous=False,
        ),
    ]
    stats = compute_contributor_stats(commits, tasks)
    auto = stats["Autonomous Agents"]
    human = stats["Human Developers"]

    assert auto.tasks_delivered == 1
    assert auto.merged_commits == 2
    assert auto.verification_pass_rate == 100.0

    assert human.tasks_delivered == 1
    assert human.merged_commits == 1
    assert human.verification_pass_rate == 100.0


def test_compute_contributor_stats_explicit_rate_and_fails():
    """Tests explicit Pass-Rate trailer and fail ratio calculation."""
    tasks = [Task(id="TASK-0001", title="T1", status="Complete")]
    commits = [
        CommitRecord(
            full_hash="1" * 40, short_hash="1111111", author="Agent", email="a@a", date="2026-09-30",
            subject="c1", body="SpecOps-Task: TASK-0001\nPass-Rate: 93.3%\n",
            trailers={"Provenance": "autonomous", "Pass-Rate": "93.3%"},
            task_ids=["TASK-0001"], is_autonomous=True,
        )
    ]
    stats = compute_contributor_stats(commits, tasks)
    assert stats["Autonomous Agents"].verification_pass_rate == 93.3


def test_audit_provenance_full_integrity():
    """Tests audit report with 100% unbroken integrity."""
    data = ProjectData(
        personas=[Persona(id="p1", name="Jordan")],
        prds=[PRD(id="PRD-0001", title="PRD 1", target_persona="Jordan")],
        stories=[UserStory(id="US-0001", title="Story 1", governing_prd="PRD-0001")],
        tasks=[Task(id="TASK-0001", title="Task 1", status="Complete", governing_stories=["US-0001"])],
    )
    commit = CommitRecord(
        full_hash="1" * 40, short_hash="1111111", author="Dev", email="d@d", date="2026-09-30",
        subject="c1", body="SpecOps-Task: TASK-0001", task_ids=["TASK-0001"],
    )
    report = audit_provenance(data, [commit])
    assert report.total_commits == 1
    assert report.anchored_commits == 1
    assert len(report.unanchored_commits) == 0
    assert len(report.orphaned_tasks) == 0
    assert len(report.orphaned_stories) == 0
    assert report.integrity_pct == 100.0


def test_audit_provenance_flaws_detection():
    """Tests detection of unanchored commits, orphaned tasks, and missing tasks."""
    data = ProjectData(
        personas=[Persona(id="p1", name="Jordan")],
        prds=[PRD(id="PRD-0001", title="PRD 1", target_persona="Jordan")],
        stories=[UserStory(id="US-0001", title="Story 1", governing_prd="PRD-0001")],
        tasks=[Task(id="TASK-0001", title="Task 1", status="Complete", governing_stories=["US-0001"])],
    )
    unanchored = CommitRecord(
        full_hash="u" * 40, short_hash="uuuuuuu", author="Rogue", email="r@r", date="2026-09-30",
        subject="rogue", body="no trailer", task_ids=[],
    )
    missing_task_commit = CommitRecord(
        full_hash="m" * 40, short_hash="mmmmmmm", author="Dev", email="d@d", date="2026-09-30",
        subject="m", body="SpecOps-Task: TASK-9999", task_ids=["TASK-9999"],
    )

    report = audit_provenance(data, [unanchored, missing_task_commit])
    assert len(report.unanchored_commits) == 1
    assert report.unanchored_commits[0].short_hash == "uuuuuuu"
    assert len(report.missing_task_commits) == 1
    assert report.missing_task_commits[0][1] == "TASK-9999"
    assert len(report.orphaned_tasks) == 1
    assert report.orphaned_tasks[0] == "TASK-0001"
    assert report.integrity_pct < 100.0


def test_table_formatters():
    """Tests table string formatting functions."""
    stats = {
        "Autonomous Agents": ContributorStats(
            contributor_class="Autonomous Agents", tasks_delivered=14, merged_commits=28, verification_pass_rate=93.3
        ),
        "Human Developers": ContributorStats(
            contributor_class="Human Developers", tasks_delivered=9, merged_commits=15, verification_pass_rate=100.0
        ),
    }
    table = format_contributions_table(stats)
    assert "| Contributor Class   | Tasks Delivered | Merged Commits | Verification Pass Rate |" in table
    assert "| Autonomous Agents   | 14              | 28             | 93.3%                  |" in table
    assert "| Human Developers    | 9               | 15             | 100.0%                 |" in table

    empty_matrix = format_traceability_matrix_table([])
    assert "(no traceability records found)" in empty_matrix

    matrix = format_traceability_matrix_table([
        {"persona": "Jordan", "prd": "PRD-0005", "story": "US-0019", "task": "TASK-0075", "commit": "abc1234", "status": "Complete"}
    ])
    assert "Jordan" in matrix
    assert "PRD-0005" in matrix


def test_run_provenance_audit_cli_frontdoor(tmp_path: Path):
    """Tests run_provenance_audit CLI entrypoint logic."""
    (tmp_path / "docs" / "project" / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "project" / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "project" / "backlog" / "complete").mkdir(parents=True, exist_ok=True)

    config = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(repo=str(tmp_path), strict=False, contributions=True)
    exit_code = run_provenance_audit(args, config)
    assert exit_code == 0
