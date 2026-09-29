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

    ci_file = tmp_path / ".github" / "workflows" / "ci.yml"
    assert ci_file.is_file()
    ci_content = ci_file.read_text(encoding="utf-8")
    assert "uv run spec-ops health" in ci_content
    assert "uv run pytest" in ci_content
    assert "uv lock --check" in ci_content

    agents_md = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "# AcmeSystem Agent Operating Manual" in agents_md
    assert "File Length Limit (<500 lines)" in agents_md
    assert "Blackbox Frontdoor Verification" in agents_md
    assert "Strict Backlog Isolation" in agents_md
    assert "Executable BDD User Stories" in agents_md
    assert "Domain-Driven Design (DDD)" in agents_md
    assert "Property-Based Testing (Hypothesis)" in agents_md
    assert "Diataxis Standards" in agents_md
    assert "Definition of Ready (DoR)" in agents_md
    assert "Definition of Done (DoD)" in agents_md


    pages_file = tmp_path / ".github" / "workflows" / "deploy-pages.yml"
    assert pages_file.is_file()
    pages_content = pages_file.read_text(encoding="utf-8")
    assert "actions/deploy-pages@v4" in pages_content
    assert "actions/upload-pages-artifact@v3" in pages_content
    assert "uv run spec-ops docs build" in pages_content
    assert "id-token: write" in pages_content
    assert "pages: write" in pages_content

    pre_commit_file = tmp_path / ".pre-commit-config.yaml"
    assert pre_commit_file.is_file()
    pre_commit_content = pre_commit_file.read_text(encoding="utf-8")
    assert "uv run spec-ops health" in pre_commit_content
    assert "ruff" in pre_commit_content


def test_init_project_core_only_profiles(tmp_path: Path):
    target = tmp_path / "core_only"
    init_project(target, name="CoreOnlyApp", profiles=["core"])
    agents_md = (target / "AGENTS.md").read_text(encoding="utf-8")

    assert "# CoreOnlyApp Agent Operating Manual" in agents_md
    assert "File Length Limit (<500 lines)" in agents_md
    assert "Executable BDD User Stories" not in agents_md
    assert "Domain-Driven Design (DDD)" not in agents_md


def test_init_project_no_github_pages(tmp_path: Path):
    target = tmp_path / "no_pages"
    init_project(target, name="NoPages", github_pages=False)
    assert not (target / ".github" / "workflows" / "deploy-pages.yml").exists()
    assert (target / ".github" / "workflows" / "ci.yml").is_file()


def test_init_project_no_pre_commit(tmp_path: Path):
    target = tmp_path / "no_pre_commit"
    init_project(target, name="NoPreCommit", pre_commit=False)
    assert not (target / ".pre-commit-config.yaml").exists()


def test_init_project_with_agent_adapters(tmp_path: Path):
    from spec_ops.config.loader import load_config

    target = tmp_path / "multi_agent"
    created = init_project(target, name="MultiAgentApp", agents=["antigravity", "claude", "cursor"])

    assert (target / "CLAUDE.md").is_file()
    assert (target / ".cursorrules").is_file()
    assert (target / "GEMINI.md").is_file()
    assert (target / ".agents" / "skills" / "curate" / "SKILL.md").is_file()
    assert (target / ".agents" / "skills" / "health" / "SKILL.md").is_file()
    assert (target / ".agents" / "skills" / "worker" / "SKILL.md").is_file()

    toml_content = (target / "specops.toml").read_text(encoding="utf-8")
    assert 'target_agents = ["antigravity", "claude", "cursor"]' in toml_content

    cfg = load_config(root_dir=target)
    assert cfg.execution.target_agents == ["antigravity", "claude", "cursor"]
