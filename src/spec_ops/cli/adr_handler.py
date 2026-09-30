"""CLI command handler for Architectural Decision Record (ADR) supersession."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..adrs.supersede import ADRNotFoundError, CircularSupersessionError, supersede_adr
from ..config.models import SpecOpsConfig


def handle_adr_command(args: Any, config: SpecOpsConfig) -> int:
    """Dispatches 'spec-ops adr' subcommands."""
    action = getattr(args, "adr_action", None)
    if action == "supersede":
        new_target = getattr(args, "by", None) or getattr(args, "new_id_pos", None)
        if not new_target:
            print(
                "❌ Error: Superseding ADR must be specified via --by, --with, or positional argument.",
                file=sys.stderr,
            )
            return 1

        try:
            res = supersede_adr(
                old_target=args.old_id,
                new_target=new_target,
                docs_dir=config.project_docs_dir,
            )
            print(f"✨ Superseded {res.old_id} by {res.new_id}")
            print(f"📄 Updated {res.old_file.relative_to(config.root_dir)} status to 'Superseded'")
            print(f"📄 Promoted {res.new_file.relative_to(config.root_dir)} status to 'Accepted'")
            print(f"📋 Updated {config.docs_dir / 'adrs' / 'REGISTRY.md'}")
            for w in res.warnings:
                print(f"⚠️ Warning: {w}")
            return 0
        except (CircularSupersessionError, ADRNotFoundError, ValueError, FileNotFoundError) as err:
            print(f"❌ Error: {err}", file=sys.stderr)
            return 1

    print("Usage: spec-ops adr supersede <old-id> --by <new-id>", file=sys.stderr)
    return 1
