"""CLI command handler for backlog queue, dependency trees, and blocker resolution."""

from __future__ import annotations

import argparse
import json
import sys

from rich.console import Console
from rich.table import Table

from ..backlog.blockers import block_task, list_project_blockers, unblock_task
from ..backlog.queue import BacklogQueue
from ..backlog.tree import TaskDependencyTreeEngine
from ..config.models import SpecOpsConfig


def handle_queue_command(
    args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser
) -> int:
    """Dispatches queue actions: complete, tree, block, unblock, blockers."""
    action = getattr(args, "queue_action", None)
    if not action:
        parser.parse_args(["queue", "--help"])
        return 0

    queue = BacklogQueue(config.backlog_dir)
    console = Console()

    if action == "complete":
        clean_id = args.task_id.upper()
        if not clean_id.startswith("TASK-") and clean_id.isdigit():
            clean_id = f"TASK-{clean_id.zfill(4)}"

        target_task = None
        for t in queue.list_all_tasks():
            if t.canonical_id == clean_id:
                target_task = t
                break

        if not target_task:
            print(f"❌ Task {args.task_id} not found in backlog.", file=sys.stderr)
            return 1

        base = getattr(args, "base", "main")
        ok, msg = queue.complete_task_with_gate(
            target_task, base_branch=base, repo_root=config.root_dir, config=config
        )
        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            print(msg)
            return 1
        print(f"✅ {msg}")
        return 0

    if action == "tree":
        tasks = queue.list_all_tasks()
        engine = TaskDependencyTreeEngine(
            tasks, completed_ids=queue.get_completed_task_ids()
        )

        if getattr(args, "json", False):
            print(json.dumps(engine.to_dict(), indent=2))
            return 0

        if getattr(args, "waves", False):
            panel = engine.render_waves_panel()
            console.print(panel)
            return 0

        is_reverse = (
            getattr(args, "reverse", False)
            or getattr(args, "direction", "blocks") == "blocked-by"
        )
        focus_id = getattr(args, "task", None)
        include_completed = getattr(args, "all", False)

        if is_reverse:
            tree = engine.build_prerequisite_tree(
                focus_id=focus_id, include_completed=include_completed
            )
        else:
            tree = engine.build_forward_tree(
                focus_id=focus_id, include_completed=include_completed
            )

        console.print(tree)
        return 0

    if action == "block":
        ok, msg, _ = block_task(
            config.backlog_dir,
            args.task_id,
            question=args.question,
            blocker_type=getattr(args, "type", "unknown"),
            create_spike_flag=getattr(args, "spike", False),
            timebox=getattr(args, "timebox", "2h"),
            raised_by=getattr(args, "raised_by", ""),
            root_dir=config.root_dir,
        )
        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            return 1
        print(f"🛑 {msg}")
        return 0

    if action == "unblock":
        ok, msg, _ = unblock_task(
            config.backlog_dir,
            args.task_id,
            resolution=args.resolution,
            adr_id=getattr(args, "adr", None),
        )
        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            return 1
        print(f"✅ {msg}")
        return 0

    if action == "blockers":
        blockers = list_project_blockers(config.backlog_dir)
        if getattr(args, "json", False):
            print(json.dumps(blockers, indent=2))
            return 0

        if not blockers:
            console.print(
                "✅ [bold green]Zero active blockers or unresolved unknowns in project backlog.[/bold green]"
            )
            return 0

        table = Table(
            title=f"🛑 Active Backlog Blockers & Unknowns ({len(blockers)})",
            expand=True,
            border_style="red",
        )
        table.add_column("Task ID", style="bold cyan")
        table.add_column("Title", style="white")
        table.add_column("Type", style="yellow")
        table.add_column("Unresolved Question / Impediment", style="bold red")
        table.add_column("Linked Spike", style="cyan")

        for b in blockers:
            table.add_row(
                b["task_id"],
                b["title"],
                b["type"],
                b["question"],
                b["spike_id"] or "None",
            )
        console.print(table)
        return 0

    parser.parse_args(["queue", "--help"])
    return 0
