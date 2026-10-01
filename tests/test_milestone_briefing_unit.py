"""Unit tests for executive milestone briefing and roadmap alignment (TASK-0081)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from spec_ops.backlog.milestone_briefing import (
    MilestoneBriefing,
    audit_milestone_scope,
    export_milestone_briefing,
    generate_milestone_briefing,
    render_briefing_html,
    render_briefing_markdown,
)
from spec_ops.cli.parser import build_parser
from spec_ops.cli.report_handler import handle_report_command
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="BriefingTest")

    # Author ROADMAP.md
    roadmap = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone M1-MVP: Core Foundations (Active)\n"
        "- Initial setup (`TASK-0001`).\n"
        "- Baseline ADRs (`TASK-0002`).\n"
        "- Executive briefing generator (`TASK-0081`).\n"
        "- Target horizon: 2026-10-30\n",
        encoding="utf-8",
    )

    # Add a completed task for M1
    comp_dir = repo / "docs" / "project" / "backlog" / "complete"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "0001-setup.md").write_text(
        "---\nid: '0001'\ntitle: Initial setup\nstatus: Complete\ngoverning_prds:\n- PRD-0001\ntarget_bc: core\n---\n# TASK-0001\n",
        encoding="utf-8",
    )

    # Add a refined remaining task for M1 with dependencies
    ref_dir = repo / "docs" / "project" / "backlog" / "refined"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "0081-briefing.md").write_text(
        "---\nid: '0081'\ntitle: Executive briefing generator\nstatus: Refined\ndependencies:\n- TASK-0002\ngoverning_prds:\n- PRD-0005\ntarget_bc: backlog\n---\n# TASK-0081\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup test repo"], cwd=repo, check=True, capture_output=True)
    return repo


def test_generate_milestone_briefing(test_repo: Path):
    config = load_config(root_dir=test_repo)
    briefing = generate_milestone_briefing("M1-MVP", config)

    assert briefing.milestone_id == "M1-MVP"
    assert "Core Foundations" in briefing.title
    assert briefing.target_date == "2026-10-30"
    assert briefing.total_tasks >= 2
    assert briefing.completed_tasks >= 1
    assert 0.0 <= briefing.completion_pct <= 100.0
    assert len(briefing.critical_path_items) > 0
    assert any("TASK-0081" in item for item in briefing.critical_path_items)
    assert any("TASK-0002" in risk for risk in briefing.risk_factors)


def test_audit_milestone_scope_detection(test_repo: Path):
    config = load_config(root_dir=test_repo)
    # Initially no unanchored tasks
    count, unanchored = audit_milestone_scope(config)
    assert count == 0

    # Introduce an unanchored completed task
    comp_dir = test_repo / "docs" / "project" / "backlog" / "complete"
    (comp_dir / "0099-unanchored.md").write_text(
        "---\nid: '0099'\ntitle: Rogue Feature\nstatus: Complete\ntarget_bc: rogue\n---\n# TASK-0099\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=test_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: rogue task"], cwd=test_repo, check=True, capture_output=True)

    count2, unanchored2 = audit_milestone_scope(config)
    assert count2 == 1
    assert unanchored2[0]["id"] == "TASK-0099"
    assert unanchored2[0]["target_bc"] == "rogue"


def test_render_briefing_html_and_markdown(test_repo: Path):
    config = load_config(root_dir=test_repo)
    briefing = generate_milestone_briefing("M1-MVP", config)

    # HTML
    html = render_briefing_html(briefing)
    assert html.startswith("<!DOCTYPE html>")
    assert "<svg" in html and "circle" in html
    assert f"{briefing.completion_pct}%" in html
    assert "http://" not in html and "https://" not in html

    # Markdown
    md = render_briefing_markdown(briefing)
    assert f"# Executive Milestone Briefing: {briefing.title}" in md
    assert f"**Progress**: {briefing.completion_pct}%" in md
    assert "Critical Path Items:" in md


def test_export_milestone_briefing_files(test_repo: Path):
    config = load_config(root_dir=test_repo)
    briefing = generate_milestone_briefing("M1-MVP", config)

    # Default export HTML
    out_html = export_milestone_briefing(briefing, export_format="html", config=config)
    assert out_html.exists()
    assert out_html.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")

    # Custom export Markdown
    custom_md = test_repo / "dist" / "briefing.md"
    out_md = export_milestone_briefing(briefing, export_format="markdown", output_path=custom_md, config=config)
    assert out_md == custom_md
    assert custom_md.exists()
    assert "# Executive Milestone Briefing" in custom_md.read_text(encoding="utf-8")


def test_handle_report_command_cli(test_repo: Path, capsys: pytest.CaptureFixture[str]):
    config = load_config(root_dir=test_repo)
    parser = build_parser()

    # 1. Positional milestone execution
    args1 = parser.parse_args(["report", "milestone", "M1-MVP"])
    rc1 = handle_report_command(args1, config, parser)
    assert rc1 == 0
    captured1 = capsys.readouterr().out
    assert "Executive Milestone Briefing" in captured1
    assert "M1-MVP" in captured1

    # 2. Scope audit with clean repo
    args2 = parser.parse_args(["report", "milestone", "--audit-scope"])
    rc2 = handle_report_command(args2, config, parser)
    assert rc2 == 0
    captured2 = capsys.readouterr().out
    assert "All completed tasks are anchored" in captured2

    # 3. Export HTML with -o
    out_path = test_repo / "dist" / "one-pager.html"
    args3 = parser.parse_args(["report", "milestone", "M1-MVP", "--export", "html", "-o", str(out_path)])
    rc3 = handle_report_command(args3, config, parser)
    assert rc3 == 0
    assert out_path.exists()
    assert "<!DOCTYPE html>" in out_path.read_text(encoding="utf-8")

    # 4. Export markdown with --out
    out_md = test_repo / "dist" / "summary.md"
    args4 = parser.parse_args(["report", "milestone", "--milestone", "M1-MVP", "--export", "markdown", "--out", str(out_md)])
    rc4 = handle_report_command(args4, config, parser)
    assert rc4 == 0
    assert out_md.exists()
    assert "Executive Milestone Briefing" in out_md.read_text(encoding="utf-8")
