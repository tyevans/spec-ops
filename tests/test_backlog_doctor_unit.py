"""Comprehensive unit tests for src/spec_ops/backlog/doctor.py to maximize mutant kill rate under mutmut."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.backlog.doctor import (
    BacklogDefect,
    BacklogDoctor,
    BacklogDoctorReport,
    find_dependency_line,
    run_backlog_doctor,
)


def test_find_dependency_line_various_formats():
    """Tests line discovery for various frontmatter dependency formats."""
    # 1. Direct match on dependency item line
    doc1 = "---\nid: '0001'\ntitle: Task 1\ndependencies:\n  - TASK-9999\n---\n"
    assert find_dependency_line(doc1, "TASK-9999") == 5

    # 2. Inline list format
    doc2 = "---\nid: '0002'\ntitle: Task 2\ndependencies: [TASK-8888, TASK-7777]\n---\n"
    assert find_dependency_line(doc2, "TASK-8888") == 4
    assert find_dependency_line(doc2, "TASK-7777") == 4

    # 3. Numeric match
    doc3 = "---\nid: '0003'\ntitle: Task 3\ndependencies:\n  - 6543\n---\n"
    assert find_dependency_line(doc3, "TASK-6543") == 5

    # 4. Fallback to 1 if not present
    doc4 = "---\nid: '0004'\ntitle: Task 4\n---\n"
    assert find_dependency_line(doc4, "TASK-1111") == 1


def test_report_properties_and_to_dict():
    """Tests BacklogDoctorReport dataclass, properties, and serialization."""
    d1 = BacklogDefect(
        defect_type="dangling_dependency",
        task_id="TASK-0010",
        message="Dangling dep",
        file_path=Path("docs/task.md"),
        line_number=5,
        target_ref="TASK-9999",
        suggestion="Remove ref",
    )
    d2 = BacklogDefect(
        defect_type="ghost_index_entry",
        task_id="TASK-0020",
        message="Ghost entry",
        file_path=Path("docs/PRIORITY.md"),
        line_number=10,
        target_ref="proposed/0020.md",
    )
    d3 = BacklogDefect(
        defect_type="unindexed_task",
        task_id="TASK-0030",
        message="Unindexed",
        file_path=Path("docs/0030.md"),
    )
    d4 = BacklogDefect(
        defect_type="sync_drift",
        task_id="TASK-0040",
        message="Drift",
        file_path=Path("docs/PRIORITY.md"),
    )
    d5 = BacklogDefect(
        defect_type="broken_link",
        task_id="TASK-0050",
        message="Broken link",
        file_path=Path("docs/0050.md"),
    )

    report = BacklogDoctorReport(
        defects=[d1, d2, d3, d4, d5],
        remediations=["Fixed issue 1", "Fixed issue 2"],
        remediated_count=2,
    )

    assert not report.is_healthy
    assert report.dangling_dependencies == [d1]
    assert report.ghost_entries == [d2]
    assert report.unindexed_tasks == [d3]
    assert report.sync_drifts == [d4]
    assert report.broken_links == [d5]

    data = report.to_dict()
    assert data["is_healthy"] is False
    assert data["issues_count"] == 5
    assert data["remediated_count"] == 2
    assert len(data["defects"]) == 5
    assert data["defects"][0]["task_id"] == "TASK-0010"
    assert data["defects"][0]["suggestion"] == "Remove ref"


def test_doctor_on_empty_and_corrupted_directory(tmp_path: Path):
    """Tests doctor resilience when directory structure is missing or contains corrupt files."""
    empty_backlog = tmp_path / "empty_backlog"
    empty_backlog.mkdir()
    doctor = BacklogDoctor(empty_backlog)

    tasks = doctor.discover_disk_tasks()
    assert tasks == {}

    report = doctor.audit()
    assert report.is_healthy

    # Add corrupt/binary markdown file and hidden file
    proposed = empty_backlog / "proposed"
    proposed.mkdir()
    (proposed / ".hidden.md").write_text("hidden", encoding="utf-8")
    (proposed / "binary.md").write_bytes(b"\x80\x81\x82")

    tasks2 = doctor.discover_disk_tasks()
    assert len(tasks2) == 0


def test_audit_detects_sync_drift_and_broken_links(tmp_path: Path):
    """Tests auditing of status drift and relative broken markdown links."""
    backlog_dir = tmp_path / "backlog"
    for f in ("complete", "refined", "proposed"):
        (backlog_dir / f).mkdir(parents=True)

    # 1. Complete task on disk, but PRIORITY.md points to proposed
    task1 = backlog_dir / "complete" / "0001-setup.md"
    task1.write_text(
        "---\nid: '0001'\ntitle: Setup\nstatus: Complete\n---\n\n"
        "# Setup\nLink to [missing doc](non_existent_doc.md)\n"
        "Link to [external](https://example.com)\n",
        encoding="utf-8",
    )

    # 2. Refined task on disk with In-Progress status in PRIORITY.md (should be exempt from drift)
    task2 = backlog_dir / "refined" / "0002-feature.md"
    task2.write_text("---\nid: '0002'\ntitle: Feature\nstatus: Refined\n---\n\n# Feature\n", encoding="utf-8")

    priority_lines = [
        "# Backlog Priority Index",
        "",
        "- **TASK-0001 (Proposed)**: [`0001-setup`](proposed/0001-setup.md)",
        "- **TASK-0002 (In-Progress)**: [`0002-feature`](refined/0002-feature.md)",
    ]
    (backlog_dir / "PRIORITY.md").write_text("\n".join(priority_lines) + "\n", encoding="utf-8")

    doctor = BacklogDoctor(backlog_dir)
    report = doctor.audit()

    assert not report.is_healthy
    # Drift for TASK-0001
    assert len(report.sync_drifts) == 1
    assert report.sync_drifts[0].task_id == "TASK-0001"
    # Broken link for task1
    assert len(report.broken_links) == 1
    assert report.broken_links[0].target_ref == "non_existent_doc.md"


def test_fix_on_healthy_backlog_is_noop(tmp_path: Path):
    """Tests that calling fix() on an already healthy backlog does nothing."""
    backlog_dir = tmp_path / "backlog"
    for f in ("complete", "refined", "proposed"):
        (backlog_dir / f).mkdir(parents=True)

    task_file = backlog_dir / "complete" / "0001-task.md"
    task_file.write_text("---\nid: '0001'\ntitle: Task 1\nstatus: Complete\n---\n\n# Task 1\n", encoding="utf-8")

    (backlog_dir / "PRIORITY.md").write_text(
        "# Backlog Priority Index\n\n- **TASK-0001 (Complete)**: [`0001-task`](complete/0001-task.md)\n",
        encoding="utf-8",
    )

    doctor = BacklogDoctor(backlog_dir)
    report = doctor.fix()
    assert report.is_healthy
    assert report.remediated_count == 0
    assert len(report.remediations) == 0


def test_fix_creates_priority_file_if_missing(tmp_path: Path):
    """Tests that fix() initializes PRIORITY.md if it does not exist."""
    backlog_dir = tmp_path / "backlog"
    proposed = backlog_dir / "proposed"
    proposed.mkdir(parents=True)

    t = proposed / "0005-init.md"
    t.write_text("---\nid: '0005'\ntitle: Init\nstatus: Proposed\n---\n\n# Init\n", encoding="utf-8")

    doctor = BacklogDoctor(backlog_dir)
    assert not doctor.priority_file.exists()

    report = doctor.fix()
    assert report.is_healthy
    assert doctor.priority_file.exists()
    content = doctor.priority_file.read_text(encoding="utf-8")
    assert "TASK-0005" in content
    assert "proposed/0005-init.md" in content


def test_fix_handles_tasks_without_body(tmp_path: Path):
    """Tests fixing dangling dependencies when the markdown body is empty."""
    backlog_dir = tmp_path / "backlog"
    proposed = backlog_dir / "proposed"
    proposed.mkdir(parents=True)

    t = proposed / "0008-empty-body.md"
    t.write_text("---\nid: '0008'\ntitle: No Body\nstatus: Proposed\ndependencies:\n  - TASK-9999\n---\n", encoding="utf-8")

    (backlog_dir / "PRIORITY.md").write_text(
        f"# Backlog Priority Index\n\n- **TASK-0008 (Proposed)**: [`0008-empty-body`](proposed/0008-empty-body.md)\n",
        encoding="utf-8",
    )

    doctor = BacklogDoctor(backlog_dir)
    report = doctor.fix()
    assert report.is_healthy
    updated = t.read_text(encoding="utf-8")
    assert "TASK-9999" not in updated


def test_run_backlog_doctor_json_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Tests CLI entrypoint run_backlog_doctor in JSON mode."""
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir(parents=True)
    (backlog_dir / "proposed").mkdir()

    # 1. Clean run in JSON
    code = run_backlog_doctor(backlog_dir, fix=False, as_json=True)
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["is_healthy"] is True
    assert data["issues_count"] == 0

    # 2. Defect run in JSON
    t = backlog_dir / "proposed" / "0012-orphan.md"
    t.write_text("---\nid: '0012'\ntitle: Orphan\nstatus: Proposed\ndependencies:\n  - TASK-8888\n---\n\n# Orphan\n", encoding="utf-8")

    code2 = run_backlog_doctor(backlog_dir, fix=False, as_json=True)
    out2 = capsys.readouterr().out
    assert code2 == 1
    data2 = json.loads(out2)
    assert data2["is_healthy"] is False
    assert data2["issues_count"] >= 1

    # 3. Fix run in JSON
    code3 = run_backlog_doctor(backlog_dir, fix=True, as_json=True)
    out3 = capsys.readouterr().out
    assert code3 == 0
    data3 = json.loads(out3)
    assert data3["is_healthy"] is True
    assert data3["remediated_count"] >= 1


