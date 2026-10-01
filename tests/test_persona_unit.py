"""Unit tests for persona discovery, coverage audit, and living maintenance engine."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from spec_ops.cli.main import main
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.persona_engine import PersonaEngine
from spec_ops.core.persona_models import (
    EmergingArchetype,
    PersonaDocument,
    PersonaProfile,
)


@pytest.fixture
def persona_test_env(tmp_path: Path) -> tuple[Path, PersonaEngine]:
    """Sets up an isolated workspace with docs/project structure."""
    docs_dir = tmp_path / "docs" / "project"
    stories_dir = docs_dir / "user_stories"
    prd_dir = docs_dir / "product" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    prd_dir.mkdir(parents=True, exist_ok=True)

    personas_md = (
        "# SpecOps User Personas\n\n"
        "Archetypes representing stakeholders.\n\n"
        "---\n\n"
        "## 1. Alex — The Agentic Systems Architect\n"
        "- **Role**: Staff engineer and platform architect.\n"
        "- **Pain Points**:\n"
        "  - Context rot when specs drift.\n"
        "- **Goals with SpecOps**:\n"
        "  - Version-lock all specs in git.\n\n"
        "---\n\n"
        "## 2. Jordan — The AI-Native Engineering Lead\n"
        "- **Role**: Engineering lead overseeing hybrid teams.\n"
        "- **Pain Points**:\n"
        "  - Invisible progress.\n"
        "- **Goals with SpecOps**:\n"
        "  - Living relationship graph.\n"
    )
    (stories_dir / "PERSONAS.md").write_text(personas_md, encoding="utf-8")

    engine = PersonaEngine(tmp_path)
    return tmp_path, engine


def test_persona_engine_parse_doc(persona_test_env: tuple[Path, PersonaEngine]):
    _, engine = persona_test_env
    doc = engine.parse_personas_doc()
    assert len(doc.personas) == 2
    assert doc.personas[0].name == "Alex"
    assert doc.personas[0].role == "The Agentic Systems Architect"
    assert doc.personas[0].pain_points == ["Context rot when specs drift."]
    assert doc.personas[0].goals == ["Version-lock all specs in git."]
    assert doc.personas[1].name == "Jordan"


def test_persona_audit_clean_coverage(persona_test_env: tuple[Path, PersonaEngine]):
    tmp_path, engine = persona_test_env
    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    (prd_dir / "prd-0001.md").write_text(
        "---\nid: '0001'\ntitle: First PRD\ntarget_persona: Alex\n---\n# PRD",
        encoding="utf-8",
    )
    (stories_dir / "us-0001.md").write_text(
        "---\nid: '0001'\ntitle: Story 1\npersona: Jordan\n---\n# US-0001",
        encoding="utf-8",
    )

    res = engine.audit(check_git=False)
    assert res.total_personas == 2
    assert res.covered_personas == 2
    assert res.uncovered_personas == []
    assert res.coverage_percentage == 100.0
    assert len(res.emerging_archetypes) == 0

    text = res.format_text()
    assert "Alex" in text
    assert "Jordan" in text
    assert "Active" in text


def test_persona_audit_with_emerging_archetype(persona_test_env: tuple[Path, PersonaEngine]):
    tmp_path, engine = persona_test_env
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"

    (prd_dir / "prd-0002.md").write_text(
        "---\nid: '0002'\ntitle: Security Compliance\ntarget_persona: Casey (The Compliance Officer)\n---\n# PRD",
        encoding="utf-8",
    )

    res = engine.audit(check_git=False)
    assert len(res.emerging_archetypes) == 1
    arch = res.emerging_archetypes[0]
    assert arch.name == "Casey"
    assert arch.role == "The Compliance Officer"
    assert "PRD-0002" in arch.sources


def test_persona_audit_uncovered_persona(persona_test_env: tuple[Path, PersonaEngine]):
    tmp_path, engine = persona_test_env
    # Only create a PRD for Alex, Jordan has 0 PRDs and 0 stories
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    (prd_dir / "prd-0001.md").write_text(
        "---\nid: '0001'\ntarget_persona: Alex\n---\n# PRD",
        encoding="utf-8",
    )

    res = engine.audit(check_git=False)
    assert res.covered_personas == 1
    assert "Jordan" in res.uncovered_personas
    assert res.coverage_percentage == 50.0


def test_persona_sync_diff_preview(persona_test_env: tuple[Path, PersonaEngine]):
    tmp_path, engine = persona_test_env
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    (prd_dir / "prd-0003.md").write_text(
        "---\nid: '0003'\ntarget_persona: Sam (The Site Reliability Engineer)\n---\n# PRD",
        encoding="utf-8",
    )

    # Sync with apply=False (diff preview)
    res = engine.sync(apply=False, check_git=False)
    assert len(res.emerging_archetypes) == 1
    assert res.applied is False
    assert "+## 3. Sam — The Site Reliability Engineer" in res.diff

    # Verify disk content is unchanged
    personas_file = tmp_path / "docs" / "project" / "user_stories" / "PERSONAS.md"
    assert "Sam" not in personas_file.read_text(encoding="utf-8")


def test_persona_sync_apply(persona_test_env: tuple[Path, PersonaEngine]):
    tmp_path, engine = persona_test_env
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    (prd_dir / "prd-0003.md").write_text(
        "---\nid: '0003'\ntarget_persona: Sam (The Site Reliability Engineer)\n---\n# PRD",
        encoding="utf-8",
    )

    # Sync with apply=True
    res = engine.sync(apply=True, check_git=False)
    assert res.applied is True

    personas_file = tmp_path / "docs" / "project" / "user_stories" / "PERSONAS.md"
    content = personas_file.read_text(encoding="utf-8")
    assert "## 3. Sam — The Site Reliability Engineer" in content
    assert "- **Role**: Subject matter specialist and core contributor driving sam capabilities." in content

    # Re-audit: Sam is now a known persona, 0 emerging archetypes
    re_audit = engine.audit(check_git=False)
    assert re_audit.total_personas == 3
    assert len(re_audit.emerging_archetypes) == 0


def test_persona_cli_audit_and_sync_json(capsys, monkeypatch):
    """Test persona audit and sync CLI entry points with --json flag."""
    code = main(["persona", "audit", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "total_personas" in data
    assert "distribution" in data
    assert data["total_personas"] == 6

    code_sync = main(["persona", "sync", "--json"])
    assert code_sync == 0
    captured_sync = capsys.readouterr()
    data_sync = json.loads(captured_sync.out)
    assert "emerging_archetypes" in data_sync
    assert data_sync["applied"] is False


def test_persona_cli_help(capsys):
    """Test persona root CLI command prints help."""
    code = main(["persona"])
    assert code == 0
    captured = capsys.readouterr()
    assert "persona" in captured.out or "usage:" in captured.out
