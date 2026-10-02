"""CLI command handlers for worker, cycle, and rescue commands."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..backlog.curator import BacklogCurator
from ..backlog.health import HealthChecker
from ..backlog.queue import BacklogQueue
from ..config.models import SpecOpsConfig
from ..prd.decomposer import PRDDecomposer
from ..prd.manager import PRDManager
from ..worker import BacklogWorkerEngine, BatchCycleOrchestrator


def handle_worker_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops worker' command execution."""
    if getattr(args, "telemetry", False):
        import json
        from ..visualizer.telemetry_script import aggregate_fleet_telemetry, harvest_fleet_telemetry

        records = harvest_fleet_telemetry(config)
        aggregated = aggregate_fleet_telemetry(records)

        if getattr(args, "json", False):
            print(json.dumps(aggregated, indent=2))
            return 0

        from rich.console import Console
        from rich.table import Table

        console = Console(width=180)
        table = Table(title=f"SpecOps Worker Fleet Telemetry ({config.project.name})")
        table.add_column("Task ID", style="bold cyan")
        table.add_column("Worktree Directory", style="dim")
        table.add_column("Branch", style="green")
        table.add_column("Status", style="bold", no_wrap=True)
        table.add_column("Retries", justify="center")
        table.add_column("Preflight Hook", style="yellow")
        table.add_column("Elapsed", justify="right")
        table.add_column("Memory", justify="right")
        table.add_column("Rescue Command", style="magenta")

        for r in records:
            st = r.get("status", "Running")
            st_style = "red bold" if r.get("stalled") else ("yellow" if "healing" in st.lower() else "green")
            table.add_row(
                r.get("task_id", ""),
                r.get("worktree_path", ""),
                r.get("branch", ""),
                f"[{st_style}]{st}[/{st_style}]",
                r.get("retries") or r.get("attempt") or "0/3",
                r.get("current_preflight_hook") or r.get("active_preflight_check") or "",
                r.get("elapsed_runtime", "0s"),
                r.get("memory_usage", "0 MB"),
                r.get("rescue_cmd", ""),
            )

        console.print(table)
        summary = (
            f"Total: {aggregated['total']} | Active: {aggregated['active']} | "
            f"Stalled: {aggregated['stalled']} | Rescued: {aggregated['rescued']} | "
            f"Completed: {aggregated['completed']} | Memory: {aggregated['total_memory_mb']} MB"
        )
        console.print(f"[bold]{summary}[/bold]")
        if aggregated["stalled"] > 0:
            console.print(f"[bold red]⚠️  Alert: {aggregated['stalled']} worker(s) stalled: {', '.join(aggregated['stalled_tasks'])}[/bold red]")
            console.print("[dim]Run 'spec-ops rescue <task-id>' to take over.[/dim]")
        return 0

    action_or_task = getattr(args, "action_or_task", None)
    task_pos = getattr(args, "task_pos", None)
    auto_flag = getattr(args, "auto", False)

    if action_or_task and action_or_task.lower() in ("ci-heal", "ci_heal"):
        from ..worker.ci_repair import ci_heal_task
        target_id = getattr(args, "task", None) or task_pos
        if not target_id:
            print("❌ Error: --task <task-id> is required for ci-heal.", file=sys.stderr)
            return 1
        ok, msg = ci_heal_task(
            config,
            target_id,
            dry_run=getattr(args, "dry_run", False),
            no_push=getattr(args, "no_merge", False),
        )
        print(f"=== Remote CI Heal ({target_id}) ===")
        print(f"Status: {'✅ SUCCESS' if ok else '❌ FAILED'}")
        print(f"Message: {msg}")
        return 0 if ok else 1

    if (action_or_task and action_or_task.lower() == "claim") or auto_flag:
        import json
        from ..worker.claimer import TaskClaimer
        claimer = TaskClaimer(config)
        target = task_pos or getattr(args, "task", None)
        claimant = getattr(args, "worker_id", None) or os.environ.get("SPECOPS_WORKER_ID") or os.environ.get("SPECOPS_CLAIMANT") or "spec-ops-worker"
        res = claimer.claim_auto(claimant=claimant) if (auto_flag or not target) else claimer.claim_task(target, claimant=claimant)
        if res:
            print(json.dumps(res, indent=2))
            return 0
        return 1

    if getattr(args, "drain", False) or getattr(args, "max_tasks", None) is not None or getattr(args, "max_concurrency", 1) > 1:
        orchestrator = BatchCycleOrchestrator(
            config,
            max_concurrency=getattr(args, "max_concurrency", 1),
            max_tasks=getattr(args, "max_tasks", None),
            drain=getattr(args, "drain", False),
            dry_run=args.dry_run,
            no_merge=args.no_merge,
        )
        report = orchestrator.run()
        return 0 if not report.tasks_failed else 1

    worker = BacklogWorkerEngine(config)
    queue = BacklogQueue(config.backlog_dir)
    target_task = None
    target_task_id = args.task
    action_or_task = getattr(args, "action_or_task", None)
    task_pos = getattr(args, "task_pos", None)
    if action_or_task:
        if action_or_task.lower() == "execute":
            target_task_id = task_pos or target_task_id
        else:
            target_task_id = action_or_task or target_task_id
    elif task_pos:
        target_task_id = task_pos

    if target_task_id:
        clean_id = target_task_id.upper()
        if not clean_id.startswith("TASK-") and clean_id.isdigit():
            clean_id = f"TASK-{clean_id.zfill(4)}"
        for t in queue.list_all_tasks():
            if t.canonical_id == clean_id:
                target_task = t
                break
        if not target_task:
            print(f"❌ Task {target_task_id} not found in backlog.")
            return 1
    else:
        ready = queue.get_ready_unblocked_tasks()
        if not ready:
            print("ℹ️ No ready, unblocked tasks in refined/ buffer. Run 'spec-ops curate' first.")
            return 0
        target_task = ready[0]

    res = worker.execute_task(
        target_task,
        local_merge=not args.no_merge,
        dry_run=args.dry_run,
        skip_review=getattr(args, "no_review", False),
    )
    print(f"=== Worker Result ({target_task.canonical_id}) ===")
    print(f"Status: {'✅ SUCCESS' if res.success else '❌ FAILED'}")
    print(f"Message: {res.message}")
    return 0 if res.success else 1