def test_run_backlog_doctor_human_mode_healthy_and_defects(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Tests CLI entrypoint human-readable printouts."""
    backlog_dir = tmp_path / "backlog"
    for f in ("complete", "refined", "proposed"):
        (backlog_dir / f).mkdir(parents=True)

    # Clean run
    code = run_backlog_doctor(backlog_dir, fix=False, as_json=False)
    out = capsys.readouterr().out
    assert code == 0
    assert "Backlog is healthy: 0 defects detected." in out

    # Add dangling dependency and ghost entry
    t = backlog_dir / "proposed" / "0015-dangling.md"
    t.write_text("---\nid: '0015'\ntitle: Dangling\nstatus: Proposed\ndependencies:\n  - TASK-7777\n---\n\n# Dangling\n", encoding="utf-8")
    (backlog_dir / "PRIORITY.md").write_text(
        "- **TASK-0015 (Proposed)**: [`0015-dangling`](proposed/0015-dangling.md)\n"
        "- **TASK-0099 (Proposed)**: [`0099-ghost`](proposed/0099-ghost.md)\n",
        encoding="utf-8",
    )

    code2 = run_backlog_doctor(backlog_dir, fix=False, as_json=False)
    out2 = capsys.readouterr().out
    assert code2 == 1
    assert "Backlog Defect: TASK-0015 references non-existent dependency 'TASK-7777'" in out2
    assert "Backlog Defect: PRIORITY.md lists reference to 'TASK-0099'" in out2
    assert "Warning: backlog synchronization drift detected." in out2

    # Run fix in human mode
    code3 = run_backlog_doctor(backlog_dir, fix=True, as_json=False)
    out3 = capsys.readouterr().out
    assert code3 == 0
    assert "Backlog self-healing complete: 2 issues remediated." in out3
