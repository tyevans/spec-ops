"""Unit tests and mutation coverage for burndown deck and milestone reporting (ADR-0009)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from spec_ops.cli.report_handler import handle_report_command
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.burndown_deck import (
    calculate_milestone_burndown,
    check_scope_alignment,
    export_burndown_deck,
    format_milestone_digest,
    parse_roadmap_milestones,
    render_presentation_deck,
)


def test_parse_roadmap_milestones_nonexistent(tmp_path: Path):
    """Tests roadmap parser on missing file."""
    res = parse_roadmap_milestones(tmp_path / "nonexistent.md")
    assert res == []


def test_parse_roadmap_milestones_structure(tmp_path: Path):
    """Tests roadmap parser on structured milestone headings and task lists."""
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone 1: Foundations (Complete)\n"
        "- Initial architecture spike (`TASK-0001`).\n"
        "- Profile registry (`TASK-0002`).\n"
        "- Milestone completion date: 2026-09-29\n\n"
        "## Milestone 2: Agent Worktrees (Active)\n"
        "- Autonomous runner (`TASK-0003`).\n"
        "- Target horizon: 2026-10-15\n",
        encoding="utf-8",
    )

    milestones = parse_roadmap_milestones(roadmap)
    assert len(milestones) == 2
    assert milestones[0]["id"] == "1"
    assert milestones[0]["title"] == "Foundations"
    assert milestones[0]["status"] == "Complete"
    assert milestones[0]["tasks"] == ["TASK-0001", "TASK-0002"]
    assert milestones[0]["horizon"] == "2026-09-29"

    assert milestones[1]["id"] == "2"
    assert milestones[1]["title"] == "Agent Worktrees"
    assert milestones[1]["status"] == "Active"
    assert milestones[1]["tasks"] == ["TASK-0003"]
    assert milestones[1]["horizon"] == "2026-10-15"


def test_burndown_calculations_and_digest(tmp_path: Path):
    """Tests milestone burndown velocity, persona value, and digest formatting."""
    repo = tmp_path / "calc_repo"
    init_project(repo, name="CalcTest")
    config = load_config(root_dir=repo)

    burndown = calculate_milestone_burndown("M1", config)
    assert burndown.milestone_id is not None
    assert burndown.total_tasks > 0
    assert burndown.completion_pct >= 0.0
    assert burndown.velocity_per_week > 0.0
    assert len(burndown.persona_value) == 5

    digest = format_milestone_digest(burndown)
    assert "# Executive Milestone Briefing:" in digest
    assert "Alex" in digest
    assert "Taylor" in digest
    assert "Frontdoor Tests" in digest
    assert "Mutation Kill Score" in digest


def test_export_burndown_deck(tmp_path: Path):
    """Tests file export in deck and digest formats."""
    repo = tmp_path / "export_repo"
    init_project(repo, name="ExportTest")
    config = load_config(root_dir=repo)

    out_deck = repo / "dist" / "test-deck.html"
    res1 = export_burndown_deck("M1-MVP", config, output_path=out_deck, format="deck")
    assert res1.exists()
    assert "<!DOCTYPE html>" in res1.read_text(encoding="utf-8")

    out_digest = repo / "dist" / "test-digest.md"
    res2 = export_burndown_deck("M1-MVP", config, output_path=out_digest, format="digest")
    assert res2.exists()
    assert "# Executive Milestone Briefing:" in res2.read_text(encoding="utf-8")


def test_cli_report_handler(tmp_path: Path):
    """Tests handle_report_command CLI handler."""
    repo = tmp_path / "cli_repo"
    init_project(repo, name="CLITest")
    config = load_config(root_dir=repo)
    parser = argparse.ArgumentParser()

    # 1. Burndown deck export
    args_deck = argparse.Namespace(
        report_action="burndown",
        milestone="M1",
        format="deck",
        output=str(repo / "dist" / "cli-deck.html"),
        check_alignment=False,
    )
    rc1 = handle_report_command(args_deck, config, parser)
    assert rc1 == 0
    assert (repo / "dist" / "cli-deck.html").exists()

    # 2. Scope alignment
    args_align = argparse.Namespace(
        report_action="milestone",
        milestone="M1",
        format="digest",
        output=None,
        check_alignment=True,
    )
    rc2 = handle_report_command(args_align, config, parser)
    assert rc2 == 0

    # 3. Milestone digest
    args_digest = argparse.Namespace(
        report_action="milestone",
        milestone="M1",
        format="digest",
        output=None,
        check_alignment=False,
    )
    rc3 = handle_report_command(args_digest, config, parser)
    assert rc3 == 0
