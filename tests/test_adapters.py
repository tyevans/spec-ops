"""Tests for multi-agent platform adapters (Claude, Cursor, Antigravity)."""

from pathlib import Path
import pytest

from spec_ops.scaffold.adapters import (
    SUPPORTED_AGENTS,
    generate_antigravity_rules,
    generate_claude_rules,
    generate_cursor_rules,
    get_antigravity_slash_commands,
    parse_target_agents,
    scaffold_agent_adapters,
)


def test_parse_target_agents():
    assert parse_target_agents(None) == []
    assert parse_target_agents("") == []
    assert parse_target_agents([]) == []

    # Single string
    assert parse_target_agents("claude") == ["claude"]
    assert parse_target_agents("cursor") == ["cursor"]
    assert parse_target_agents("antigravity") == ["antigravity"]

    # Comma-separated
    assert parse_target_agents("antigravity,claude,cursor") == ["antigravity", "claude", "cursor"]
    assert parse_target_agents("claude, cursor") == ["claude", "cursor"]
    assert parse_target_agents("CURSOR, CLAUDE") == ["claude", "cursor"]

    # List of strings
    assert parse_target_agents(["antigravity", "cursor"]) == ["antigravity", "cursor"]
    assert parse_target_agents(["claude,cursor", "antigravity"]) == ["antigravity", "claude", "cursor"]

    # Keyword 'all'
    assert parse_target_agents("all") == ["antigravity", "claude", "cursor"]
    assert parse_target_agents(["all"]) == ["antigravity", "claude", "cursor"]

    # Invalid agent
    with pytest.raises(ValueError, match="Unsupported agent platform: 'unsupported'"):
        parse_target_agents("unsupported")

    with pytest.raises(ValueError, match="Unsupported agent platform: 'copilot'"):
        parse_target_agents(["claude", "copilot"])


def test_generate_claude_rules():
    content = generate_claude_rules("AlphaProject", profiles=["core", "bdd", "ddd"])
    assert "# Claude Code Operating Guidelines — AlphaProject" in content
    assert "File Length Limit (<500 lines)" in content
    assert "Blackbox Frontdoor Verification" in content
    assert "Strict Backlog Isolation" in content
    assert "Executable BDD Scenarios" in content
    assert "Domain-Driven Design" in content
    assert "uv run spec-ops health" in content
    assert "uv run spec-ops curate" in content
    assert "uv run spec-ops worker" in content
    assert "uv run pytest" in content
    assert "uv lock --check" in content
    assert "AGENTS.md" in content


def test_generate_cursor_rules():
    content = generate_cursor_rules("BetaProject", profiles=["core", "bdd"])
    assert "# Cursor Rules — BetaProject" in content
    assert "Strictly <500 lines per file" in content
    assert "Blackbox Frontdoor Verification" in content
    assert "Strict Backlog Isolation" in content
    assert "Executable BDD Scenarios" in content
    assert "uv run spec-ops health" in content
    assert "uv run spec-ops curate" in content
    assert "uv run spec-ops worker" in content
    assert "uv run pytest" in content
    assert "uv lock --check" in content
    assert "AGENTS.md" in content


def test_generate_antigravity_rules():
    content = generate_antigravity_rules("GammaProject", profiles=["core", "ddd"])
    assert "# Antigravity Operating Rules — GammaProject" in content
    assert "File Length Limit (<500 lines)" in content
    assert "Blackbox Frontdoor Verification" in content
    assert "Strict Backlog Isolation" in content
    assert "Domain-Driven Design" in content
    assert "/curate" in content
    assert "/health" in content
    assert "/worker" in content
    assert "uv run spec-ops health" in content
    assert "uv run pytest" in content
    assert "uv lock --check" in content
    assert "AGENTS.md" in content


def test_get_antigravity_slash_commands():
    cmds = get_antigravity_slash_commands()
    assert ".agents/skills/curate/SKILL.md" in cmds
    assert ".agents/skills/health/SKILL.md" in cmds
    assert ".agents/skills/worker/SKILL.md" in cmds
    assert ".agents/skills/spec-ops/SKILL.md" in cmds

    curate_content = cmds[".agents/skills/curate/SKILL.md"]
    assert "name: curate" in curate_content
    assert "uv run spec-ops curate" in curate_content
    assert "--infer" in curate_content
    assert "Cognitive Refinement" in curate_content
    assert "PRIORITY.md" in curate_content

    health_content = cmds[".agents/skills/health/SKILL.md"]
    assert "name: health" in health_content
    assert "uv run spec-ops health" in health_content
    assert "File Length Limit (<500 lines)" in health_content

    worker_content = cmds[".agents/skills/worker/SKILL.md"]
    assert "name: worker" in worker_content
    assert "uv run spec-ops worker" in worker_content
    assert "TASK-XXXX" in worker_content
    assert ".worktrees/<task-id>" in worker_content

    spec_ops_content = cmds[".agents/skills/spec-ops/SKILL.md"]
    assert "name: spec-ops" in spec_ops_content
    assert "Company in a Box" in spec_ops_content
    assert "Orchestration Failure Protocol" in spec_ops_content or "Orchestrator" in spec_ops_content


def test_scaffold_agent_adapters_individual(tmp_path: Path):
    # Claude only
    claude_dir = tmp_path / "claude_project"
    files = scaffold_agent_adapters(claude_dir, "ClaudeApp", agents="claude")
    assert len(files) == 1
    assert (claude_dir / "CLAUDE.md").is_file()
    assert not (claude_dir / ".cursorrules").exists()
    assert not (claude_dir / "GEMINI.md").exists()

    # Cursor only
    cursor_dir = tmp_path / "cursor_project"
    files = scaffold_agent_adapters(cursor_dir, "CursorApp", agents="cursor")
    assert len(files) == 1
    assert (cursor_dir / ".cursorrules").is_file()
    assert not (cursor_dir / "CLAUDE.md").exists()
    assert not (cursor_dir / "GEMINI.md").exists()

    # Antigravity only
    ag_dir = tmp_path / "ag_project"
    files = scaffold_agent_adapters(ag_dir, "AgApp", agents="antigravity")
    assert len(files) == 5
    assert (ag_dir / "GEMINI.md").is_file()
    assert (ag_dir / ".agents" / "skills" / "curate" / "SKILL.md").is_file()
    assert (ag_dir / ".agents" / "skills" / "health" / "SKILL.md").is_file()
    assert (ag_dir / ".agents" / "skills" / "worker" / "SKILL.md").is_file()
    assert (ag_dir / ".agents" / "skills" / "spec-ops" / "SKILL.md").is_file()
    assert not (ag_dir / "CLAUDE.md").exists()
    assert not (ag_dir / ".cursorrules").exists()


def test_scaffold_agent_adapters_all(tmp_path: Path):
    target = tmp_path / "all_project"
    files = scaffold_agent_adapters(target, "AllApp", agents="antigravity,claude,cursor")
    assert len(files) == 7

    assert (target / "CLAUDE.md").is_file()
    assert (target / ".cursorrules").is_file()
    assert (target / "GEMINI.md").is_file()
    assert (target / ".agents" / "skills" / "curate" / "SKILL.md").is_file()
    assert (target / ".agents" / "skills" / "health" / "SKILL.md").is_file()
    assert (target / ".agents" / "skills" / "worker" / "SKILL.md").is_file()
    assert (target / ".agents" / "skills" / "spec-ops" / "SKILL.md").is_file()

    # Verify idempotency (no duplication)
    second_run = scaffold_agent_adapters(target, "AllApp", agents="antigravity,claude,cursor")
    assert len(second_run) == 0
