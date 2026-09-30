"""Handler for spec-ops rescue command."""

from __future__ import annotations

import argparse
from ..config.models import SpecOpsConfig


def handle_rescue_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Executes the rescue subcommand actions."""
    from ..backlog.rescue import WorktreeRescueManager

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
