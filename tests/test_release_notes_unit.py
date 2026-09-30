"""Unit tests for release notes generator module (src/spec_ops/prd/release_notes.py)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import CommitInfo, Persona, ProjectData, Task, UserStory
from spec_ops.prd.release_notes import (
    CapabilityItem,
    PersonaBenefit,
    ReleaseNotesData,
    StorySummary,
    build_release_notes_data,
    extract_persona_benefits,
    extract_story_scenarios,
    extract_what_good_looks_like,
    generate_release_notes,
    is_chore_or_spike_commit,
    is_chore_or_spike_task,
    milestone_slug,
    render_html_release_notes,
    render_markdown_release_notes,
)
from spec_ops.cli.release_handler import handle_release_command


def test_milestone_slug():
    assert milestone_slug("M1") == "m1"
    assert milestone_slug("m2") == "m2"
    assert milestone_slug("Milestone 10: Launch") == "m10"
    assert milestone_slug("alpha-release") == "alpha-release"
    assert milestone_slug("   ") == "m1"


def test_is_chore_or_spike_task():
    # Slice type branches
    for st in ["chore", "spike", "refactor", "internal", "test"]:
        assert is_chore_or_spike_task(Task(id="0001", title="Title", slice_type=st)) is True

    # ID starting with SPIKE
    assert is_chore_or_spike_task(Task(id="SPIKE-0001", title="Feat Title", slice_type="feat")) is True

    # Hypothesis presence
    assert is_chore_or_spike_task(Task(id="0002", title="Feat Title", slice_type="feat", hypothesis="Something")) is True

    # Title keywords
    assert is_chore_or_spike_task(Task(id="0003", title="chore: clean dependencies", slice_type="feat")) is True
    assert is_chore_or_spike_task(Task(id="0004", title="Spike on caching", slice_type="feat")) is True
    assert is_chore_or_spike_task(Task(id="0005", title="refactor models", slice_type="feat")) is True

    # Clean feature task
    assert is_chore_or_spike_task(Task(id="0006", title="Implement visualizer canvas", slice_type="feat")) is False


def test_is_chore_or_spike_commit():
    # Subject prefixes
    for prefix in ["chore: update deps", "spike: test hypothesis", "refactor: split files", "test: add tests"]:
        c = CommitInfo(hash="abc", author="Taylor", date="2026-09-30", subject=prefix)
        assert is_chore_or_spike_commit(c) is True

    # Subject keyword
    c_kw = CommitInfo(hash="abc", author="Taylor", date="2026-09-30", subject="Major refactor of pipeline")
    assert is_chore_or_spike_commit(c_kw) is True

    # Trailer
    c_trailer = CommitInfo(hash="abc", author="Taylor", date="2026-09-30", subject="Update", trailers={"SpecOps-Slice": "chore"})
    assert is_chore_or_spike_commit(c_trailer) is True

    # Clean commit
    clean_c = CommitInfo(hash="abc", author="Taylor", date="2026-09-30", subject="feat: deliver release notes generator")
    assert is_chore_or_spike_commit(clean_c) is False


def test_extract_what_good_looks_like():
    # Empty / missing
    assert extract_what_good_looks_like("") == []
    assert extract_what_good_looks_like("# No section here") == []

    # Valid markdown
    md = """# PRD-0001
## What good looks like

1. **Feature Alpha**:
   - First bullet point details.
   - Second bullet point details.
2. **Feature Beta**:
   - Description beta.

