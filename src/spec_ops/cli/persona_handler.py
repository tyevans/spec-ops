"""CLI command handlers for persona discovery and living maintenance."""

from __future__ import annotations

import argparse
import json
import sys

from ..config.models import SpecOpsConfig
from ..core.persona_engine import PersonaEngine


def handle_persona_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser | None = None,
) -> int:
    """Dispatches spec-ops persona subcommands (audit and sync)."""
    action = getattr(args, "persona_action", None)
    if not action:
        if parser:
            try:
                parser.parse_args(["persona", "--help"])
            except SystemExit:
                pass
        return 0

    engine = PersonaEngine(config.root_dir)

    if action == "audit":
        res = engine.audit()
        if getattr(args, "json", False):
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(res.format_text())
        return 0

    if action == "sync":
        apply_flag = getattr(args, "apply", False)
        res = engine.sync(apply=apply_flag)

        if getattr(args, "json", False):
            print(json.dumps(res.to_dict(), indent=2))
            return 0

        if not res.emerging_archetypes:
            print("✅ All archetypes are synchronized with PERSONAS.md. No emerging archetypes found.")
            return 0

        print(f"=== SpecOps Persona Sync: {len(res.emerging_archetypes)} Emerging Archetype(s) Discovered ===")
        for arch in res.emerging_archetypes:
            sources_str = ", ".join(arch.sources)
            print(f"  • {arch.name} ({arch.role}) — Cited in: {sources_str}")

        if res.diff:
            print("\nProposed Changes to docs/project/user_stories/PERSONAS.md:")
            print(res.diff)

        if res.applied:
            print(f"\n✨ Successfully applied {len(res.emerging_archetypes)} new persona profile(s) to PERSONAS.md")
        else:
            print("\n💡 Run 'spec-ops persona sync --apply' to write these additions to PERSONAS.md")
        return 0

    return 0
