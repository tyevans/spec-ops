"""CLI command handlers for release notes and customer-facing changelogs (US-0049, PRD-0003)."""

from __future__ import annotations

import argparse

from ..config.models import SpecOpsConfig
from ..prd.release_notes import generate_release_notes
from ..release.customer_notes import generate_customer_release_notes


def handle_release_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Dispatches release subcommands."""
    action = getattr(args, "release_action", None)
    if action not in ("notes", None):
        try:
            parser.parse_args(["release", "notes", "--help"])
        except SystemExit:
            pass
        return 1

    prd_id = getattr(args, "prd_id", None)
    milestone = getattr(args, "milestone", None)
    format_type = getattr(args, "format", "markdown").lower()
    branded = getattr(args, "branded", False)
    out_path = getattr(args, "output", None)
    publish = getattr(args, "publish", False)

    target = prd_id or milestone
    if not target:
        try:
            parser.parse_args(["release", "notes", "--help"])
        except SystemExit:
            pass
        return 1

    is_milestone = False
    if milestone:
        is_milestone = True
    elif prd_id:
        p_upper = prd_id.upper()
        if (p_upper.startswith("M") and not p_upper.startswith("PRD")) or "MILESTONE" in p_upper:
            is_milestone = True
            milestone = prd_id

    if is_milestone and milestone:
        dest, content = generate_release_notes(
            milestone_id=milestone,
            config=config,
            format_type=format_type,
            branded=branded,
            output_path=out_path,
        )
        if format_type == "html":
            print(content)
        else:
            print(f"✅ Generated customer release notes at {dest}")
        return 0

    dest, content = generate_customer_release_notes(
        prd_id=target,
        config=config,
        format_type=format_type,
        branded=branded,
        output_path=out_path,
        publish=publish,
    )

    if format_type in ("html", "json"):
        print(content)
    else:
        print(f"✅ Generated customer release notes at {dest}")
    return 0
