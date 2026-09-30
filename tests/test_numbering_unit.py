"""Blackbox frontdoor unit tests for artifact numbering uniqueness verification (ADRs, PRDs, Tasks, Stories)."""

from __future__ import annotations

import json
from pathlib import Path

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.core.numbering import (
    NumberingAuditReport,
    audit_numbering_uniqueness,
    extract_numbers_for_file,
)


def test_repository_numbering_integrity():
    """Validates that the current repository contains zero duplicate numbers across all artifact groups."""
    config = load_config(Path.cwd())
    report = audit_numbering_uniqueness(config)

    assert report.is_valid, f"Unexpected collisions found: {report.format_diagnostics()}"
    assert len(report.collisions) == 0
    assert report.entity_counts.get("adrs", 0) >= 20
    assert report.entity_counts.get("prds", 0) >= 5
    assert report.entity_counts.get("tasks", 0) >= 100
    assert report.entity_counts.get("stories", 0) >= 100
    assert "✅ Numbering Invariant Met" in report.format_diagnostics()


def test_duplicate_adr_detected(tmp_path: Path):
    """Detects duplicate numbers in the ADR group."""
    adrs_dir = tmp_path / "docs" / "project" / "adrs"
    adrs_dir.mkdir(parents=True)

    (adrs_dir / "adr-0011-first.md").write_text("# ADR-0011: First ADR\n\nContent", encoding="utf-8")
    (adrs_dir / "adr-0011-second.md").write_text("# ADR-0011: Duplicate ADR\n\nContent", encoding="utf-8")

    report = audit_numbering_uniqueness(tmp_path)
    assert not report.is_valid
    assert len(report.collisions) == 1
    col = report.collisions[0]
    assert col.group == "adrs"
    assert col.canonical_id == "ADR-0011"
    assert len(col.paths) == 2
    assert "ADR-0011 duplicated across 2 files" in report.format_diagnostics()


def test_duplicate_prd_detected(tmp_path: Path):
    """Detects duplicate numbers in the PRD group across different lifecycle folders."""
    accepted = tmp_path / "docs" / "project" / "product" / "accepted"
    shipped = tmp_path / "docs" / "project" / "product" / "shipped"
    accepted.mkdir(parents=True)
    shipped.mkdir(parents=True)

    (accepted / "prd-0003-active.md").write_text("---\nid: '0003'\ntitle: Active\n---\n# PRD-0003: Active", encoding="utf-8")
    (shipped / "prd-0003-old.md").write_text("---\nid: 3\ntitle: Old\n---\n# PRD-0003: Old", encoding="utf-8")

    report = audit_numbering_uniqueness(tmp_path)
    assert not report.is_valid
    assert len(report.collisions) == 1
    col = report.collisions[0]
    assert col.group == "prds"
    assert col.canonical_id == "PRD-0003"


def test_duplicate_task_detected(tmp_path: Path):
    """Detects duplicate task numbers across complete and refined backlog buffers."""
    complete = tmp_path / "docs" / "project" / "backlog" / "complete"
    refined = tmp_path / "docs" / "project" / "backlog" / "refined"
    complete.mkdir(parents=True)
    refined.mkdir(parents=True)

    (complete / "0053-spike.md").write_text("---\nid: '0053'\ntitle: Spike\n---\n# TASK-0053", encoding="utf-8")
    (refined / "0053-feature.md").write_text("---\nid: 'TASK-0053'\ntitle: Feat\n---\n# TASK-0053", encoding="utf-8")

    report = audit_numbering_uniqueness(tmp_path)
    assert not report.is_valid
    assert len(report.collisions) == 1
    assert report.collisions[0].canonical_id == "TASK-0053"


def test_duplicate_user_story_detected(tmp_path: Path):
    """Detects duplicate user story numbers."""
    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True)

    (stories_dir / "us-0089-failure-memory.md").write_text("---\nid: '0089'\ntitle: A\n---\n# US-0089", encoding="utf-8")
    (stories_dir / "us-0089-conflict.md").write_text("---\nid: '0089'\ntitle: B\n---\n# US-0089", encoding="utf-8")

    report = audit_numbering_uniqueness(tmp_path)
    assert not report.is_valid
    assert len(report.collisions) == 1
    assert report.collisions[0].canonical_id == "US-0089"


def test_cross_group_identical_numbers_do_not_collide(tmp_path: Path):
    """Ensures identical numbers in different groups (e.g. ADR-0001, PRD-0001, TASK-0001, US-0001) are isolated."""
    docs = tmp_path / "docs" / "project"
    (docs / "adrs" / "accepted").mkdir(parents=True)
    (docs / "product" / "accepted").mkdir(parents=True)
    (docs / "backlog" / "complete").mkdir(parents=True)
    (docs / "user_stories" / "accepted").mkdir(parents=True)

    (docs / "adrs" / "accepted" / "adr-0001-spec.md").write_text("# ADR-0001: Spec", encoding="utf-8")
    (docs / "product" / "accepted" / "prd-0001-spec.md").write_text("---\nid: '0001'\n---\n# PRD-0001", encoding="utf-8")
    (docs / "backlog" / "complete" / "0001-spec.md").write_text("---\nid: '0001'\n---\n# TASK-0001", encoding="utf-8")
    (docs / "user_stories" / "accepted" / "us-0001-spec.md").write_text("---\nid: '0001'\n---\n# US-0001", encoding="utf-8")

    report = audit_numbering_uniqueness(tmp_path)
    assert report.is_valid
    assert len(report.collisions) == 0
    assert report.entity_counts == {"adrs": 1, "prds": 1, "tasks": 1, "stories": 1}


def test_ignored_files_do_not_trigger_collisions(tmp_path: Path):
    """Verifies standard non-entity files (REGISTRY.md, README.md, etc.) are excluded from audit."""
    docs = tmp_path / "docs" / "project"
    (docs / "adrs").mkdir(parents=True)
    (docs / "adrs" / "REGISTRY.md").write_text("# ADR Registry\n| ID | Title |\n", encoding="utf-8")
    (docs / "adrs" / "README.md").write_text("# Readme\n", encoding="utf-8")
    (docs / "backlog" / "PRIORITY.md").parent.mkdir(parents=True)
    (docs / "backlog" / "PRIORITY.md").write_text("# Priority\n", encoding="utf-8")

    report = audit_numbering_uniqueness(tmp_path)
    assert report.is_valid
    assert report.checked_files == 0


def test_cli_health_numbering_clean(capsys):
    """Exercises CLI spec-ops health --numbering on clean repository."""
    exit_code = main(["health", "--numbering"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "✅ Numbering Invariant Met" in captured.out


def test_cli_health_numbering_json(capsys):
    """Exercises CLI spec-ops health --numbering --json on clean repository."""
    exit_code = main(["health", "--numbering", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    assert data["is_valid"] is True
    assert data["collision_count"] == 0
    assert "adrs" in data["entity_counts"]
