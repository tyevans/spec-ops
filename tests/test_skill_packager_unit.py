"""Unit tests for universal skill packager and multi-platform distribution.

Target bounded context: scaffold. Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0008.
Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from pathlib import Path
import pytest

from spec_ops.scaffold.init import init_project
from spec_ops.scaffold.skill_packager import (
    SUPPORTED_SKILL_TARGETS,
    generate_skill_bundle,
    package_antigravity,
    package_claude,
    package_cursor,
    scaffold_skill_command,
    validate_bundle_links,
)


def test_supported_skill_targets():
    assert "antigravity" in SUPPORTED_SKILL_TARGETS
    assert "claude" in SUPPORTED_SKILL_TARGETS
    assert "cursor" in SUPPORTED_SKILL_TARGETS
    assert "all" in SUPPORTED_SKILL_TARGETS


def test_generate_skill_bundle_invalid_target():
    with pytest.raises(ValueError, match="Unsupported target platform"):
        generate_skill_bundle(target="unsupported_platform")


def test_package_antigravity_structure():
    bundle = package_antigravity()
    expected_keys = {
        ".agents/skills/spec-ops/SKILL.md",
        ".agents/skills/spec-ops/references/cli_primer.md",
        ".agents/skills/spec-ops/references/balancing_loop.md",
        ".agents/skills/spec-ops/references/orchestration_protocol.md",
    }
    assert set(bundle.keys()) == expected_keys
    assert "SpecOps Full-Lifecycle SDLC Orchestrator" in bundle[".agents/skills/spec-ops/SKILL.md"]
    assert "SpecOps CLI Primer" in bundle[".agents/skills/spec-ops/references/cli_primer.md"]
    assert "Autonomous Continuous Balancing Loop" in bundle[".agents/skills/spec-ops/references/balancing_loop.md"]
    assert "SpecOps Multi-Agent SDLC Orchestration Protocol" in bundle[".agents/skills/spec-ops/references/orchestration_protocol.md"]


def test_package_claude_structure():
    bundle = package_claude(project_name="TestProject")
    expected_keys = {
        "CLAUDE.md",
        ".claude/skills/spec-ops/SKILL.md",
        ".claude/skills/spec-ops/references/cli_primer.md",
        ".claude/skills/spec-ops/references/balancing_loop.md",
        ".claude/skills/spec-ops/references/orchestration_protocol.md",
        ".claude/commands/spec-ops.md",
    }
    assert set(bundle.keys()) == expected_keys
    assert "TestProject" in bundle["CLAUDE.md"]
    assert "/spec-ops" in bundle[".claude/commands/spec-ops.md"]


def test_package_cursor_structure():
    bundle = package_cursor(project_name="TestProject")
    expected_keys = {
        ".cursorrules",
        ".cursor/rules/spec-ops.mdc",
        ".cursor/rules/references/cli_primer.md",
        ".cursor/rules/references/balancing_loop.md",
        ".cursor/rules/references/orchestration_protocol.md",
    }
    assert set(bundle.keys()) == expected_keys
    assert "TestProject" in bundle[".cursorrules"]
    assert "alwaysApply: true" in bundle[".cursor/rules/spec-ops.mdc"]


def test_generate_skill_bundle_all():
    bundle = generate_skill_bundle(target="all", project_name="SpecOpsProject")
    assert len(bundle) == 15
    assert ".agents/skills/spec-ops/SKILL.md" in bundle
    assert "CLAUDE.md" in bundle
    assert ".cursorrules" in bundle


def test_validate_bundle_links_valid():
    bundle = generate_skill_bundle(target="all")
    broken = validate_bundle_links(bundle)
    assert broken == []


def test_validate_bundle_links_broken():
    bundle = {
        "docs/test.md": "Check out [nonexistent](./missing.md) for details.",
    }
    broken = validate_bundle_links(bundle)
    assert len(broken) == 1
    assert "missing.md" in broken[0]


def test_validate_bundle_links_ignores_external_and_anchors():
    bundle = {
        "docs/test.md": "Links: [site](https://example.com), [mail](mailto:test@example.com), [anchor](#heading).",
    }
    broken = validate_bundle_links(bundle)
    assert broken == []


def test_scaffold_skill_command_dry_run(tmp_path: Path):
    init_project(tmp_path, name="DryRunTest")
    res = scaffold_skill_command(root_dir=tmp_path, target="all", dry_run=True)
    assert res == 0
    # Verify no files were created
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not (tmp_path / ".cursorrules").exists()


def test_scaffold_skill_command_write_and_collision(tmp_path: Path):
    init_project(tmp_path, name="WriteTest")
    # First write
    res = scaffold_skill_command(root_dir=tmp_path, target="claude", force=False)
    assert res == 0
    assert (tmp_path / "CLAUDE.md").is_file()

    # Second write without force should fail
    res_collision = scaffold_skill_command(root_dir=tmp_path, target="claude", force=False)
    assert res_collision == 1

    # Second write with force should succeed
    res_force = scaffold_skill_command(root_dir=tmp_path, target="claude", force=True)
    assert res_force == 0


def test_scaffold_skill_command_custom_output_dir(tmp_path: Path):
    init_project(tmp_path, name="OutDirTest")
    custom_out = tmp_path / "custom_output"
    res = scaffold_skill_command(root_dir=tmp_path, target="antigravity", output_dir=custom_out)
    assert res == 0
    assert (custom_out / ".agents" / "skills" / "spec-ops" / "SKILL.md").is_file()


def test_inline_skill_contract_and_protocols():
    """Verifies that .agents/skills/spec-ops/SKILL.md satisfies PMaC inline skill contracts (TASK-0184)."""
    bundle = package_antigravity()
    skill_content = bundle[".agents/skills/spec-ops/SKILL.md"]

    # 1. Frontmatter check
    assert skill_content.startswith("---\n")
    assert "name: spec-ops\n" in skill_content
    assert "description:" in skill_content

    # 2. Executable runbooks
    assert "uv run spec-ops curate" in skill_content
    assert "uv run spec-ops health" in skill_content
    assert "uv run spec-ops worktree create" in skill_content

    # 3. Subagent orchestration protocols
    assert "Multi-Agent Orchestration Protocol" in skill_content
    assert "references/orchestration_protocol.md" in skill_content
    assert "references/cli_primer.md" in skill_content
    assert "references/balancing_loop.md" in skill_content

    # 4. Invariant checks
    assert "File Length Limit (<500 lines)" in skill_content
    assert "Blackbox Frontdoor Verification" in skill_content
    assert "Strict Backlog Isolation" in skill_content
