"""Worker command handlers for SpecOps CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..worker.consultation import WorkerOrchestrator


def handle_worker_orchestrate(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops worker orchestrate' execution."""
    task_id = (
        getattr(args, "task_id", None)
        or getattr(args, "task_pos", None)
        or getattr(args, "task", None)
    )
    max_attempts = getattr(args, "max_attempts", 3) or 3
    peer_review = getattr(args, "peer_review", True)
    dry_run = getattr(args, "dry_run", False)
    as_json = getattr(args, "json", False)

    orchestrator = WorkerOrchestrator(
        config=config,
        max_attempts=max_attempts,
        peer_review=peer_review,
        dry_run=dry_run,
    )

    report = orchestrator.orchestrate(task_id=task_id)

    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.success else 1

    status_str = "✅ SUCCESS" if report.success else "❌ FAILED"
    print(f"=== Multi-Agent Worker Orchestrator ({report.task_id}) ===")
    print(f"Status: {status_str}")
    print(f"Attempts: {report.attempts}/{report.max_attempts}")
    print(f"Preflight: {'Passed' if report.preflight_passed else 'Failed'}")
    print(f"Peer Consultation: {'Approved' if report.peer_review_passed else 'Review Pending/Failed'}")

    if report.specs_consulted:
        sc = report.specs_consulted
        print(f"Specs Consulted: {len(sc.adrs)} ADR(s), {len(sc.prds)} PRD(s), {len(sc.stories)} Story/Stories")

    if report.trailers:
        print("Git Trailers:")
        for k, v in report.trailers.items():
            print(f"  {k}: {v}")

    print(f"Message: {report.message}")

    if not report.success and report.attempt_history:
        last_att = report.attempt_history[-1]
        if last_att.feedback:
            print("\nActionable Diagnostics & Feedback:")
            print(last_att.feedback[:1000])

    return 0 if report.success else 1


