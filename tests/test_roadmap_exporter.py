"""Unit tests and mutation coverage for executive roadmap visualizer and exporter (ADR-0009)."""

from __future__ import annotations

import argparse
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from spec_ops.cli.export_handler import handle_export_command
from spec_ops.config.loader import load_config
from spec_ops.prd.exporter import (
    RoadmapMilestone,
    calculate_progress,
    export_roadmap,
    load_roadmap_milestones,
    parse_roadmap_file,
    render_roadmap_html,
    render_roadmap_svg,
)
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.gantt_script import GANTT_JS


def test_calculate_progress():
    """Tests calculation of completion percentages across boundary conditions."""
    assert calculate_progress(0, 0) == 0.0
    assert calculate_progress(5, 0) == 0.0
    assert calculate_progress(-2, 10) == 0.0
    assert calculate_progress(0, 10) == 0.0
    assert calculate_progress(1, 3) == 33.3
    assert calculate_progress(2, 3) == 66.7
    assert calculate_progress(10, 10) == 100.0
    assert calculate_progress(15, 10) == 150.0


def test_parse_roadmap_file_nonexistent(tmp_path: Path):
    """Tests parsing a missing ROADMAP.md file."""
    res = parse_roadmap_file(tmp_path / "nonexistent.md")
    assert res == []


def test_parse_roadmap_file_headings_and_tasks(tmp_path: Path):
    """Tests parsing structured milestone headings, task IDs, and horizons."""
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone 1: Foundations (Complete)\n"
        "- Initial architecture spike (`TASK-0001`).\n"
        "- Scaffolding engine and models (`TASK-0002`).\n"
        "- Milestone completion date: 2026-09-29\n\n"
        "## Milestone 2: Agent Ecosystem (Active)\n"
        "- Autonomous runner and worktrees (`TASK-0003`).\n"
        "- Target horizon: 2026-10-15\n"
        "- Second task (`TASK-0004`).\n\n"
        "## Milestone M3: Web PRD Studio (Planned)\n"
        "- Interactive studio (`TASK-0005`).\n"
        "- Horizon closed for PRD-0003: 2026-11-01\n",
        encoding="utf-8",
    )

    milestones = parse_roadmap_file(roadmap)
    assert len(milestones) == 3

    assert milestones[0]["id"] == "M1"
    assert milestones[0]["display_name"] == "M1 Foundations"
    assert milestones[0]["title"] == "Foundations"
    assert milestones[0]["status"] == "Complete"
    assert milestones[0]["tasks"] == ["TASK-0001", "TASK-0002"]
    assert milestones[0]["horizon"] == "2026-09-29"

    assert milestones[1]["id"] == "M2"
    assert milestones[1]["display_name"] == "M2 Agent Ecosystem"
    assert milestones[1]["title"] == "Agent Ecosystem"
    assert milestones[1]["status"] == "Active"
    assert milestones[1]["tasks"] == ["TASK-0003", "TASK-0004"]
    assert milestones[1]["horizon"] == "2026-10-15"

    assert milestones[2]["id"] == "M3"
    assert milestones[2]["display_name"] == "M3 Web PRD Studio"
    assert milestones[2]["title"] == "Web PRD Studio"
    assert milestones[2]["status"] == "Planned"
    assert milestones[2]["tasks"] == ["TASK-0005"]
    assert milestones[2]["horizon"] == "2026-11-01"


