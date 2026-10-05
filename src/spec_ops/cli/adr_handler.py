"""CLI command handler for Architectural Decision Record (ADR) supersession and amendment."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..adrs.amend import CircularAmendmentError
from ..adrs.amendment import ADRAmendmentEngine
from ..adrs.supersede import ADRNotFoundError, CircularSupersessionError
from ..adrs.supersession import ADRSupersessionEngine
from ..config.models import SpecOpsConfig


def handle_adr_command(args: Any, config: SpecOpsConfig) -> int:
    """Dispatches 'spec-ops adr' subcommands."""
    action = getattr(args, "adr_action", None)
    if action == "supersede":
        old_id = getattr(args, "opt_old", None) or getattr(args, "old_id", None)
        new_target = getattr(args, "by", None) or getattr(args, "new_id_pos", None)
        title = getattr(args, "title", None)
        dry_run = getattr(args, "dry_run", False)

        if not old_id:
            print("❌ Error: Target ADR ID to supersede must be specified.", file=sys.stderr)
            return 1

        if not new_target and not title:
            print(
                "❌ Error: Superseding ADR must be specified via --by, positional argument, or --title.",
                file=sys.stderr,
            )
            return 1

        try:
            engine = ADRSupersessionEngine(root_dir=config.root_dir)
            res = engine.supersede(
                old_target=old_id,
                new_target=new_target,
                title=title,
                dry_run=dry_run,
            )
            mode_prefix = "[Simulated] " if dry_run else ""
            print(f"✨ {mode_prefix}Superseded {res.old_id} by {res.new_id}")
            print(f"📄 Updated {res.old_file.relative_to(config.root_dir)} status to 'Superseded'")
            print(f"📄 Generated {res.new_file.relative_to(config.root_dir)} status as 'Accepted'")
            print(f"📋 Synchronized {config.docs_dir / 'adrs' / 'REGISTRY.md'}")
            for w in res.warnings:
                print(f"⚠️ Warning: {w}")
            return 0
        except (CircularSupersessionError, ADRNotFoundError, ValueError, FileNotFoundError) as err:
            print(f"❌ Error: {err}", file=sys.stderr)
            return 1

    if action == "amend":
        old_id = getattr(args, "opt_old", None) or getattr(args, "old_id", None)
        new_target = getattr(args, "by", None) or getattr(args, "new_id_pos", None)
        title = getattr(args, "title", None)
        dry_run = getattr(args, "dry_run", False)

        if not old_id:
            print("❌ Error: Target ADR ID to amend must be specified.", file=sys.stderr)
            return 1

        if not new_target and not title:
            print(
                "❌ Error: Amending ADR must be specified via --by, positional argument, or --title.",
                file=sys.stderr,
            )
            return 1

        try:
            engine = ADRAmendmentEngine(root_dir=config.root_dir)
            res = engine.amend(
                old_target=old_id,
                new_target=new_target,
                title=title,
                dry_run=dry_run,
            )
            mode_prefix = "[Simulated] " if dry_run else ""
            print(f"✨ {mode_prefix}Amended {res.old_id} with {res.new_id}")
            print(f"📄 Target {res.old_file.relative_to(config.root_dir)} recorded amendment in 'amended_by'")
            print(f"📄 Generated/promoted {res.new_file.relative_to(config.root_dir)} status as 'Accepted'")
            print(f"📋 Synchronized {config.docs_dir / 'adrs' / 'REGISTRY.md'}")
            for w in res.warnings:
                print(f"⚠️ Warning: {w}")
            return 0
        except (CircularAmendmentError, ADRNotFoundError, ValueError, FileNotFoundError) as err:
            print(f"❌ Error: {err}", file=sys.stderr)
            return 1

    print("Usage: spec-ops adr {supersede|amend} <old-id> [--title <title> | --by <new-id>]", file=sys.stderr)
    return 1
