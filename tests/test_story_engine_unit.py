"""Unit tests for story engine and story CLI handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from spec_ops.cli.story_handler import handle_story_command
from spec_ops.config.loader import load_config
from spec_ops.core.parser import extract_frontmatter
from spec_ops.core.story_engine import StoryEngine
from spec_ops.core.story_models import (
    StoryScaffoldResult,
    StoryTraceItem,
    StoryTraceReport,
    normalize_story_id,
    slugify_story_title,
)
from spec_ops.scaffold.init import init_project


@pytest.fixture
def repo_env(tmp_path: Path):
    init_project(tmp_path, name="TestStoryRepo")
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0006.md").write_text(
        "---\n"
        "id: '0006'\n"
        "title: Orchestrator Engine\n"
        "status: Accepted\n"
        "target_persona: Jordan (The AI-Native Engineering Lead)\n"
        "component: core\n"
        "---\n"
        "# PRD-0006 — Orchestrator Engine\n",
        encoding="utf-8",
    )
    return tmp_path


def test_slugify_and_normalize():
    assert slugify_story_title("Multi-Faceted BDD User Story Generation") == "multi-faceted-bdd-user-story-generation"
    assert slugify_story_title("   Spaces   &   Special $ Characters!   ") == "spaces-special-characters"
    assert slugify_story_title("") == "story"

    assert normalize_story_id("1", "US") == "US-0001"
    assert normalize_story_id("US-0042", "US") == "US-0042"
    assert normalize_story_id("prd-6", "PRD") == "PRD-0006"
    assert normalize_story_id("custom", "US") == "CUSTOM"


def test_get_next_story_number(repo_env: Path):
    engine = StoryEngine(repo_env)
    initial_next = engine.get_next_story_number()
    assert initial_next >= 1

    # Create story 0050 in accepted
    stories_dir = repo_env / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0050-sample.md").write_text("# US-0050\n", encoding="utf-8")

    assert engine.get_next_story_number() == 51


def test_create_story_dry_run(repo_env: Path):
    engine = StoryEngine(repo_env)
    res = engine.create_story(
        title="Simulated Story",
        prd="PRD-0006",
        persona="Jordan",
        bc="worker",
        dry_run=True,
    )
    assert res.dry_run is True
    assert res.registry_updated is False
    assert not res.file_path.exists()
    assert "US-" in res.id
    assert "Scenario:" in res.content
    assert "Jordan" in res.content


def test_create_story_writes_file_and_registry(repo_env: Path):
    engine = StoryEngine(repo_env)
    res = engine.create_story(
        title="Real Multi-Faceted Story",
        prd="PRD-0006",
        persona="Alex (The Agentic Systems Architect)",
        bc="core",
        story_id="US-0010",
        feature="FEAT-ORCH-01",
        scenarios=["Scenario A", "Scenario B"],
        dry_run=False,
    )
    assert res.dry_run is False
    assert res.registry_updated is True
    assert res.file_path.is_file()

    content = res.file_path.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)
    assert meta["id"] == "0010"
    assert meta["title"] == "Real Multi-Faceted Story"
    assert meta["status"] == "Accepted"
    assert meta["persona"] == "Alex (The Agentic Systems Architect)"
    assert meta["target_bc"] == "core"
    assert meta["governing_prd"] == "PRD-0006"
    assert meta["scenarios"] == ["Scenario A", "Scenario B"]

    assert "Scenario: Scenario A" in content
    assert "Scenario: Scenario B" in content

    # Check registry file
    registry_file = repo_env / "docs" / "project" / "user_stories" / "REGISTRY.md"
    assert registry_file.is_file()
    reg_content = registry_file.read_text(encoding="utf-8")
    assert "| `US-0010` | Real Multi-Faceted Story | Accepted | Alex | FEAT-ORCH-01 | `PRD-0006` |" in reg_content


def test_registry_sorting_order(repo_env: Path):
    engine = StoryEngine(repo_env)
    # Add out of order
    engine.update_registry("US-0020", "Story 20", "Accepted", "Morgan", "FEAT-20", "PRD-0001")
    engine.update_registry("US-0005", "Story 5", "Accepted", "Jordan", "FEAT-05", "PRD-0001")
    engine.update_registry("US-0012", "Story 12", "Accepted", "Riley", "FEAT-12", "PRD-0001")

    registry_file = repo_env / "docs" / "project" / "user_stories" / "REGISTRY.md"
    lines = [line for line in registry_file.read_text(encoding="utf-8").splitlines() if line.startswith("| `US-")]
    ids = [line.split("|")[1].strip().strip("`") for line in lines]
    assert ids == sorted(ids)


def test_story_trace_clean_and_broken(repo_env: Path):
    engine = StoryEngine(repo_env)
    # Create valid story
    res = engine.create_story(
        title="Valid Story",
        prd="PRD-0006",
        persona="Jordan (The AI-Native Engineering Lead)",
        bc="core",
        story_id="US-0001",
    )
    # Add a task linking to US-0001
    backlog_dir = repo_env / "docs" / "project" / "backlog" / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "0001-task.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Task 1\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_prds: [PRD-0006]\n"
        "governing_stories: [US-0001]\n"
        "governing_adrs: []\n"
        "dependencies: []\n"
        "---\n"
        "# TASK-0001\n",
        encoding="utf-8",
    )

    report = engine.trace()
    assert report.is_clean is True
    assert report.total_stories >= 1
    assert report.covered_stories >= 1
    assert len(report.orphaned_stories) == 0

    # Test filtering
    filtered_story = engine.trace(story_filter="US-0001")
    assert filtered_story.total_stories == 1

    filtered_empty = engine.trace(story_filter="US-9999")
    assert filtered_empty.total_stories == 0

    # Break lineage: add orphaned story
    stories_dir = repo_env / "docs" / "project" / "user_stories" / "accepted"
    (stories_dir / "us-9999-bad.md").write_text(
        "---\n"
        "id: '9999'\n"
        "title: Bad Story\n"
        "status: Accepted\n"
        "persona: NonExistentPersona\n"
        "target_bc: core\n"
        "governing_prd: PRD-9999\n"
        "---\n"
        "# US-9999\n",
        encoding="utf-8",
    )

    report_broken = engine.trace()
    assert report_broken.is_clean is False
    assert "US-9999" in report_broken.orphaned_stories
    assert any("PRD-9999" in br for br in report_broken.broken_references)
    formatted = report_broken.format_text()
    assert "Orphaned Stories" in formatted
    assert "Broken References" in formatted


def test_story_cli_handler_create(repo_env: Path, capsys: pytest.CaptureFixture[str]):
    config = load_config(repo_env)
    args = argparse.Namespace(
        story_action="create",
        title="CLI Created Story",
        prd="PRD-0006",
        persona="Jordan",
        bc="worker",
        id=None,
        feature=None,
        scenarios=["Step 1, Step 2"],
        dry_run=False,
    )
    rc = handle_story_command(args, config)
    assert rc == 0
    captured = capsys.readouterr()
    assert "Scaffolded BDD user story" in captured.out
    assert "Atomically synchronized" in captured.out


def test_story_cli_handler_trace(repo_env: Path, capsys: pytest.CaptureFixture[str]):
    config = load_config(repo_env)
    # Run trace
    args = argparse.Namespace(
        story_action="trace",
        story=None,
        prd=None,
        json=False,
    )
    rc = handle_story_command(args, config)
    assert rc == 0
    captured = capsys.readouterr()
    assert "SpecOps User Story Traceability Audit" in captured.out

    # Run trace with JSON
    args_json = argparse.Namespace(
        story_action="trace",
        story=None,
        prd=None,
        json=True,
    )
    rc = handle_story_command(args_json, config)
    assert rc == 0
    captured_json = capsys.readouterr()
    parsed = json.loads(captured_json.out)
    assert "is_clean" in parsed
    assert "total_stories" in parsed


def test_story_cli_handler_no_action(repo_env: Path):
    config = load_config(repo_env)
    args = argparse.Namespace(story_action=None)
    rc = handle_story_command(args, config)
    assert rc == 0
