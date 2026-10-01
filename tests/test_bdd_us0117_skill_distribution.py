"""BDD step definitions for US-0117: Universal Multi-Platform Skill Distribution and Package Scaffolding.

Target bounded context: scaffold. Governed by ADR-0001, ADR-0003, ADR-0006, ADR-0008.
Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project
from spec_ops.scaffold.skill_packager import validate_bundle_links

scenarios("features/us_0117_skill_distribution.feature")


def _run_cli(root: Path, cmd_str: str) -> subprocess.CompletedProcess[str]:
    parts = shlex.split(cmd_str)
    # Remove leading 'spec-ops' binary name if present
    if parts and parts[0] == "spec-ops":
        parts = parts[1:]
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *parts],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bdd_skill_env(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="SkillDistBDD")
    return {
        "root": tmp_path,
        "last_res": None,
    }


@given("a user repository initialized with SpecOps")
def given_user_repo_initialized(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    assert (root / "specops.toml").is_file()
    assert (root / "docs" / "project").is_dir()


@when(parsers.parse('the user runs "{cmd}"'))
def when_user_runs_cmd(bdd_skill_env: dict[str, Any], cmd: str) -> None:
    res = _run_cli(bdd_skill_env["root"], cmd)
    bdd_skill_env["last_res"] = res


@then('portable skill definitions, slash commands, and rule files are scaffolded across ".agents/skills/", "CLAUDE.md", and ".cursorrules"')
def then_portable_definitions_scaffolded(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    res = bdd_skill_env["last_res"]
    assert res is not None
    assert res.returncode == 0, f"Command failed: {res.stderr}"

    # Antigravity artifacts
    assert (root / ".agents" / "skills" / "spec-ops" / "SKILL.md").is_file()
    assert (root / ".agents" / "skills" / "spec-ops" / "references" / "cli_primer.md").is_file()
    assert (root / ".agents" / "skills" / "spec-ops" / "references" / "balancing_loop.md").is_file()
    assert (root / ".agents" / "skills" / "spec-ops" / "references" / "orchestration_protocol.md").is_file()

    # Claude Code artifacts
    assert (root / "CLAUDE.md").is_file()
    assert (root / ".claude" / "skills" / "spec-ops" / "SKILL.md").is_file()
    assert (root / ".claude" / "skills" / "spec-ops" / "references" / "cli_primer.md").is_file()
    assert (root / ".claude" / "commands" / "spec-ops.md").is_file()

    # Cursor artifacts
    assert (root / ".cursorrules").is_file()
    assert (root / ".cursor" / "rules" / "spec-ops.mdc").is_file()
    assert (root / ".cursor" / "rules" / "references" / "cli_primer.md").is_file()


@then("references and CLI primers are packaged without broken links.")
def then_references_cli_primers_no_broken_links(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    bundle: dict[str, str] = {}
    for p in root.rglob("*"):
        if not p.is_file() or not (p.name.endswith(".md") or p.name.endswith(".mdc")):
            continue
        rel = p.relative_to(root).as_posix()
        if (
            rel.startswith(".agents/skills/")
            or rel.startswith(".claude/")
            or rel.startswith(".cursor/")
            or rel in ("CLAUDE.md", ".cursorrules")
        ):
            bundle[rel] = p.read_text(encoding="utf-8")

    broken = validate_bundle_links(bundle, root_dir=root)
    assert not broken, f"Broken links detected in skill bundle: {broken}"


@then('".agents/skills/spec-ops/SKILL.md" is scaffolded with complete CLI primers and references')
def then_antigravity_scaffolded(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    res = bdd_skill_env["last_res"]
    assert res is not None
    assert res.returncode == 0, f"Command failed: {res.stderr}"

    skill_path = root / ".agents" / "skills" / "spec-ops" / "SKILL.md"
    assert skill_path.is_file()
    content = skill_path.read_text(encoding="utf-8")
    assert "SpecOps Full-Lifecycle SDLC Orchestrator" in content
    assert "./references/cli_primer.md" in content

    refs_dir = root / ".agents" / "skills" / "spec-ops" / "references"
    assert (refs_dir / "cli_primer.md").is_file()
    assert (refs_dir / "balancing_loop.md").is_file()
    assert (refs_dir / "orchestration_protocol.md").is_file()


@then("references and runbooks are packaged without broken links.")
def then_runbooks_no_broken_links(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    bundle: dict[str, str] = {}
    for p in root.rglob("*"):
        if not p.is_file() or not (p.name.endswith(".md") or p.name.endswith(".mdc")):
            continue
        rel = p.relative_to(root).as_posix()
        if (
            rel.startswith(".agents/skills/")
            or rel.startswith(".claude/")
            or rel.startswith(".cursor/")
            or rel in ("CLAUDE.md", ".cursorrules")
        ):
            bundle[rel] = p.read_text(encoding="utf-8")

    broken = validate_bundle_links(bundle, root_dir=root)
    assert not broken, f"Broken links detected in skill bundle: {broken}"



@then('"CLAUDE.md", ".claude/skills/spec-ops/", and ".claude/commands/spec-ops.md" are scaffolded')
def then_claude_scaffolded(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    res = bdd_skill_env["last_res"]
    assert res is not None
    assert res.returncode == 0, f"Command failed: {res.stderr}"

    assert (root / "CLAUDE.md").is_file()
    assert (root / ".claude" / "skills" / "spec-ops" / "SKILL.md").is_file()
    assert (root / ".claude" / "skills" / "spec-ops" / "references" / "cli_primer.md").is_file()
    assert (root / ".claude" / "commands" / "spec-ops.md").is_file()


@then('".cursorrules" and ".cursor/rules/spec-ops.mdc" are scaffolded')
def then_cursor_scaffolded(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    res = bdd_skill_env["last_res"]
    assert res is not None
    assert res.returncode == 0, f"Command failed: {res.stderr}"

    assert (root / ".cursorrules").is_file()
    assert (root / ".cursor" / "rules" / "spec-ops.mdc").is_file()
    assert (root / ".cursor" / "rules" / "references" / "cli_primer.md").is_file()


@then("no files are written to disk")
def then_no_files_written(bdd_skill_env: dict[str, Any]) -> None:
    root = bdd_skill_env["root"]
    res = bdd_skill_env["last_res"]
    assert res is not None
    assert res.returncode == 0, f"Dry-run command failed: {res.stderr}"
    assert "Dry run:" in res.stdout

    # Confirm Claude and Cursor files were NOT created on disk
    assert not (root / "CLAUDE.md").exists()
    assert not (root / ".cursorrules").exists()
    assert not (root / ".claude").exists()
    assert not (root / ".cursor").exists()


@then("link validation succeeds without errors.")
def then_dry_run_links_succeed(bdd_skill_env: dict[str, Any]) -> None:
    res = bdd_skill_env["last_res"]
    assert res is not None
    assert "verified without errors" in res.stdout
