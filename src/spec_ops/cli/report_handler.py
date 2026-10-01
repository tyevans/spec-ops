"""CLI command handlers for executive reporting, burndown decks, and milestone alignment."""

from __future__ import annotations

import argparse
import json
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

    if action == "velocity":
        from ..backlog.velocity import calculate_hybrid_velocity, save_velocity_snapshot
        from ..backlog.velocity_dashboard import export_velocity_dashboard
        from ..backlog.velocity_format import format_rescues_table, format_velocity_table

        window = getattr(args, "window", "14d") or "14d"
        include_rescues = getattr(args, "rescues", False)
        as_json = getattr(args, "json", False)
        export_val = getattr(args, "export", None)
        fmt = getattr(args, "format", None)
        out_path = getattr(args, "output", None)

        is_html = (
            fmt == "html"
            or export_val == "html"
            or (export_val and (export_val.endswith(".html") or export_val.endswith(".svg")))
            or (out_path and out_path.endswith(".html"))
        )
        if export_val and not out_path and (export_val.endswith(".html") or export_val.endswith(".svg")):
            out_path = export_val

        report = calculate_hybrid_velocity(
            config.root_dir,
            window=window,
            include_rescues=include_rescues or is_html,
        )
        save_velocity_snapshot(report, config.root_dir)

        if is_html:
            dest = export_velocity_dashboard(report, output_path=out_path, repo_root=config.root_dir)
            print(f"✅ Exported velocity report to {dest}")
            return 0

        if as_json or fmt == "json" or export_val == "json":
            print(json.dumps(report.to_dict(), indent=2))
            return 0

        console = Console()
        console.print(format_velocity_table(report))
        if include_rescues and report.rescues:
            console.print()
            console.print(format_rescues_table(report))
            burden_pct = f"{report.rescues.rescue_burden_ratio * 100.0:.1f}%"
            console.print(
                f"[bold cyan]Rescue Burden Ratio:[/] {burden_pct}  "
                f"[bold cyan]Mean Time to Unblock:[/] {report.rescues.mean_time_to_unblock_minutes} minutes"
            )
        return 0

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
