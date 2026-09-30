"""CLI command handlers for executive reporting, burndown decks, and milestone alignment."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..config.models import SpecOpsConfig
from ..visualizer.burndown_deck import (
    calculate_milestone_burndown,
    check_scope_alignment,
    export_burndown_deck,
    format_milestone_digest,
)


def handle_report_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Dispatches executive reporting subcommands."""
    action = getattr(args, "report_action", None)
    if not action:
        parser.parse_args(["report", "--help"])
        return 1

    check_align = getattr(args, "check_alignment", False)
    if check_align:
        unanchored_count, unanchored_tasks = check_scope_alignment(config)
        if unanchored_count > 0:
            console = Console()
            console.print(f"⚠️ Scope Alignment Warning: {unanchored_count} completed tasks unanchored from ROADMAP.md", style="bold yellow")
            table = Table(title="Unanchored Completed Backlog Tasks", expand=True, border_style="dim")
            table.add_column("Task ID", style="bold cyan", width=12)
            table.add_column("Title", style="white")
            table.add_column("Target BC", style="green", width=14)
            table.add_column("Authoring Commit", style="dim", width=16)
            for t in unanchored_tasks:
                table.add_row(t["id"], t["title"], t["target_bc"], t["commit"])
            console.print(table)
            return 0
        else:
            print("✅ All completed tasks are anchored to documented milestones in ROADMAP.md.")
            return 0

    milestone_id = getattr(args, "milestone", None) or "M1-MVP"
    fmt = getattr(args, "format", "deck")
    out_path = getattr(args, "output", None)

    if fmt == "digest":
        burndown = calculate_milestone_burndown(milestone_id, config)
        digest = format_milestone_digest(burndown)
        if out_path:
            dest = Path(out_path)
            if not dest.is_absolute():
                dest = config.root_dir / dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(digest, encoding="utf-8")
            print(f"✅ Exported milestone briefing digest to {dest}")
        else:
            print(digest)
        return 0

    dest = export_burndown_deck(milestone_id, config, output_path=out_path, format=fmt)
    print(f"✅ Exported presentation slide deck to {dest}")
    return 0
