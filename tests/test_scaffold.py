"""Tests for project initialization and scaffolding."""

from pathlib import Path

from spec_ops.scaffold.init import init_project


def test_init_project_creates_structure(tmp_path: Path):
    created = init_project(tmp_path, name="AcmeSystem")
    assert len(created) > 0

    assert (tmp_path / "specops.toml").is_file()
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "docs" / "project" / "user_stories" / "PERSONAS.md").is_file()
    assert (tmp_path / "docs" / "project" / "adrs" / "accepted" / "adr-0001-specification-as-code-architecture.md").is_file()
    assert (tmp_path / "docs" / "project" / "backlog" / "PRIORITY.md").is_file()
    assert (tmp_path / "docs" / "project" / "backlog" / "refined" / "0001-initial-architecture-spike-and-setup.md").is_file()

    toml_content = (tmp_path / "specops.toml").read_text(encoding="utf-8")
    assert 'name = "AcmeSystem"' in toml_content

    agents_md = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "# AcmeSystem Agent Operating Manual" in agents_md
    assert "File Length Limit (<500 lines)" in agents_md
    assert "Blackbox Frontdoor Verification" in agents_md
    assert "Strict Backlog Isolation" in agents_md
    assert "Executable BDD User Stories" in agents_md
    assert "Domain-Driven Design (DDD)" in agents_md
    assert "Diataxis Standards" in agents_md


def test_init_project_core_only_profiles(tmp_path: Path):
    target = tmp_path / "core_only"
    init_project(target, name="CoreOnlyApp", profiles=["core"])
    agents_md = (target / "AGENTS.md").read_text(encoding="utf-8")

    assert "# CoreOnlyApp Agent Operating Manual" in agents_md
    assert "File Length Limit (<500 lines)" in agents_md
    assert "Executable BDD User Stories" not in agents_md
    assert "Domain-Driven Design (DDD)" not in agents_md