## What this does not do
"""
    items = extract_what_good_looks_like(md)
    assert len(items) == 2
    assert items[0][0] == "Feature Alpha"
    assert "First bullet point details." in items[0][1]
    assert items[1][0] == "Feature Beta"


def test_extract_persona_benefits():
    # From goals attribute
    p1 = Persona(id="alex", name="Alex", goals=["Goal 1", "Goal 2", "---", "--"])
    benefits = extract_persona_benefits(p1)
    assert benefits == ["Goal 1", "Goal 2"]

    # From raw_markdown
    p2 = Persona(
        id="jordan",
        name="Jordan",
        raw_markdown="## 2. Jordan\n- **Goals with SpecOps**:\n  - Better velocity\n  - Clean frontdoors\n  - --\n",
    )
    b2 = extract_persona_benefits(p2)
    assert b2 == ["Better velocity", "Clean frontdoors"]

    # Empty
    p3 = Persona(id="nobody", name="Nobody")
    assert extract_persona_benefits(p3) == []


def test_extract_story_scenarios():
    # From scenarios list
    s1 = UserStory(id="US-0001", title="Title", scenarios=["Scenario A", "Scenario B"])
    assert extract_story_scenarios(s1) == ["Scenario A", "Scenario B"]

    # From raw markdown
    s2 = UserStory(
        id="US-0002",
        title="Title",
        raw_markdown="### Scenario 1: Setup\n### Scenario: Teardown\n",
    )
    assert extract_story_scenarios(s2) == ["Setup", "Teardown"]

    # From i_want fallback
    s3 = UserStory(id="US-0003", title="Title", as_a="developer", i_want="to run tests")
    assert extract_story_scenarios(s3) == ["As a developer, I want to run tests"]


def test_render_markdown_release_notes():
    # Full data
    notes = ReleaseNotesData(
        milestone_id="M1",
        milestone_title="Foundations",
        capabilities=[
            CapabilityItem(prd_id="PRD-0001", prd_title="Engine", title="Cap 1", description="Desc 1"),
            CapabilityItem(prd_id="PRD-0002", prd_title="Security", title="Cap 2", description="Desc 2"),
        ],
        stories=[
            StorySummary(id="US-0001", title="Story 1", scenarios=["Sc 1"]),
        ],
        personas=[
            PersonaBenefit(name="Taylor", role="Product Manager", benefits=["Benefit 1"]),
        ],
    )
    md = render_markdown_release_notes(notes)
    assert "# Release Notes: Foundations" in md
    assert "## New Capabilities" in md
    assert "### PRD-0001: Engine" in md
    assert "- **Cap 1**: Desc 1" in md
    assert "### PRD-0002: Security" in md
    assert "## User Scenarios Added" in md
    assert "### US-0001: Story 1" in md
    assert "- Scenario: Sc 1" in md
    assert "## Persona Impacts" in md
    assert "### Taylor — Product Manager" in md
    assert "- Benefit 1" in md

    # Empty data
    empty_notes = ReleaseNotesData(milestone_id="M0", milestone_title="Empty")
    empty_md = render_markdown_release_notes(empty_notes)
    assert "Foundations and baseline stability enhancements." in empty_md
    assert "Core system verification scenarios." in empty_md
    assert "Accelerated autonomous delivery loops" in empty_md


def test_render_html_release_notes():
    notes = ReleaseNotesData(
        milestone_id="M1",
        milestone_title="Milestone M1",
        capabilities=[
            CapabilityItem(
                prd_id="PRD-0001",
                prd_title="Engine",
                title="Canvas",
                description="2D canvas",
                doc_url="https://specops.github.io/spec-ops/docs/prd-0001",
                visualizer_permalink="https://specops.github.io/spec-ops/visualizer/#tab=prds&entity=PRD-0001",
            )
        ],
        stories=[StorySummary(id="US-0001", title="Story 1", scenarios=["Scenario A"])],
        personas=[PersonaBenefit(name="Alex", role="", benefits=["Zero conflict"])],
    )
    # Branded
    html_branded = render_html_release_notes(notes, branded=True)
    assert "SpecOps Release" in html_branded
    assert "Live GitHub Pages Documentation" in html_branded
    assert "Visualizer Permalink" in html_branded
    assert "Alex" in html_branded

    # Unbranded
    html_unbranded = render_html_release_notes(notes, branded=False)
    assert "Release Notes: Milestone M1" in html_unbranded
    assert "SpecOps Release" not in html_unbranded

    # Empty notes HTML
    empty_notes = ReleaseNotesData(milestone_id="M0", milestone_title="Empty")
    empty_html = render_html_release_notes(empty_notes, branded=False)
    assert "No new capabilities recorded." in empty_html
    assert "No new user scenarios recorded." in empty_html
    assert "No persona impacts recorded." in empty_html


def test_generate_release_notes_and_cli_handler(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    docs_dir = repo / "docs" / "project"
    docs_dir.mkdir(parents=True)
    (repo / "docs" / "reference").mkdir(parents=True)
    
    config = SpecOpsConfig(root_dir=repo)
    config.project.docs_dir = "docs/project"

    # Markdown generation
    dest_md, content_md = generate_release_notes("M1", config, format_type="markdown")
    assert dest_md.name == "release-notes-m1.md"
    assert dest_md.exists()
    assert "# Release Notes:" in content_md

    # HTML generation with custom output path
    custom_html = repo / "custom" / "notes.html"
    dest_html, content_html = generate_release_notes("M1", config, format_type="html", branded=True, output_path=custom_html)
    assert dest_html == custom_html
    assert dest_html.exists()
    assert "<!DOCTYPE html>" in content_html

    # CLI handler tests
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    p_rel = sub.add_parser("release")
    rel_sub = p_rel.add_subparsers(dest="release_action")
    p_notes = rel_sub.add_parser("notes")
    p_notes.add_argument("--milestone")
    p_notes.add_argument("--format", default="markdown")
    p_notes.add_argument("--branded", action="store_true")
    p_notes.add_argument("--output", default=None)

    # Missing milestone -> error
    args_bad = parser.parse_args(["release", "notes"])
    assert handle_release_command(args_bad, config, parser) == 1

    # Invalid action -> error
    args_invalid = argparse.Namespace(release_action="unknown", milestone="M1")
    assert handle_release_command(args_invalid, config, parser) == 1

    # Success markdown
    args_ok_md = argparse.Namespace(release_action="notes", milestone="M1", format="markdown", branded=False, output=None)
    assert handle_release_command(args_ok_md, config, parser) == 0

    # Success html
    args_ok_html = argparse.Namespace(release_action="notes", milestone="M1", format="html", branded=True, output=str(custom_html))
    assert handle_release_command(args_ok_html, config, parser) == 0
