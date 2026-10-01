"""BDD step definitions for US-0049: Automated Customer-Facing Release Notes and Business Value Changelog Generator."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0049_release_notes.feature")

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

    init_project(repo, name="ReleaseNotesApp")

    # Author ROADMAP.md
    roadmap = repo / "docs" / "project" / "backlog" / "ROADMAP.md"
    roadmap.write_text(
        "# Delivery Roadmap\n\n"
        "## Milestone 1: Foundations (Complete)\n"
        "- Initial architecture spike and system foundation (`TASK-0001`).\n"
        "- Universal Markdown parser and relational graph (`TASK-0004`).\n"
        "- Zero-dependency interactive 2D graph visualizer (`TASK-0008`).\n\n"
        "- Milestone completion date: 2026-09-29 (Horizon closed for PRD-0001 — SpecOps Autonomous Project Management Engine).\n",
        encoding="utf-8",
    )

    # Shipped PRD-0001
    shipped_dir = repo / "docs" / "project" / "product" / "shipped"
    shipped_dir.mkdir(parents=True, exist_ok=True)
    prd_file = shipped_dir / "prd-0001-autonomous-engine.md"
    prd_file.write_text(
        """---
id: '0001'
title: SpecOps Autonomous Project Management Engine
status: Shipped
target_persona: Taylor (The Product Manager)
component: core
---

# PRD-0001 — SpecOps Autonomous Project Management Engine

## What good looks like

1. **Specification as Code (PMaC)**:
   - Personas, PRDs, User Stories, Backlog Tasks, and ADRs live as Markdown with YAML frontmatter under `docs/project/`.
2. **Living 2D Graph Visualizer**:
   - Zero-dependency canvas visualizing directional relationships and health metrics with standalone HTML export.

## Checkable Outcomes

1. Visualizer renders 2D canvas.
""",
        encoding="utf-8",
    )

    # Accepted User Story US-0001
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    story_file = stories_dir / "us-0001-project-init.md"
    story_file.write_text(
        """---
id: '0001'
title: Project Initialization with Architectural Profiles
status: Accepted
persona: Taylor (The Product Manager)
feature: FEAT-CORE-01
governing_prd: PRD-0001
---

# US-0001 — Project Initialization with Architectural Profiles

## User Story

**As an** product manager,  
**I want** to bootstrap new projects with baseline ADRs,  
**So that** project specifications are version-locked in git.

## Acceptance Criteria

```gherkin
Scenario: Bootstrapping a New Repository
Given a blank project directory
When the engineer executes "spec-ops init"
Then the directory structure is created
```
""",
        encoding="utf-8",
    )

    # PERSONAS.md
    personas_file = repo / "docs" / "project" / "user_stories" / "PERSONAS.md"
    personas_file.write_text(
        """# SpecOps User Personas

---

## 5. Taylor — The Product Manager
- **Role**: Product manager owning product outcomes and customer discovery.
- **Pain Points**:
  - High friction and terminal-command intimidation.
- **Goals with SpecOps**:
  - Clear user acceptance testing (UAT) workflows and visual PRD lifecycle tracking.
  - Direct traceability from business outcomes to executable Gherkin scenarios without writing raw code.

---
""",
        encoding="utf-8",
    )

    # Completed Tasks: 1 spike, 1 feature
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)

    task_spike = complete_dir / "0001-architecture-spike.md"
    task_spike.write_text(
        """---
id: '0001'
title: Initial Architecture Spike and System Foundation
status: Complete
slice_type: spike
hypothesis: Graph parsing runs sub-50ms
governing_prds:
- PRD-0001
governing_stories:
- US-0001
target_bc: core
---
# TASK-0001: Spike
""",
        encoding="utf-8",
    )

    task_feat = complete_dir / "0004-universal-parser.md"
    task_feat.write_text(
        """---
