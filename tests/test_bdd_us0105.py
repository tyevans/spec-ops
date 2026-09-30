"""BDD step definitions for US-0105: Executive Milestone Burndown and Multi-Format Presentation Deck Exporter."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0105_executive_milestone_burndown_deck.feature")

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
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "test_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="ExecReporting")

    # Author ROADMAP.md
    roadmap = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone M1-MVP: Core Foundations (Active)\n"
        "- Architecture spike and configuration (`TASK-0001`).\n"
        "- Profile registry and baseline ADRs (`TASK-0002`).\n"
        "- Living reporting and slide deck exporter (`TASK-0074`).\n"
        "- Target horizon: 2026-10-30\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial specs"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "output": "", "html": "", "download_filename": ""}


@given('a project repository with documented milestones in "docs/project/backlog/ROADMAP.md"')
def given_project_repo_with_milestones(repo_context: dict[str, Any]):
    assert (repo_context["repo"] / "docs" / "project" / "backlog" / "ROADMAP.md").exists()


@when('Taylor runs "spec-ops report milestone --milestone M1-MVP --format digest"')
def when_run_report_milestone(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["report", "milestone", "--milestone", "M1-MVP", "--format", "digest"])
    assert res.returncode == 0
    repo_context["output"] = res.stdout


@then("the CLI outputs a clean executive briefing containing:")
def then_briefing_contains_items(repo_context: dict[str, Any], docstring: str):
    out = repo_context["output"]
    assert "M1-MVP" in out or "Foundations" in out
    assert "%" in out
    for persona in ["Alex", "Jordan", "Morgan", "Riley", "Taylor"]:
        assert persona in out
    assert "frontdoor" in out.lower() or "tests" in out.lower()
    assert "mutation" in out.lower()
    assert "deliverables" in out.lower() or "horizon" in out.lower()


@then("the output is formatted cleanly with Markdown tables and bulleted highlights for email or Slack distribution.")
def then_formatted_cleanly(repo_context: dict[str, Any]):
    out = repo_context["output"]
    assert "| Persona | Role |" in out or "|---|" in out
    assert "- **Frontdoor Tests**:" in out or "- **Mutation Kill Score**:" in out


@given('the visualizer is loaded on the "Gantt & Timeline" tab')
def given_visualizer_loaded(repo_context: dict[str, Any]):
    from spec_ops.visualizer.gantt_script import GANTT_JS
    assert "renderGanttView" in GANTT_JS
    assert "exportPresentationDeck" in GANTT_JS


@when('Taylor clicks "Export Presentation Deck" and selects milestone "M1-MVP"')
def when_export_presentation_deck(repo_context: dict[str, Any]):
    from spec_ops.config.loader import load_config
    from spec_ops.visualizer.burndown_deck import export_burndown_deck

    config = load_config(root_dir=repo_context["repo"])
    out_file = repo_context["repo"] / "dist" / "m1-mvp-executive-briefing.html"
    res_path = export_burndown_deck("M1-MVP", config, output_path=out_file, format="deck")

    repo_context["download_filename"] = res_path.name
    repo_context["html"] = res_path.read_text(encoding="utf-8")


@then('the browser initiates a download of a single-file HTML presentation "m1-mvp-executive-briefing.html"')
def then_browser_initiates_download(repo_context: dict[str, Any]):
    assert repo_context["download_filename"] == "m1-mvp-executive-briefing.html"
    assert (repo_context["repo"] / "dist" / "m1-mvp-executive-briefing.html").exists()


@then("the downloaded presentation contains:")
def then_presentation_contains_items(repo_context: dict[str, Any], docstring: str):
    html = repo_context["html"]
    # 1. Executive overview slide with interactive radial progress meters
    assert 'data-slide="1"' in html
    assert "Executive Overview" in html
    assert "<svg" in html and "circle" in html
    # 2. Visual delivery horizon Gantt timeline
    assert 'data-slide="2"' in html
    assert "Gantt Timeline" in html or "Delivery Horizon" in html
    # 3. Persona value delivered matrix
    assert 'data-slide="3"' in html
    assert "Persona Value Delivered Matrix" in html
    for p in ["Alex", "Jordan", "Morgan", "Riley", "Taylor"]:
        assert p in html
    # 4. Codebase health metrics
    assert 'data-slide="4"' in html
    assert "Health" in html
    assert "0" in html and ("<500 lines" in html or "&lt;500 lines" in html)
    assert "100%" in html


@then("the slide deck presents cleanly with keyboard slide navigation (Arrow keys / Spacebar) and zero external network calls.")
def then_slide_deck_navigation_and_airgap(repo_context: dict[str, Any]):
    html = repo_context["html"]
    assert "ArrowRight" in html or "ArrowLeft" in html or "keydown" in html
    ext_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']https?://', html, re.IGNORECASE)
    assert len(ext_scripts) == 0
    ext_links = re.findall(r'<link\b[^>]*\bhref=["\']https?://', html, re.IGNORECASE)
    assert len(ext_links) == 0


@given('3 completed tasks in the backlog that are not associated with any milestone in "ROADMAP.md"')
def given_unanchored_tasks(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    comp_dir = repo / "docs" / "project" / "backlog" / "complete"
    comp_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, 4):
        tid = f"TASK-009{i}"
        file_path = comp_dir / f"{tid.lower()}-unanchored-feature-{i}.md"
        file_path.write_text(
            f"---\nid: '009{i}'\ntitle: Unanchored Task {i}\nstatus: Complete\ntarget_bc: core\n---\n\n# {tid}\n",
            encoding="utf-8",
        )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: add completed unanchored tasks"], cwd=repo, check=True, capture_output=True)


@when('Taylor runs "spec-ops report milestone --check-alignment"')
def when_run_check_alignment(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["report", "milestone", "--check-alignment"])
    assert res.returncode == 0
    repo_context["output"] = res.stdout


@then('the report flags an alert: "⚠️ Scope Alignment Warning: 3 completed tasks unanchored from ROADMAP.md"')
def then_alert_flagged(repo_context: dict[str, Any]):
    out = repo_context["output"]
    assert "⚠️ Scope Alignment Warning: 3 completed tasks unanchored from ROADMAP.md" in out


@then("provides a table listing the unanchored tasks, their target bounded contexts, and authoring commits.")
def then_table_provided(repo_context: dict[str, Any]):
    out = repo_context["output"]
    assert "TASK-0091" in out
    assert "TASK-0092" in out
    assert "TASK-0093" in out
    assert "core" in out
