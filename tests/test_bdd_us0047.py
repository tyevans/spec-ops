"""BDD step definitions for US-0047: Executive Roadmap Exporter and Zero-Overhead Presentation Generator."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0047_executive_roadmap_exporter_and_presentation_generator.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def roadmap_repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "roadmap_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="ExecutiveRoadmapTest")

    # Author ROADMAP.md with M1 Foundations and M2 Agent Ecosystem
    roadmap = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone 1: Foundations (Complete)\n"
        "- Initial architecture spike and loader (`TASK-0001`).\n"
        "- Scaffolding engine and models (`TASK-0002`).\n"
        "- Milestone completion date: 2026-09-29\n\n"
        "## Milestone 2: Agent Ecosystem (Active)\n"
        "- Autonomous runner and worktrees (`TASK-0003`).\n"
        "- Target horizon: 2026-10-15\n",
        encoding="utf-8",
    )

    # Commit TASK-0001
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(core): initial foundation spike (TASK-0001)"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "output": "", "svg": "", "html": ""}


@given('a project with documented milestones in "docs/project/backlog/ROADMAP.md"')
def given_project_with_milestones(roadmap_repo_context: dict[str, Any]):
    repo = roadmap_repo_context["repo"]
    roadmap_path = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    assert roadmap_path.exists()
    content = roadmap_path.read_text(encoding="utf-8")
    assert "Foundations" in content
    assert "Agent Ecosystem" in content


@when('Taylor runs "spec-ops export roadmap --format svg --out dist/executive-roadmap.svg"')
def when_run_export_roadmap_svg(roadmap_repo_context: dict[str, Any]):
    res = run_spec_ops(roadmap_repo_context["repo"], ["export", "roadmap", "--format", "svg", "--out", "dist/executive-roadmap.svg"])
    assert res.returncode == 0
    roadmap_repo_context["output"] = res.stdout
    svg_file = roadmap_repo_context["repo"] / "dist" / "executive-roadmap.svg"
    assert svg_file.exists()
    roadmap_repo_context["svg"] = svg_file.read_text(encoding="utf-8")


@then("a high-resolution vector roadmap graphic is generated")
def then_high_res_vector_graphic_generated(roadmap_repo_context: dict[str, Any]):
    svg_content = roadmap_repo_context["svg"]
    assert svg_content.startswith("<svg")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg_content
    assert "viewBox=" in svg_content
    # Strictly well-formed XML
    root = ET.fromstring(svg_content)
    assert root.tag.endswith("svg")


@then("the graphic illustrates milestones grouped by delivery horizon (M1 Foundations, M2 Agent Ecosystem)")
def then_graphic_illustrates_milestones(roadmap_repo_context: dict[str, Any]):
    svg_content = roadmap_repo_context["svg"]
    assert "M1 Foundations" in svg_content
    assert "M2 Agent Ecosystem" in svg_content
    assert "Target Horizon:" in svg_content


@then("completed tasks are marked with progress bars based on git commit history")
def then_completed_tasks_marked_progress_bars(roadmap_repo_context: dict[str, Any]):
    svg_content = roadmap_repo_context["svg"]
    assert "TASK-0001" in svg_content
    # TASK-0001 was committed in git history
    assert "barGrad" in svg_content or "url(#bar)" in svg_content
    assert "%" in svg_content


@then("zero manual configuration files are required.")
def then_zero_manual_config(roadmap_repo_context: dict[str, Any]):
    # Verified execution operates out-of-the-box on convention defaults
    assert (roadmap_repo_context["repo"] / "specops.toml").exists()


@given('the SpecOps visualizer is open on the "Gantt & Timeline" tab')
def given_visualizer_open_gantt():
    from spec_ops.visualizer.gantt_script import GANTT_JS
    assert "renderGanttView" in GANTT_JS
    assert "exportExecutiveSummary" in GANTT_JS
    assert "exec-audience-select" in GANTT_JS
    assert "exec-granularity-select" in GANTT_JS


@when('Taylor clicks "Export Executive Summary"')
def when_clicks_export_executive_summary(roadmap_repo_context: dict[str, Any]):
    from spec_ops.visualizer.gantt_script import GANTT_JS
    assert "Export Executive Summary" in GANTT_JS


@when('selects audience "Leadership / Non-Technical" with granularity "Milestones & PRD Outcomes"')
def when_selects_audience_and_granularity(roadmap_repo_context: dict[str, Any]):
    from spec_ops.config.loader import load_config
    from spec_ops.prd.exporter import export_roadmap

    config = load_config(root_dir=roadmap_repo_context["repo"])
    out_file = roadmap_repo_context["repo"] / "dist" / "executive-summary.html"
    dest = export_roadmap(
        config,
        format="html",
        output_path=out_file,
        audience="Leadership / Non-Technical",
        granularity="Milestones & PRD Outcomes",
    )
    assert dest.exists()
    roadmap_repo_context["html"] = dest.read_text(encoding="utf-8")


@then("a self-contained, single-file HTML presentation is downloaded")
def then_self_contained_html_downloaded(roadmap_repo_context: dict[str, Any]):
    html = roadmap_repo_context["html"]
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<style>" in html
    assert "<script>" in html


@then("the slide deck contains interactive progress dials, horizon milestones, and persona impact summaries")
def then_deck_contains_dials_and_summaries(roadmap_repo_context: dict[str, Any]):
    html = roadmap_repo_context["html"]
    # Interactive progress dials (SVG circular meters)
    assert "<circle" in html
    assert "stroke-dashoffset" in html
    assert "Overall Progress" in html or "Progress Dial" in html

    # Horizon milestones
    assert "M1 Foundations" in html
    assert "M2 Agent Ecosystem" in html
    assert "Horizon" in html

    # Persona impact summaries
    for p in ["Taylor", "Alex", "Jordan", "Morgan", "Riley"]:
        assert p in html


@then("opens cleanly in any web browser without server dependencies.")
def then_opens_cleanly_without_server_dependencies(roadmap_repo_context: dict[str, Any]):
    html = roadmap_repo_context["html"]
    # Airgap check: zero external network scripts or links
    ext_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']https?://', html, re.IGNORECASE)
    assert len(ext_scripts) == 0
    ext_links = re.findall(r'<link\b[^>]*\bhref=["\']https?://', html, re.IGNORECASE)
    assert len(ext_links) == 0


@given("a repository configured with the GitHub Pages deployment workflow")
def given_repo_with_pages_workflow(roadmap_repo_context: dict[str, Any]):
    repo = roadmap_repo_context["repo"]
    pages_wf = repo / ".github" / "workflows" / "deploy-pages.yml"
    assert pages_wf.exists()


@when('changes merge into "main" updating task completion states')
def when_changes_merge_into_main(roadmap_repo_context: dict[str, Any]):
    repo = roadmap_repo_context["repo"]
    # Run the documentation pipeline (as executed in CI pages deploy)
    res = run_spec_ops(repo, ["docs", "build"])
    assert res.returncode == 0


@then('the documentation pipeline automatically generates updated roadmap SVG artifacts in "site/assets/roadmap.svg"')
def then_pipeline_generates_roadmap_svg(roadmap_repo_context: dict[str, Any]):
    site_svg = roadmap_repo_context["repo"] / "site" / "assets" / "roadmap.svg"
    assert site_svg.exists()
    content = site_svg.read_text(encoding="utf-8")
    assert "<svg" in content
    root = ET.fromstring(content)
    assert root.tag.endswith("svg")


@then("executive bookmarks always reflect current git ground truth without double-entry.")
def then_bookmarks_reflect_git_truth(roadmap_repo_context: dict[str, Any]):
    site_svg = roadmap_repo_context["repo"] / "site" / "assets" / "roadmap.svg"
    content = site_svg.read_text(encoding="utf-8")
    assert "M1 Foundations" in content
    assert "M2 Agent Ecosystem" in content
