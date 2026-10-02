"""CLI command handler for backlog queue, dependency trees, and blocker resolution."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

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

    if action == "next":
        ready = queue.get_ready_unblocked_tasks()
        target_task = ready[0] if ready else None
        if not target_task:
            for t in queue.list_all_tasks():
                if t.status == "Refined":
                    target_task = t
                    break

        if getattr(args, "json", False):
            from .formatters import format_task_json
            print(format_task_json(target_task, config))
            return 0

        if not target_task:
            print("ℹ️ No ready, unblocked tasks in refined/ buffer. Run 'spec-ops curate' first.")
            return 0

        clean_id = target_task.canonical_id.lower().replace("task-", "").replace("spike-", "")
        branch = target_task.branch or f"{config.execution.git_branch_prefix}task-{clean_id}"
        print(f"=== Next Backlog Task ({target_task.canonical_id}) ===")
        print(f"Title:        {target_task.title}")
        print(f"Branch:       {branch}")
        print(f"Target BC:    {target_task.target_bc or 'None'}")
        print(f"Dependencies: {', '.join(target_task.dependencies) or 'None'}")
        print(f"Governing ADRs: {', '.join(target_task.governing_adrs) or 'None'}")
        return 0

    if action == "claim":
        auto = getattr(args, "auto", False)
        target = getattr(args, "task_id", None)
        claimant = getattr(args, "worker_id", None) or os.environ.get("SPECOPS_WORKER_ID") or os.environ.get("SPECOPS_CLAIMANT") or "spec-ops-worker"
        from ..worker.claimer import TaskClaimer

        claimer = TaskClaimer(config)
        res = claimer.claim_auto(claimant=claimant) if (auto or not target) else claimer.claim_task(target, claimant=claimant)
        if res:
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"✅ Claimed {res['task_id']} for {claimant} on {res['branch']}")
            return 0
        print("❌ No ready, unblocked tasks available to claim.", file=sys.stderr)
        return 1

    if action == "refine":
        target_task = _find_task_in_queue(queue, args.task_id, config)
        if not target_task:
            print(f"❌ Task {args.task_id} not found in backlog.", file=sys.stderr)
            return 1

        from ..backlog.dor_gate import audit_task_health

        strict_mode = getattr(args, "strict", False)
        report = audit_task_health(target_task, config, strict=strict_mode)
        if not report.is_ready:
            print("❌ Definition of Ready (DoR) validation failed:")
            print(report.format_report())
            return 1

        dest = queue.refine_task(target_task)
        print(f"✅ Promoted task {target_task.canonical_id} to refined/ ({dest.name}).")
        return 0

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
        from ..app.task_lifecycle import TaskLifecycleService
        lifecycle = TaskLifecycleService(config)
        ok, msg = lifecycle.complete_task_with_gate(
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

    if action == "monitor":
        from ..tui.flow_monitor import FlowMonitor

        monitor = FlowMonitor(config)
        if getattr(args, "once", False):
            monitor.render_snapshot()
            return 0
        return monitor.run()

    if action == "doctor":
        from ..backlog.doctor import run_backlog_doctor

        backlog_dir = getattr(args, "dir", None)
        target_dir = Path(backlog_dir) if backlog_dir else config.backlog_dir
        fix = bool(getattr(args, "fix", False) or getattr(args, "repair", False))
        as_json = bool(getattr(args, "json", False))
        return run_backlog_doctor(target_dir, fix=fix, as_json=as_json)

    if action == "digest":
        from ..backlog.digest import generate_standup_digest

        fmt = getattr(args, "format", "markdown") or "markdown"
        window = getattr(args, "window", "24h") or "24h"
        digest_output = generate_standup_digest(config, window=window, fmt=fmt)
        print(digest_output)
        if getattr(args, "reclaim_stalled", False):
            from ..backlog.reclaim import reclaim_stalled_claims

            rec = reclaim_stalled_claims(config, timeout_hours=4.0)
            if rec.reclaimed_count > 0:
                print(f"\n🔄 Reclaimed {rec.reclaimed_count} stalled claim(s): {', '.join(rec.reclaimed_ids)}")
        return 0

    if action == "reorder":
        from ..backlog.reranker import BacklogReranker

        dry_run = getattr(args, "dry_run", False)
        topological = getattr(args, "topological", False)
        by_weights = getattr(args, "by_weights", False)
        if not topological and not by_weights:
            by_weights = True
            topological = True
        elif by_weights:
            topological = True

        reranker = BacklogReranker(config.backlog_dir)
        ok, msg, result = reranker.apply(
            dry_run=dry_run,
            by_weights=by_weights,
            topological=topological,
        )

        if getattr(args, "json", False):
            payload = result.to_dict()
            payload["success"] = ok
            payload["message"] = msg
            payload["dry_run"] = dry_run
            print(json.dumps(payload, indent=2))
            return 0 if ok else 1

        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            return 1

        if result.inversions:
            console.print(f"⚠️  [bold yellow]Detected {len(result.inversions)} priority inversion(s):[/bold yellow]")
            for inv in result.inversions:
                console.print(f"   • {inv}")

        if dry_run:
            console.print(f"🔍 [bold cyan]{msg}[/bold cyan]")
            table = Table(title="Proposed Backlog Priority Order (Dry Run)", expand=True)
            table.add_column("Rank", style="bold cyan")
            table.add_column("Task ID", style="bold white")
            table.add_column("Title", style="white")
            table.add_column("Status", style="yellow")
            table.add_column("Score", style="green")
            for idx, t in enumerate(result.ordered_tasks, start=1):
                sc = result.scores.get(t.canonical_id)
                score_str = f"{sc.total_score:.1f}" if sc else "-"
                table.add_row(str(idx), t.canonical_id, t.title, t.status, score_str)
            console.print(table)
            return 0

        console.print(f"✅ [bold green]{msg}[/bold green]")
        return 0

    if action == "reclaim-stalled":
        from ..backlog.reclaim import reclaim_stalled_claims

        timeout = float(getattr(args, "timeout_hours", 4.0) or 4.0)
        dry_run = bool(getattr(args, "dry_run", False))
        result = reclaim_stalled_claims(config, timeout_hours=timeout, dry_run=dry_run)
        if getattr(args, "json", False):
            print(json.dumps(result.to_dict(), indent=2))
        else:
            result.render_console(console)
        return 0

    parser.parse_args(["queue", "--help"])
    return 0


def _find_task_in_queue(
    queue: BacklogQueue, task_ref: str, config: SpecOpsConfig | None = None
) -> Any:
    """Finds a task in the backlog queue by canonical ID, raw number, filename, or disk path."""
    task_ref_str = str(task_ref).strip()
    task_file_stem = Path(task_ref_str).stem.upper()
    task_file_name = Path(task_ref_str).name.lower()

    clean_id = task_ref_str.upper()
    if not clean_id.startswith("TASK-") and not clean_id.startswith("SPIKE-") and clean_id.isdigit():
        clean_id = f"TASK-{clean_id.zfill(4)}"

    for t in queue.list_all_tasks():
        if (
            t.canonical_id == clean_id
            or t.canonical_id == task_ref_str.upper()
            or t.id == task_ref_str
            or t.file_path.name.lower() == task_file_name
            or task_file_stem in t.canonical_id
            or t.canonical_id in task_file_stem
            or t.file_path.stem.upper() == task_file_stem
        ):
            return t

    candidate = Path(task_ref_str)
    if not candidate.is_absolute() and config:
        candidate = config.root_dir / candidate
    if candidate.is_file():
        from ..core.parser import parse_task

        return parse_task(candidate)
    return None


def handle_verify_dor_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Audits backlog tasks against the 7 Definition of Ready (DoR) criteria."""
    queue = BacklogQueue(config.backlog_dir)
    strict_mode = getattr(args, "strict", False)
    task_ref = getattr(args, "task_id", None)
    from ..backlog.dor_gate import audit_task_health

    if task_ref:
        target_task = _find_task_in_queue(queue, task_ref, config)
        if not target_task:
            print(f"❌ Task {task_ref} not found in backlog.", file=sys.stderr)
            return 1
        report = audit_task_health(target_task, config, strict=strict_mode)
        print(report.format_report())
        return 0 if report.is_ready else 1

    all_tasks = queue.list_all_tasks()
    proposed = [t for t in all_tasks if t.status == "Proposed"]
    if not proposed:
        print("ℹ️ No proposed tasks found in backlog to audit.")
        return 0

    all_ready = True
    for t in proposed:
        report = audit_task_health(t, config, strict=strict_mode)
        print(report.format_report())
        if not report.is_ready:
            all_ready = False

    return 0 if all_ready else 1
