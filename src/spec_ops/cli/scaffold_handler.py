"""CLI handler for scaffold commands (agents, docs, diataxis)."""

from __future__ import annotations

import argparse

from ..config.models import SpecOpsConfig
from ..scaffold.docs_scaffold import (
    DocumentationExistsError,
    InvalidBoundedContextError,
    scaffold_bc_docs,
)


def handle_scaffold_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Executes 'spec-ops scaffold' commands."""
    action = getattr(args, "scaffold_action", None)
    if action == "agents":
        from ..scaffold.agents_md import scaffold_agents_command

        msg = scaffold_agents_command(config.root_dir)
        print(f"✨ {msg}")
        return 0

    if action in ("docs", "diataxis"):
        bc = getattr(args, "bc", None)
        if not bc:
            print("❌ Error: --bc / --bounded-context is required.")
            return 1
        title = getattr(args, "title", None)
        force = bool(getattr(args, "force", False))
        try:
            created = scaffold_bc_docs(config.root_dir, bc=bc, title=title, force=force)
            print(
                f"✨ Successfully scaffolded Diataxis documentation for bounded context '{bc}' ({len(created)} files):"
            )
            for p in created:
                try:
                    rel = p.relative_to(config.root_dir)
                    print(f"   - {rel}")
                except ValueError:
                    print(f"   - {p}")
            return 0
        except DocumentationExistsError:
            print(f"⚠️ Warning: Diataxis documentation for '{bc}' already exists. Use --force to overwrite.")
            return 1
        except (InvalidBoundedContextError, ValueError) as e:
            print(f"❌ Error: {e}")
            return 1

    parser.parse_args(["scaffold", "--help"])
    return 0
