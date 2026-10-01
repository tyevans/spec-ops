"""BDD step definitions for US-0023: Automated Executive Milestone Briefing and Roadmap Alignment Digest."""

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

scenarios("features/us_0023_executive_milestone_briefing.feature")

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
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="ExecBriefingRepo")

    roadmap = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone M1-MVP: Core Foundations (Active)\n"
        "- Initial architecture spike (`TASK-0001`).\n"
        "- Profile registry and baseline ADRs (`TASK-0002`).\n"
        "- Executive briefing generator (`TASK-0081`).\n"
        "- Target horizon: 2026-10-30\n",
        encoding="utf-8",
    )

    # 1. Complete task
    comp_dir = repo / "docs" / "project" / "backlog" / "complete"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "0001-setup.md").write_text(
        "---\nid: '0001'\ntitle: Initial architecture spike\nstatus: Complete\ngoverning_prds:\n- PRD-0001\ntarget_bc: core\n---\n# TASK-0001\n",
        encoding="utf-8",
    )

    # 2. Refined remaining task
    ref_dir = repo / "docs" / "project" / "backlog" / "refined"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "0081-briefing.md").write_text(
        "---\nid: '0081'\ntitle: Executive briefing generator\nstatus: Refined\ndependencies:\n- TASK-0002\ngoverning_prds:\n- PRD-0005\ntarget_bc: backlog\n---\n# TASK-0081\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup repo and tasks"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "output": "", "html": ""}


@given('an accepted roadmap milestone "M1-MVP" in "docs/project/backlog/ROADMAP.md"')
def given_accepted_roadmap_milestone(repo_context: dict[str, Any]):
    roadmap = repo_context["repo"] / "docs" / "project" / "backlog" / "ROADMAP.md"
    assert roadmap.exists()
    assert "M1-MVP" in roadmap.read_text(encoding="utf-8")


@given("linked PRDs, user stories, and tasks with varying completion statuses")
def given_linked_entities_with_statuses(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    assert (repo / "docs" / "project" / "backlog" / "complete" / "0001-setup.md").exists()
    assert (repo / "docs" / "project" / "backlog" / "refined" / "0081-briefing.md").exists()


@when('the lead runs "spec-ops report milestone M1-MVP"')
def when_run_report_milestone_m1(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["report", "milestone", "M1-MVP"])
    assert res.returncode == 0
    repo_context["output"] = res.stdout


@then("the command outputs an executive briefing containing:")
def then_outputs_briefing_containing(repo_context: dict[str, Any]):
    out = repo_context["output"]
    assert "M1-MVP" in out
    assert "%" in out
    for persona in ["Alex", "Jordan", "Morgan"]:
        assert persona in out
    assert "frontdoor" in out.lower() or "tests" in out.lower()
    assert "mutation" in out.lower()
    assert "critical path" in out.lower() or "deliverables" in out.lower()
    assert "risk" in out.lower() or "blocked" in out.lower()


@then("formats the summary cleanly for direct pasting into Slack, email, or executive slide decks.")
def then_formats_cleanly(repo_context: dict[str, Any]):
    out = repo_context["output"]
    assert "| Persona | Role |" in out or "|---|" in out
    assert "- **Frontdoor Tests**:" in out


@given("tasks completed on feature branches that are not linked to any milestone in ROADMAP.md")
def given_unanchored_completed_tasks(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    comp_dir = repo / "docs" / "project" / "backlog" / "complete"
    for i in range(1, 4):
        tid = f"TASK-009{i}"
        (comp_dir / f"{tid.lower()}-unanchored-{i}.md").write_text(
            f"---\nid: '009{i}'\ntitle: Rogue Feature {i}\nstatus: Complete\ntarget_bc: telemetry\n---\n# {tid}\n",
            encoding="utf-8",
        )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add 3 unanchored completed tasks"], cwd=repo, check=True, capture_output=True)


@when('the lead runs "spec-ops report milestone --audit-scope"')
def when_run_report_milestone_audit_scope(repo_context: dict[str, Any]):
    res = run_spec_ops(repo_context["repo"], ["report", "milestone", "--audit-scope"])
    assert res.returncode == 0
    repo_context["output"] = res.stdout


@then('the command reports "Roadmap Alignment Warning: 3 completed tasks have no milestone association"')
def then_reports_alignment_warning(repo_context: dict[str, Any]):
    out = repo_context["output"]
    assert "Roadmap Alignment Warning: 3 completed tasks have no milestone association" in out


@then("lists the unanchored tasks and their target bounded contexts.")
def then_lists_unanchored_tasks(repo_context: dict[str, Any]):
    out = repo_context["output"]
    assert "TASK-0091" in out
    assert "TASK-0092" in out
    assert "TASK-0093" in out
    assert "telemetry" in out


@given("milestone progress data")
def given_milestone_progress_data(repo_context: dict[str, Any]):
    assert (repo_context["repo"] / "docs" / "project" / "backlog" / "ROADMAP.md").exists()


@when('the lead runs "spec-ops report milestone M1-MVP --export html -o dist/briefing.html"')
def when_run_report_milestone_export_html(repo_context: dict[str, Any]):
    res = run_spec_ops(
        repo_context["repo"],
        ["report", "milestone", "M1-MVP", "--export", "html", "-o", "dist/briefing.html"],
    )
    assert res.returncode == 0
    repo_context["output"] = res.stdout


@then("a self-contained, responsive HTML briefing document is generated")
def then_html_document_generated(repo_context: dict[str, Any]):
    dest = repo_context["repo"] / "dist" / "briefing.html"
    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    assert "</html>" in content
    repo_context["html"] = content


@then("includes visual progress rings, persona impact quotes, and delivery horizon timelines with zero CDN dependencies.")
def then_html_features_verified(repo_context: dict[str, Any]):
    html = repo_context["html"]
    # 1. Visual progress rings
    assert "<svg" in html and "circle" in html
    assert "%" in html
    # 2. Persona impact quotes
    for p in ["Alex", "Jordan", "Morgan"]:
        assert p in html
    # 3. Delivery horizon timelines
    assert "2026-10-30" in html
    # 4. Zero CDN dependencies
    ext_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']https?://', html, re.IGNORECASE)
    assert len(ext_scripts) == 0
    ext_links = re.findall(r'<link\b[^>]*\bhref=["\']https?://', html, re.IGNORECASE)
    assert len(ext_links) == 0
