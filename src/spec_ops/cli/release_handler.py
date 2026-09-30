"""CLI command handlers for release notes and customer-facing changelogs (US-0049)."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..prd.release_notes import generate_release_notes


def handle_release_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Dispatches release subcommands."""
    action = getattr(args, "release_action", None)
    milestone = getattr(args, "milestone", None)
    if action not in ("notes", None) or not milestone:
        try:
            parser.parse_args(["release", "notes", "--help"])
        except SystemExit:
            pass
        return 1


    format_type = getattr(args, "format", "markdown")
    branded = getattr(args, "branded", False)
    out_path = getattr(args, "output", None)

    dest, content = generate_release_notes(
        milestone_id=milestone,
        config=config,
        format_type=format_type,
        branded=branded,
        output_path=out_path,
    )

    if format_type.lower() == "html":
        print(content)
    else:
        print(f"✅ Generated customer release notes at {dest}")
    return 0
