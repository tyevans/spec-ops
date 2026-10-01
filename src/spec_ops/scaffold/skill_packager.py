"""Universal multi-platform skill distribution and package scaffolding.

Target bounded context: scaffold. Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0008.
Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import os
from pathlib import Path
import posixpath
import re
import sys
from typing import Any

from .adapters import generate_claude_rules, generate_cursor_rules
from .skill_loop import BALANCING_LOOP_MD, SPEC_OPS_ORCHESTRATOR_SKILL_MD
from .skill_references import CLI_PRIMER_MD, ORCHESTRATION_PROTOCOL_MD

SUPPORTED_SKILL_TARGETS = ("antigravity", "claude", "cursor", "all")

CURSOR_ORCHESTRATOR_MDC = """---
description: SpecOps full-lifecycle SDLC orchestrator and autonomous development rules
globs: *
alwaysApply: true
---

# SpecOps Full-Lifecycle SDLC Orchestrator ("Company in a Box")

You are the **Lead SDLC Orchestrator** for SpecOps. Your objective is to drive end-to-end software development with non-negotiable craftsmanship, architectural clarity, and zero-drift PMaC specifications.

## Quick References

- 🔄 [Continuous Balancing Loop & Tri-Directional Discovery](./references/balancing_loop.md)
- 📖 [SpecOps CLI Primer](./references/cli_primer.md)
- 🤝 [Multi-Agent Orchestration Protocol](./references/orchestration_protocol.md)

## Hard Invariants
1. **File Length Limit (<500 lines)**: Decompose modules exceeding ~400 lines (ADR-0002).
2. **Blackbox Frontdoor Verification**: Test observable behavior strictly through public APIs; zero private backdoor mocks (ADR-0003, ADR-0006).
3. **Strict Backlog Isolation**: Work in isolated worktrees; never touch `docs/project/backlog/` on feature branches (ADR-0005).
4. **Lockfile Immutability**: `uv lock --check` must pass cleanly.
5. **Specification as Code (PMaC)**: Requirements and specifications live under `docs/project/` (ADR-0001).
"""

CLAUDE_SLASH_COMMAND_MD = """# /spec-ops — SpecOps Autonomous SDLC Orchestrator

