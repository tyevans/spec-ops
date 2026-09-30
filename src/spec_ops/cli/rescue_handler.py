"""Handler for spec-ops rescue command."""

from __future__ import annotations

import argparse
from ..config.models import SpecOpsConfig


def handle_rescue_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Executes the rescue subcommand actions."""
    is_prune = (getattr(args, "task_id", None) == "prune") or getattr(args, "prune", False)
    if is_prune:
        from ..rescue.prune import format_bytes, prune_worktrees

        dry_run = getattr(args, "dry_run", False)
        candidates, warnings = prune_worktrees(config.root_dir, config.backlog_dir, dry_run=dry_run)

        for w in warnings:
            print(w)

        if dry_run:
            print("Candidate Worktrees for Pruning:")
            print(f"{'Worktree':<26} {'Branch':<20} {'Estimated Space':<18} {'Status'}")
            print("-" * 75)
            total_size = sum(c.size_bytes for c in candidates)
            for c in candidates:
                rel_wt = f".worktrees/{c.worktree_dir.name}"
                status_str = c.task_status or "Orphan"
                size_str = format_bytes(c.size_bytes)
                print(f"{rel_wt:<26} {c.branch:<20} {size_str:<18} {status_str}")
            print("-" * 75)
            print(f"Total estimated reclaimable space: {format_bytes(total_size)}")
            print("(Dry run mode: no filesystem modifications made)")
            return 0

        print(f"🧹 Pruned and cleaned up {len(candidates)} worktree(s).")
        return 0

    from ..backlog.rescue import WorktreeRescueManager

    mgr = WorktreeRescueManager(config)

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