def handle_cycle_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops cycle' autonomous SDLC iteration."""
    print(f"🔄 Starting autonomous SpecOps development lifecycle ({config.project.name})...")
    # Step 1: PRD Audit & Decompose
    mgr = PRDManager(config)
    audit_res = mgr.audit()
    if audit_res.undecomposed_prds:
        decomposer = PRDDecomposer(config)
        for prd_id in audit_res.undecomposed_prds:
            print(f"📄 Decomposing accepted PRD {prd_id}...")
            decomposer.decompose(prd_id)

    # Step 2: JIT Curate Backlog
    curator = BacklogCurator(config)
    cur_res = curator.curate()
    print(f"📋 Backlog Curation: {cur_res.message}")

    # Step 3: Health Check
    checker = HealthChecker(config)
    h_report = checker.run_check()
    if not h_report.is_healthy:
        print("❌ Invariant health check failed. Stopping cycle.")
        for v in h_report.violations:
            print(f"   Violation: {v.path} ({v.lines} lines > {v.limit})")
        for err in h_report.sync_errors:
            print(f"   Sync Error: {err}")
        return 1
    print("✅ Health invariants verified: 0 file violations, PRIORITY.md synchronized.")

    # Step 4: Worker Execution
    max_concurrency = getattr(args, "max_concurrency", 3)
    drain = getattr(args, "drain", False)
    max_tasks = getattr(args, "max_tasks", None)
    if not drain and max_tasks is None:
        max_tasks = 1

    orchestrator = BatchCycleOrchestrator(
        config,
        max_concurrency=max_concurrency,
        max_tasks=max_tasks,
        drain=drain,
        dry_run=args.dry_run,
        no_merge=args.no_merge,
        skip_review=getattr(args, "no_review", False),
        adaptive=getattr(args, "adaptive", False),
    )
    report = orchestrator.run()
    if report.tasks_failed:
        print(f"❌ Cycle finished with {len(report.tasks_failed)} failure(s).")
        return 1

    # Step 5: Visualizer & Docs build
    if getattr(args, "build_docs", False):
        print("📚 Compiling documentation and living 2D visualizer...")
        from ..docs.builder import build_docs_site
        build_docs_site(config)

    print("\n🎉 Autonomous cycle completed cleanly.")
    return 0


def handle_rescue_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops rescue' worktree diagnostics and recovery."""
    from ..rescue.manager import WorktreeRescueManager

    mgr = WorktreeRescueManager(config)

    if getattr(args, "prune", False):
        count = mgr.prune_all_worktrees()
        print(f"🧹 Pruned and cleaned up {count} worktree(s).")
        return 0

    if args.list or not args.task_id:
        wts = mgr.list_active_worktrees()
        print("=== Active / Stalled Worktrees (.worktrees/) ===")
        if not wts:
            print("No active or stalled worktrees found.")
            return 0
        for w in wts:
            dirty = " [DIRTY]" if w.is_dirty else ""
            print(f"• {w.task_id} ({w.branch}){dirty} at {w.worktree_dir}")
            if w.failure_feedback:
                print(f"  Diagnostics: {w.failure_feedback[:100]}...")
        return 0

    if args.complete:
        ok, msg = mgr.complete_rescue(args.task_id)
        print(f"=== Worktree Rescue: {args.task_id} ===")
        print(f"Status: {'✅ SUCCESS' if ok else '❌ FAILED'}")
        print(msg)
        return 0 if ok else 1

    if args.discard:
        ok, msg = mgr.discard_worktree(args.task_id)
        print(msg)
        return 0 if ok else 1

    info = mgr.inspect_task(args.task_id)
    if not info:
        print(f"❌ No worktree found for {args.task_id}.")
        return 1

    print(f"=== Stalled Worktree: {info.task_id} ===")
    print(f"Directory: {info.worktree_dir}")
    print(f"Branch:    {info.branch}")
    print(f"Dirty:     {info.is_dirty}")
    if info.failure_feedback:
        print(f"\nLast Diagnostics:\n{info.failure_feedback}\n")
    print("👉 To finish and integrate: run 'spec-ops rescue <task-id> --complete'")
    print("👉 To discard: run 'spec-ops rescue <task-id> --discard'")
    return 0