def test_load_roadmap_milestones_with_git_and_disk(tmp_path: Path):
    """Tests load_roadmap_milestones integrating git commits and complete/ directory."""
    repo = tmp_path / "test_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="RoadmapTest")
    roadmap = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap.write_text(
        "## Milestone 1: Core (Active)\n- Task (`TASK-0001`).\n- Task (`TASK-0002`).\n",
        encoding="utf-8",
    )

    # Make commit for TASK-0001
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: implement TASK-0001"], cwd=repo, check=True, capture_output=True)

    # Place TASK-0002 into complete/
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    (complete_dir / "0002-task.md").write_text("---\nid: '0002'\nstatus: Complete\n---\n", encoding="utf-8")

    config = load_config(root_dir=repo)
    milestones = load_roadmap_milestones(config)

    assert len(milestones) == 1
    m = milestones[0]
    assert m.id == "M1"
    assert len(m.tasks) == 2
    assert "TASK-0001" in m.completed_tasks
    assert "TASK-0002" in m.completed_tasks
    assert m.progress_pct == 100.0
    assert "TASK-0001" in m.task_commits
    assert m.task_commits["TASK-0002"] == "HEAD"


def test_render_roadmap_svg_structure_and_limits():
    """Tests SVG rendering with chip truncation and visual elements."""
    tasks = [f"TASK-{i:04d}" for i in range(1, 12)]
    commits = {f"TASK-{i:04d}": f"abc{i:04d}" for i in range(1, 7)}
    m = RoadmapMilestone(
        id="M1",
        display_name="M1 Foundations",
        title="Foundations",
        status="Complete",
        horizon="2026-09-29",
        tasks=tasks,
        completed_tasks=tasks[:6],
        progress_pct=54.5,
        task_commits=commits,
    )

    svg = render_roadmap_svg([m], project_name="SpecOps Test")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "M1 Foundations" in svg
    assert "54.5%" in svg
    assert "Target Horizon: 2026-09-29" in svg
    # Mini task chip limit of 6
    assert "TASK-0001 (abc0001)" in svg
    assert "TASK-0006 (abc0006)" in svg
    assert "TASK-0007" not in svg  # Beyond top 6 chips


def test_render_roadmap_html_presentation():
    """Tests HTML presentation rendering, dials, and slides."""
    m = RoadmapMilestone(
        id="M1",
        display_name="M1 Foundations",
        title="Foundations",
        status="Active",
        horizon="2026-10-15",
        tasks=["TASK-0001", "TASK-0002"],
        completed_tasks=["TASK-0001"],
        progress_pct=50.0,
        task_commits={"TASK-0001": "1a2b3c4"},
    )

    html_doc = render_roadmap_html(
        [m],
        audience="Leadership / Non-Technical",
        granularity="Milestones & PRD Outcomes",
    )
    assert "<!DOCTYPE html>" in html_doc
    assert "Leadership / Non-Technical" in html_doc
    assert "Milestones &amp; PRD Outcomes" in html_doc
    assert "M1 Foundations" in html_doc
    assert "50.0%" in html_doc
    assert "Taylor" in html_doc
    assert "Alex" in html_doc
    assert "Jordan" in html_doc
    assert "Morgan" in html_doc
    assert "Riley" in html_doc


def test_export_roadmap_file_modes(tmp_path: Path):
    """Tests export_roadmap function writing SVG and HTML files."""
    repo = tmp_path / "export_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="ExportTestApp")
    config = load_config(root_dir=repo)

    # 1. Export SVG with default path
    svg_default = export_roadmap(config, format="svg")
    assert svg_default.exists()
    assert svg_default.name == "roadmap.svg"
    assert "<svg" in svg_default.read_text(encoding="utf-8")

    # 2. Export HTML with custom path
    html_custom = repo / "out" / "custom-deck.html"
    res_html = export_roadmap(config, format="html", output_path=html_custom)
    assert res_html.exists()
    assert res_html == html_custom
    assert "<!DOCTYPE html>" in res_html.read_text(encoding="utf-8")