def handle_worker_rebase(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops worker rebase' execution."""
    task_id = (
        getattr(args, "task_id", None)
        or getattr(args, "task_pos", None)
        or getattr(args, "task", None)
    )
    if not task_id and getattr(args, "action_or_task", None) == "rebase":
        task_id = getattr(args, "task_pos", None)

    abort_on_conflict = getattr(args, "abort_on_conflict", True)
    dry_run = getattr(args, "dry_run", False)
    as_json = getattr(args, "json", False)

    from ..worker.auto_rebase import auto_rebase_worktree

    result = auto_rebase_worktree(
        task_id=task_id,
        abort_on_conflict=abort_on_conflict,
        dry_run=dry_run,
        config=config,
    )

    if as_json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.success else 1

    status_str = "✅ CLEAN" if result.success else ("ℹ️ DRY RUN" if result.status == "dry_run" else "❌ CONFLICT ABORTED")
    print(f"=== Autonomous Worktree Auto-Rebase ({result.task_id or 'Current'}) ===")
    print(f"Status: {status_str}")
    print(f"Message: {result.message}")
    if result.conflicted_files:
        print(f"Conflicted Files ({len(result.conflicted_files)}):")
        for f in result.conflicted_files:
            print(f"  - {f}")
    if result.handover_path:
        print(f"Handover Brief: {result.handover_path}")

    return 0 if result.success else 1


def handle_worker_diagnose(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops worker diagnose' execution."""
    from ..worker.diagnostic_injector import DiagnosticInjector

    log_file = getattr(args, "log_file", None)
    trace_text = getattr(args, "trace_text", None)
    as_json = getattr(args, "json", False)

    content = ""
    if trace_text:
        content = trace_text
    elif log_file:
        p = Path(log_file)
        if not p.exists():
            print(f"Error: Log file not found: {log_file}", file=sys.stderr)
            return 1
        content = p.read_text(encoding="utf-8", errors="ignore")
    else:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            preflight_log = Path(".preflight.log")
            if preflight_log.exists():
                content = preflight_log.read_text(encoding="utf-8", errors="ignore")

    cards = DiagnosticInjector.diagnose_failure(content, repo_root=Path.cwd())

    if as_json:
        print(json.dumps([c.to_dict() for c in cards], indent=2))
        return 0

    if not cards:
        print("✅ No diagnostic failure patterns identified in provided input.")
        return 0

    prompt = DiagnosticInjector.synthesize_retry_prompt(cards)
    print(prompt)
    return 0


def handle_worker_lease(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops worker lease' execution."""
    from ..worker.lease_manager import WorkerLeaseManager

    as_json = getattr(args, "json", False)
    dry_run = getattr(args, "dry_run", False)
    ttl = getattr(args, "ttl", 300) or 300
    mgr = WorkerLeaseManager(config.root_dir, default_ttl_seconds=ttl)

    if getattr(args, "heartbeat", False):
        task_id = getattr(args, "task_id", None)
        if not task_id:
            print("❌ Error: --task must be specified to record a lease heartbeat.", file=sys.stderr)
            return 1
        lease = mgr.record_heartbeat(task_id)
        if not lease:
            print(f"❌ Error: No active worker lease found for {task_id}.", file=sys.stderr)
            return 1
        if as_json:
            print(json.dumps(lease.to_dict(), indent=2))
        else:
            print(f"💓 Heartbeat recorded for {lease.task_id} (PID {lease.pid}). Expires at {lease.expires_at}.")
        return 0

    if getattr(args, "reclaim", False):
        reclaimed, active = mgr.reclaim_zombies(dry_run=dry_run)
        if as_json:
            print(json.dumps({"reclaimed": reclaimed, "active": active, "dry_run": dry_run}, indent=2))
            return 0

        mode_str = " [SIMULATED]" if dry_run else ""
        print(f"=== Worker Lease Reconciliation & Zombie Claim Reclaimer{mode_str} ===")
        print(f"Active Leases:    {len(active)}")
        print(f"Reclaimed Claims: {len(reclaimed)}")
        for rec in reclaimed:
            print(f"  🔄 Revoked zombie claim {rec['task_id']} ({rec['reason']}) -> Restored to Refined")
        for act in active:
            print(f"  ⚡ Active lease {act['task_id']} held by worker {act['worker_id']} (PID {act['pid']})")
        return 0

    # Default: --status / inspect leases
    leases = mgr.list_leases()
    if as_json:
        print(json.dumps([l.to_dict() for l in leases], indent=2))
        return 0

    print("=== SpecOps Worker Lease Status ===")
    if not leases:
        print("No active worker leases registered on disk.")
        return 0

    for lease in leases:
        valid, reason = mgr.evaluate_lease(lease)
        icon = "⚡ [ACTIVE]" if valid else "⚠️  [ZOMBIE]"
        print(f"{icon} {lease.task_id}: Worker={lease.worker_id}, PID={lease.pid}, Reason={reason}")
        print(f"    Expires: {lease.expires_at} | Last Heartbeat: {lease.last_heartbeat}")
    return 0


def handle_worker_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Dispatches worker command to orchestrator, rebase, diagnose, lease, or legacy cycle_handler."""
    worker_action = getattr(args, "worker_action", None)
    action_or_task = getattr(args, "action_or_task", None)

    if worker_action == "orchestrate" or (isinstance(action_or_task, str) and action_or_task.lower() == "orchestrate"):
        return handle_worker_orchestrate(args, config)

    if worker_action == "rebase" or (isinstance(action_or_task, str) and action_or_task.lower() == "rebase"):
        return handle_worker_rebase(args, config)

    if worker_action == "diagnose" or (isinstance(action_or_task, str) and action_or_task.lower() == "diagnose"):
        return handle_worker_diagnose(args, config)

    if worker_action == "lease" or (isinstance(action_or_task, str) and action_or_task.lower() == "lease"):
        return handle_worker_lease(args, config)

    from .cycle_handler import handle_worker_command as handle_legacy_worker

    return handle_legacy_worker(args, config)


