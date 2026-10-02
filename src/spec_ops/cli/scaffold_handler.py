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

    if action == "hooks":
        from ..scaffold.native_hooks import scaffold_hooks_command

        res, msg = scaffold_hooks_command(
            config.root_dir,
            force=getattr(args, "force", False),
            native=getattr(args, "native", True),
        )
        print(f"✨ {msg}" if res == 0 else f"❌ {msg}")
        return res

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

    if action == "ci":
        from ..scaffold.ci_multi import scaffold_ci_command

        platform = getattr(args, "platform", "all")
        force = bool(getattr(args, "force", False) or getattr(args, "update", False))
        matrix = getattr(args, "matrix", None)
        timeout = getattr(args, "timeout_minutes", None)
        return scaffold_ci_command(
            root_dir=config.root_dir,
            platform=platform,
            force=force,
            matrix=matrix,
            project_name=config.project.name,
            timeout_minutes=timeout,
        )

    if action == "skill":
        from ..scaffold.skill_packager import scaffold_skill_command

        target = getattr(args, "target", "all")
        output_dir = getattr(args, "output_dir", None)
        dry_run = bool(getattr(args, "dry_run", False))
        force = bool(getattr(args, "force", False))
        return scaffold_skill_command(
            root_dir=config.root_dir,
            target=target,
            output_dir=output_dir,
            dry_run=dry_run,
            force=force,
            project_name=config.project.name,
        )

    parser.parse_args(["scaffold", "--help"])
    return 0