Execute the SpecOps full-lifecycle SDLC orchestrator.
Read instructions in `.claude/skills/spec-ops/SKILL.md` and follow the autonomous balancing loop.
"""


def _get_skill_md(root_dir: Path | None) -> str:
    """Retrieves orchestrator skill markdown from repository or bundled template."""
    if root_dir:
        p = root_dir / ".agents" / "skills" / "spec-ops" / "SKILL.md"
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return SPEC_OPS_ORCHESTRATOR_SKILL_MD.strip() + "\n"


def _get_reference(root_dir: Path | None, filename: str, fallback: str) -> str:
    """Retrieves reference file from repository or bundled fallback."""
    if root_dir:
        p = root_dir / ".agents" / "skills" / "spec-ops" / "references" / filename
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return fallback.strip() + "\n"


def package_antigravity(root_dir: Path | None = None) -> dict[str, str]:
    """Generates file mapping for Antigravity skill platform."""
    skill_md = _get_skill_md(root_dir)
    cli_primer = _get_reference(root_dir, "cli_primer.md", CLI_PRIMER_MD)
    balancing = _get_reference(root_dir, "balancing_loop.md", BALANCING_LOOP_MD)
    protocol = _get_reference(root_dir, "orchestration_protocol.md", ORCHESTRATION_PROTOCOL_MD)

    return {
        ".agents/skills/spec-ops/SKILL.md": skill_md.strip() + "\n",
        ".agents/skills/spec-ops/references/cli_primer.md": cli_primer.strip() + "\n",
        ".agents/skills/spec-ops/references/balancing_loop.md": balancing.strip() + "\n",
        ".agents/skills/spec-ops/references/orchestration_protocol.md": protocol.strip() + "\n",
    }


def package_claude(project_name: str = "SpecOps", root_dir: Path | None = None) -> dict[str, str]:
    """Generates file mapping for Claude Code platform."""
    skill_md = _get_skill_md(root_dir)
    cli_primer = _get_reference(root_dir, "cli_primer.md", CLI_PRIMER_MD)
    balancing = _get_reference(root_dir, "balancing_loop.md", BALANCING_LOOP_MD)
    protocol = _get_reference(root_dir, "orchestration_protocol.md", ORCHESTRATION_PROTOCOL_MD)
    claude_rules = generate_claude_rules(project_name)

    return {
        "CLAUDE.md": claude_rules.strip() + "\n",
        ".claude/skills/spec-ops/SKILL.md": skill_md.strip() + "\n",
        ".claude/skills/spec-ops/references/cli_primer.md": cli_primer.strip() + "\n",
        ".claude/skills/spec-ops/references/balancing_loop.md": balancing.strip() + "\n",
        ".claude/skills/spec-ops/references/orchestration_protocol.md": protocol.strip() + "\n",
        ".claude/commands/spec-ops.md": CLAUDE_SLASH_COMMAND_MD.strip() + "\n",
    }


def package_cursor(project_name: str = "SpecOps", root_dir: Path | None = None) -> dict[str, str]:
    """Generates file mapping for Cursor platform."""
    cursor_rules = generate_cursor_rules(project_name)
    cli_primer = _get_reference(root_dir, "cli_primer.md", CLI_PRIMER_MD)
    balancing = _get_reference(root_dir, "balancing_loop.md", BALANCING_LOOP_MD)
    protocol = _get_reference(root_dir, "orchestration_protocol.md", ORCHESTRATION_PROTOCOL_MD)

    return {
        ".cursorrules": cursor_rules.strip() + "\n",
        ".cursor/rules/spec-ops.mdc": CURSOR_ORCHESTRATOR_MDC.strip() + "\n",
        ".cursor/rules/references/cli_primer.md": cli_primer.strip() + "\n",
        ".cursor/rules/references/balancing_loop.md": balancing.strip() + "\n",
        ".cursor/rules/references/orchestration_protocol.md": protocol.strip() + "\n",
    }


def generate_skill_bundle(
    target: str = "all",
    root_dir: Path | None = None,
    project_name: str = "SpecOps",
) -> dict[str, str]:
    """Generates universal skill bundles for target platform."""
    normalized_target = target.strip().lower()
    if normalized_target not in SUPPORTED_SKILL_TARGETS:
        raise ValueError(
            f"Unsupported target platform '{target}'. "
            f"Supported platforms: {', '.join(SUPPORTED_SKILL_TARGETS)}"
        )

    bundle: dict[str, str] = {}
    if normalized_target in ("antigravity", "all"):
        bundle.update(package_antigravity(root_dir=root_dir))
    if normalized_target in ("claude", "all"):
        bundle.update(package_claude(project_name=project_name, root_dir=root_dir))
    if normalized_target in ("cursor", "all"):
        bundle.update(package_cursor(project_name=project_name, root_dir=root_dir))

    return bundle


def validate_bundle_links(bundle: dict[str, str], root_dir: Path | None = None) -> list[str]:
    """Validates relative markdown links across all files in bundle."""
    broken: list[str] = []
    pattern = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")

    for rel_path, content in bundle.items():
        if not (rel_path.endswith(".md") or rel_path.endswith(".mdc")):
            continue
        doc_dir = posixpath.dirname(rel_path)

        for match in pattern.finditer(content):
            raw_link = match.group(2).strip()
            target = raw_link.split()[0].strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:", "ftp:")):
                continue

            target_clean = target.split("#")[0].split("?")[0].strip()
            if not target_clean:
                continue

            resolved = posixpath.normpath(posixpath.join(doc_dir, target_clean))
            if resolved in bundle:
                continue
            if root_dir and (root_dir / resolved).exists():
                continue

            broken.append(f"Broken link in '{rel_path}': '{raw_link}' -> '{resolved}' does not exist")

    return broken


def scaffold_skill_command(
    root_dir: Path,
    target: str = "all",
    output_dir: Path | str | None = None,
    dry_run: bool = False,
    force: bool = False,
    project_name: str = "SpecOps",
) -> int:
    """Executes 'spec-ops scaffold skill' CLI command."""
    normalized_target = target.strip().lower()
    if normalized_target not in SUPPORTED_SKILL_TARGETS:
        print(
            f"❌ Error: Unsupported target platform '{target}'. "
            f"Supported platforms: {', '.join(SUPPORTED_SKILL_TARGETS)}",
            file=sys.stderr,
        )
        return 1

    dest_dir = Path(output_dir).resolve() if output_dir else root_dir.resolve()
    bundle = generate_skill_bundle(
        target=normalized_target,
        root_dir=root_dir,
        project_name=project_name,
    )

    broken_links = validate_bundle_links(bundle, root_dir=dest_dir)
    if broken_links:
        print("❌ Error: Broken links detected in skill bundle:", file=sys.stderr)
        for err in broken_links:
            print(f"   - {err}", file=sys.stderr)
        return 1

    existing_files: list[str] = []
    for rel_path in sorted(bundle.keys()):
        p = dest_dir / rel_path
        if p.exists():
            existing_files.append(rel_path)

    if existing_files and not force and not dry_run:
        print(
            f"⚠️ Error: {len(existing_files)} target file(s) already exist. "
            f"Use --force to overwrite (e.g. '{existing_files[0]}').",
            file=sys.stderr,
        )
        return 1

    if dry_run:
        print(f"🔍 Dry run: Skill bundle for target '{normalized_target}' verified without errors.")
        print(f"   Candidate files ({len(bundle)}):")
        for rel_path in sorted(bundle.keys()):
            status = "overwrite" if rel_path in existing_files else "create"
            print(f"   - [{status}] {rel_path}")
        return 0

    created_count = 0
    overwritten_count = 0
    for rel_path, content in bundle.items():
        p = dest_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            overwritten_count += 1
        else:
            created_count += 1
        p.write_text(content.strip() + "\n", encoding="utf-8")

    action_label = f"{created_count} created, {overwritten_count} overwritten" if overwritten_count else f"{created_count} created"
    print(f"✨ Successfully scaffolded skill bundle for target '{normalized_target}' ({action_label}):")
    for rel_path in sorted(bundle.keys()):
        print(f"   - {rel_path}")

    return 0