id: '0004'
title: Universal Markdown parser and relational graph
status: Complete
slice_type: feat
governing_prds:
- PRD-0001
governing_stories:
- US-0001
target_bc: core
---
# TASK-0004: Universal Parser
""",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup initial specs and tasks\n\nSpecOps-Task: TASK-0001\nSpecOps-Slice: chore"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "spike: experiment with cache\n\nSpecOps-Task: TASK-0001\nSpecOps-Slice: spike"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "feat: implement markdown parser\n\nSpecOps-Task: TASK-0004\nSpecOps-Slice: feat"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "output": "", "html": ""}


@given('a completed milestone "Milestone 1: Foundations" in "ROADMAP.md" with linked PRDs and stories')
def given_completed_milestone(repo_context: dict[str, Any]) -> None:
    repo = repo_context["repo"]
    assert (repo / "docs" / "project" / "backlog" / "ROADMAP.md").is_file()
    assert (repo / "docs" / "project" / "product" / "shipped" / "prd-0001-autonomous-engine.md").is_file()


@when('Taylor executes "spec-ops release notes --milestone M1 --format markdown"')
def when_execute_release_notes_markdown(repo_context: dict[str, Any]) -> None:
    res = run_spec_ops(repo_context["repo"], ["release", "notes", "--milestone", "M1", "--format", "markdown"])
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    repo_context["output"] = res.stdout


@then('a release notes document is generated at "docs/reference/release-notes-m1.md"')
def then_release_notes_generated_at_path(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "reference" / "release-notes-m1.md"
    assert dest.is_file(), f"Expected release notes file at {dest}"


@then("the content categorizes changes by customer-visible outcome:")
def then_content_categorizes_changes(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "reference" / "release-notes-m1.md"
    content = dest.read_text(encoding="utf-8")

    assert "## New Capabilities" in content
    assert "Specification as Code (PMaC)" in content
    assert "Living 2D Graph Visualizer" in content

    assert "## User Scenarios Added" in content
    assert "US-0001" in content
    assert "Bootstrapping a New Repository" in content

    assert "## Persona Impacts" in content
    assert "Taylor" in content
    assert "Clear user acceptance testing (UAT) workflows" in content


@then("internal developer refactors and invisible spike commits are excluded.")
def then_internal_chores_and_spikes_excluded(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "reference" / "release-notes-m1.md"
    content = dest.read_text(encoding="utf-8")

    assert "TASK-0001" not in content
    assert "Initial Architecture Spike" not in content
    assert "chore:" not in content
    assert "spike:" not in content
    assert "refactor:" not in content


@given("generated release notes for an accepted release")
def given_generated_release_notes_for_accepted_release(repo_context: dict[str, Any]) -> None:
    # Ensure markdown release notes already ran or exist
    run_spec_ops(repo_context["repo"], ["release", "notes", "--milestone", "M1", "--format", "markdown"])
    dest = repo_context["repo"] / "docs" / "reference" / "release-notes-m1.md"
    assert dest.is_file()


@when('Taylor runs "spec-ops release notes --milestone M1 --format html --branded"')
def when_run_release_notes_html_branded(repo_context: dict[str, Any]) -> None:
    res = run_spec_ops(repo_context["repo"], ["release", "notes", "--milestone", "M1", "--format", "html", "--branded"])
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    repo_context["html"] = res.stdout


@then("a styled, standalone HTML email template is created")
def then_styled_standalone_html_template_created(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "reference" / "release-notes-m1.html"
    assert dest.is_file(), f"Expected HTML file at {dest}"
    html_content = dest.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content
    assert "SpecOps Release" in html_content
    assert "New Capabilities" in html_content
    assert "Persona Impacts" in html_content


@then("links each new capability directly to the live GitHub Pages documentation and visualizer permalink.")
def then_links_each_new_capability_to_pages_and_permalink(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "reference" / "release-notes-m1.html"
    html_content = dest.read_text(encoding="utf-8")

    # Links directly to Live GitHub Pages documentation
    assert "Live GitHub Pages Documentation" in html_content
    assert "https://specops.github.io/spec-ops/docs/prd-0001" in html_content

    # Links directly to Visualizer permalink
    assert "Visualizer Permalink" in html_content
    assert "https://specops.github.io/spec-ops/visualizer/#tab=prds&amp;entity=PRD-0001" in html_content or "#tab=prds" in html_content


@given('a shipped PRD "PRD-0001" with verified checkable outcomes and linked persona "Taylor"')
def given_shipped_prd_with_outcomes_and_taylor(repo_context: dict[str, Any]) -> None:
    repo = repo_context["repo"]
    prd_file = repo / "docs" / "project" / "product" / "shipped" / "prd-0001-autonomous-engine.md"
    assert prd_file.is_file()
    content = prd_file.read_text(encoding="utf-8")
    assert "target_persona: Taylor" in content
    assert "## Checkable Outcomes" in content


@when('the product lead executes "spec-ops release notes PRD-0001"')
def when_execute_release_notes_prd(repo_context: dict[str, Any]) -> None:
    res = run_spec_ops(repo_context["repo"], ["release", "notes", "PRD-0001"])
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    repo_context["prd_notes_output"] = res.stdout


@then("customer-facing release notes are generated")
def then_customer_facing_release_notes_generated(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "releases" / "prd-0001-release-notes.md"
    assert dest.is_file(), f"Expected release notes file at {dest}"
    content = dest.read_text(encoding="utf-8")
    assert "# Release Notes:" in content
    assert "PRD-0001" in content


@then("the notes group changes by target persona benefits without internal git commit jargon")
def then_notes_group_by_persona_without_jargon(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "releases" / "prd-0001-release-notes.md"
    content = dest.read_text(encoding="utf-8")
    assert "## Target Persona Benefits" in content
    assert "Taylor" in content
    assert "chore:" not in content
    assert "spike:" not in content
    assert "refactor:" not in content
    assert "TASK-0001" not in content


@given('a shipped PRD "PRD-0001"')
def given_shipped_prd(repo_context: dict[str, Any]) -> None:
    repo = repo_context["repo"]
    prd_file = repo / "docs" / "project" / "product" / "shipped" / "prd-0001-autonomous-engine.md"
    assert prd_file.is_file()


@when('the user runs "spec-ops release notes PRD-0001 --format html"')
def when_run_release_notes_prd_html(repo_context: dict[str, Any]) -> None:
    res = run_spec_ops(repo_context["repo"], ["release", "notes", "PRD-0001", "--format", "html"])
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    repo_context["prd_html"] = res.stdout


@then("a standalone HTML release announcement is produced")
def then_standalone_html_produced(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "releases" / "prd-0001-release-notes.html"
    assert dest.is_file(), f"Expected HTML file at {dest}"
    html_content = dest.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content
    assert "Release Announcement:" in html_content
    assert "PRD-0001" in html_content


@then("includes verifiable customer UAT checkmarks")
def then_includes_verifiable_customer_uat_checkmarks(repo_context: dict[str, Any]) -> None:
    dest = repo_context["repo"] / "docs" / "releases" / "prd-0001-release-notes.html"
    assert dest.is_file(), f"Expected HTML file at {dest}"
    html_content = dest.read_text(encoding="utf-8")
    assert "Verifiable Customer UAT Checkmarks" in html_content
    assert "✓ Verified UAT" in html_content