def test_cli_handle_export_command(tmp_path: Path):
    """Tests handle_export_command CLI integration."""
    repo = tmp_path / "cli_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="CLIExportTest")
    config = load_config(root_dir=repo)
    parser = argparse.ArgumentParser()

    # 1. Export roadmap SVG
    out_svg = repo / "dist" / "cli-roadmap.svg"
    args_svg = argparse.Namespace(
        command="export",
        export_action="roadmap",
        format="svg",
        output=str(out_svg),
        audience="Leadership / Non-Technical",
        granularity="Milestones & PRD Outcomes",
    )
    rc_svg = handle_export_command(args_svg, config, parser)
    assert rc_svg == 0
    assert out_svg.exists()

    # 2. Export roadmap HTML
    out_html = repo / "dist" / "cli-roadmap.html"
    args_html = argparse.Namespace(
        command="export",
        export_action="roadmap",
        format="html",
        output=str(out_html),
        audience="Engineering / Technical",
        granularity="Backlog Tasks",
    )
    rc_html = handle_export_command(args_html, config, parser)
    assert rc_html == 0
    assert out_html.exists()


def test_visualizer_gantt_script_summary_exporter():
    """Tests that visualizer GANTT_JS script contains executive summary exporter and UI hooks."""
    assert "exportExecutiveSummary" in GANTT_JS
    assert "exec-audience-select" in GANTT_JS
    assert "exec-granularity-select" in GANTT_JS
    assert "Export Executive Summary" in GANTT_JS
    assert "executive-summary.html" in GANTT_JS
    assert "Progress Dial" in GANTT_JS
    assert "Persona Impact Summaries" in GANTT_JS


def test_cli_handle_export_fallback_and_defaults(tmp_path: Path):
    """Tests handle_export_command defaults and unknown action help dispatch."""
    from spec_ops.cli.parser import build_parser

    repo = tmp_path / "cli_defaults"
    init_project(repo, name="CLIDefaults")
    config = load_config(root_dir=repo)
    parser = build_parser()

    # 1. Action is None -> defaults to roadmap
    args_none = argparse.Namespace(
        command="export",
        export_action=None,
        format=None,
        output=str(repo / "dist" / "def.svg"),
        audience=None,
        granularity=None,
    )
    rc1 = handle_export_command(args_none, config, parser)
    assert rc1 == 0
    assert (repo / "dist" / "def.svg").exists()

    # 2. Unknown action -> catches SystemExit from parser --help
    args_unknown = argparse.Namespace(
        command="export",
        export_action="invalid_target",
    )
    with pytest.raises(SystemExit):
        handle_export_command(args_unknown, config, parser)


def test_render_roadmap_svg_empty_and_active():
    """Tests SVG rendering on empty milestones and active milestones."""
    # Empty
    svg_empty = render_roadmap_svg([], project_name="EmptyProject")
    assert "<svg" in svg_empty
    root = ET.fromstring(svg_empty)
    assert root.tag.endswith("svg")

    # Active status with progress < 100
    m = RoadmapMilestone(
        id="M1",
        display_name="M1 InFlight",
        title="InFlight",
        status="Active",
        horizon="2026-12-01",
        tasks=["TASK-0010"],
        completed_tasks=[],
        progress_pct=0.0,
        task_commits={},
    )
    svg_active = render_roadmap_svg([m], project_name="ActiveProject")
    assert "#38bdf8" in svg_active  # active status color
    assert "0.0%" in svg_active
    assert "TASK-0010" in svg_active


def test_load_roadmap_milestones_non_numeric_complete(tmp_path: Path):
    """Tests load_roadmap_milestones ignoring non-task markdown files in complete/."""
    repo = tmp_path / "load_repo"
    init_project(repo, name="LoadRepo")
    comp_dir = repo / "docs" / "project" / "backlog" / "complete"
    comp_dir.mkdir(parents=True, exist_ok=True)
    # Write a file without numeric prefix
    (comp_dir / "README.md").write_text("# Complete directory\n", encoding="utf-8")

    roadmap = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap.write_text("## Milestone 1: Test\n- Unfinished (`TASK-0099`).\n", encoding="utf-8")

    config = load_config(root_dir=repo)
    milestones = load_roadmap_milestones(config)
    assert len(milestones) == 1
    assert milestones[0].completed_tasks == []
    assert milestones[0].progress_pct == 0.0
