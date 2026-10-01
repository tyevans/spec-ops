"""CLI command handler for milestone scope transitions, planning studio, and rollover.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0025, US-0077.
Deals strictly with public CLI frontdoors and keeps source under 400 lines.
"""

from __future__ import annotations

import argparse
import json
import sys

from ..backlog.rollover import MilestoneRolloverCoordinator
from ..config.loader import SpecOpsConfig


def handle_milestone_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser | None = None,
) -> int:
    """Dispatches milestone CLI subcommands."""
    action = getattr(args, "milestone_action", None)
    if action == "rollover":
        from_m = getattr(args, "from_m", None)
        to_m = getattr(args, "to_m", None)
        dry_run = bool(getattr(args, "dry_run", False))
        as_json = bool(getattr(args, "json", False))

        if not from_m or not to_m:
            if parser:
                parser.parse_args(["milestone", "rollover", "--help"])
            else:
                print("Error: Both --from and --to milestone identifiers are required.", file=sys.stderr)
            return 1

        coordinator = MilestoneRolloverCoordinator(config)
        result = coordinator.rollover(from_milestone=from_m, to_milestone=to_m, dry_run=dry_run)

        if as_json:
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        header = "=== Milestone Rollover (Dry Run) ===" if dry_run else "=== Milestone Rollover ==="
        print(header)
        print(f"From: {result.from_milestone}")
        print(f"To:   {result.to_milestone}")

        if result.transitioned_count == 0:
            print(f"No unfinished tasks found assigned to milestone '{result.from_milestone}'.")
            return 0

        action_word = (
            "Candidate tasks for rollover"
            if dry_run
            else f"Successfully rolled over {result.transitioned_count} task(s) to '{result.to_milestone}'"
        )
        print(f"{action_word}:")
        for detail in result.details:
            prefix = "  •" if dry_run else "  ✓"
            print(f"{prefix} {detail.task_id}: {detail.title}")

        return 0

    if action == "plan":
        simulate = bool(getattr(args, "simulate", False))
        assign = list(getattr(args, "assign", []) or [])
        save = bool(getattr(args, "save", False))
        as_json = bool(getattr(args, "json", False))
        non_interactive = bool(getattr(args, "non_interactive", False))

        from ..backlog.milestone_studio import MilestoneStudio

        studio = MilestoneStudio(config)
        result = studio.execute(
            simulate=simulate,
            assignments=assign,
            save=save,
            non_interactive=non_interactive,
        )

        if as_json:
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        studio.render(result)
        return 0

    if parser:
        parser.parse_args(["milestone", "--help"])
    else:
        print("Usage: spec-ops milestone <rollover|plan> [options]")
    return 0
