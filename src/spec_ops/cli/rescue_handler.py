"""Handler for spec-ops rescue command."""

from __future__ import annotations

import argparse
import subprocess
from ..config.models import SpecOpsConfig


def handle_rescue_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Executes the rescue subcommand actions."""
    action = getattr(args, "rescue_action", None) or getattr(args, "task_id", None)

    if action == "quota":
        import json as json_lib
        from ..rescue.prune_daemon import audit_worktree_quotas, format_quota_table, parse_threshold_bytes, format_bytes

        threshold_val = parse_threshold_bytes(getattr(args, "threshold", None))
        report = audit_worktree_quotas(config.root_dir, config.backlog_dir, threshold_bytes=threshold_val)

        if getattr(args, "json", False):
            payload = {
                "worktrees": [
                    {
                        "worktree": f".worktrees/{w.worktree_name}",
                        "name": w.worktree_name,
                        "task_id": w.task_id,
                        "task_status": w.task_status,
                        "size_bytes": w.size_bytes,
                        "size_human": format_bytes(w.size_bytes),
                        "last_modified": w.last_modified.isoformat(),
                        "is_dirty": w.is_dirty,
                        "is_merged": w.is_merged,
                        "eligible_for_prune": w.is_eligible,
                        "skip_reason": w.skip_reason,
                    }
                    for w in report.worktrees
                ],
                "total_size_bytes": report.total_size_bytes,
                "total_size_human": format_bytes(report.total_size_bytes),
                "threshold_bytes": report.threshold_bytes,
                "threshold_human": format_bytes(report.threshold_bytes),
                "threshold_exceeded": report.threshold_exceeded,
                "candidates_count": report.candidates_count,
                "reclaimable_bytes": report.reclaimable_bytes,
                "reclaimable_human": format_bytes(report.reclaimable_bytes),
                "warning": report.warning_message or None,
            }
            print(json_lib.dumps(payload, indent=2))
            return 0

        print(format_quota_table(report))
        return 0

    is_prune = (action == "prune") or getattr(args, "prune", False)
    if is_prune:
        import json as json_lib
        from ..rescue.prune_daemon import run_prune, format_bytes

        older_than = getattr(args, "older_than", None)
        dry_run = getattr(args, "dry_run", False)
        force = getattr(args, "force", False)
        is_json = getattr(args, "json", False)

        try:
            pruned, skipped, warnings = run_prune(
                config.root_dir, config.backlog_dir, older_than=older_than, force=force, dry_run=dry_run
            )
        except ValueError as err:
            print(f"❌ {err}")
            return 1

        for w in warnings:
            print(w)

        if is_json:
            total_reclaimed = sum(p.size_bytes for p in pruned)
            payload = {
                "dry_run": dry_run,
                "pruned": [
                    {
                        "worktree": f".worktrees/{p.worktree_name}",
                        "name": p.worktree_name,
                        "task_id": p.task_id,
                        "branch": p.branch,
                        "size_bytes": p.size_bytes,
                        "size_human": format_bytes(p.size_bytes),
                        "task_status": p.task_status,
                    }
                    for p in pruned
                ],
                "skipped": [
                    {
                        "worktree": f".worktrees/{s.worktree_name}",
                        "name": s.worktree_name,
                        "task_id": s.task_id,
                        "task_status": s.task_status,
                        "skip_reason": s.skip_reason,
                    }
                    for s in skipped
                ],
                "reclaimed_bytes": total_reclaimed,
                "reclaimed_human": format_bytes(total_reclaimed),
                "warnings": warnings,
            }
            print(json_lib.dumps(payload, indent=2))
            return 0

        if dry_run:
            print("Candidate Worktrees for Pruning:")
            print(f"{'Worktree':<26} {'Branch':<20} {'Estimated Space':<18} {'Status'}")
            print("-" * 75)
            total_size = sum(c.size_bytes for c in pruned)
            for c in pruned:
                rel_wt = f".worktrees/{c.worktree_name}"
                status_str = c.task_status or "Orphan"
                size_str = format_bytes(c.size_bytes)
                print(f"{rel_wt:<26} {c.branch:<20} {size_str:<18} {status_str}")
            print("-" * 75)
            print(f"Total estimated reclaimable space: {format_bytes(total_size)}")
            print("(Dry run mode: no filesystem modifications made)")
            return 0

        reclaimed = sum(p.size_bytes for p in pruned)
        print(f"🧹 Pruned and cleaned up {len(pruned)} worktree(s). Reclaimed {format_bytes(reclaimed)}.")
        return 0

    if action == "cluster" or getattr(args, "rescue_action", None) == "cluster":
        from ..rescue.failure_clustering import handle_cluster_cli

        return handle_cluster_cli(config, args)

    from ..backlog.rescue import WorktreeRescueManager

    mgr = WorktreeRescueManager(config)

    raw_task_id = getattr(args, "task_id", None)
    target = getattr(args, "target", None)

    action: str | None = None
    task_id: str | None = None

    known_actions = {"triage", "takeover", "inspect", "shell", "test", "reset", "salvage", "patch", "finish", "complete", "cluster"}
    if raw_task_id in known_actions:
        action = raw_task_id
        task_id = target
    elif target in known_actions:
        action = target
        task_id = raw_task_id
    elif getattr(args, "step", None) or getattr(args, "only_failed", False):
        action = "test"
        task_id = raw_task_id
    else:
        task_id = raw_task_id
        if task_id and not args.complete and not args.discard and not getattr(args, "reset", False) and not args.list and not getattr(args, "salvage", False):
            action = "inspect"

    if action == "test":
        from ..rescue.incremental_runner import run_incremental_rescue_test

        return run_incremental_rescue_test(
            config=config,
            task_id=task_id,
            step=getattr(args, "step", None),
            only_failed=getattr(args, "only_failed", False),
        )

    if getattr(args, "rescue_action", None) == "salvage" or action == "salvage":
        from ..rescue.salvage import salvage_task

        files = getattr(args, "files", []) or []
        target_tid = task_id or getattr(args, "task_id", None)
        if not target_tid:
            print("❌ Task ID is required for rescue salvage.")
            return 1
        ok, msg = salvage_task(config, target_tid, files)
        print(msg)
        return 0 if ok else 1

    if getattr(args, "rescue_action", None) == "patch" or action == "patch":
        from ..rescue.salvage import patch_task

        include_files = getattr(args, "include", []) or []
        target_tid = task_id or getattr(args, "task_id", None)
        if not target_tid:
            print("❌ Task ID is required for rescue patch.")
            return 1
        ok, msg = patch_task(config, target_tid, include_files)
        print(msg)
        return 0 if ok else 1

    if args.list or not task_id:

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

    is_salvage = getattr(args, "salvage", False)
    if args.complete or action in ("complete", "finish") or is_salvage:
        if is_salvage:
            from ..rescue.salvage import complete_salvage

            ok, msg = complete_salvage(config, task_id)
            print(f"=== Worktree Rescue (Salvage): {task_id} ===")
            print(f"Status: {'✅ SUCCESS' if ok else '❌ FAILED'}")
            print(msg)
            return 0 if ok else 1
        else:
            ok, msg = mgr.complete_rescue(task_id)
            print(f"=== Worktree Rescue: {task_id} ===")
            print(f"Status: {'✅ SUCCESS' if ok else '❌ FAILED'}")
            print(msg)
            return 0 if ok else 1

    if args.discard:
        ok, msg = mgr.discard_worktree(task_id)
        print(msg)
        return 0 if ok else 1

    if getattr(args, "reset", False) or action == "reset" or getattr(args, "rescue_action", None) == "reset":
        from ..rescue.memory import reset_worktree_with_memory

        reason = getattr(args, "reason", "") or ""
        demote = getattr(args, "demote", False)
        worker_id = getattr(args, "worker_id", "") or ""
        target_tid = task_id or getattr(args, "task_id", None)
        if not target_tid:
            print("❌ Task ID is required for rescue reset.")
            return 1
        ok, msg = reset_worktree_with_memory(
            config.root_dir,
            config.backlog_dir,
            target_tid,
            reason=reason,
            demote=demote,
            worker_id=worker_id,
        )
        print(msg)
        return 0 if ok else 1

    if action == "takeover":
        from ..rescue.triage import takeover_task

        ok, msg = takeover_task(config, task_id)
        print(msg)
        return 0 if ok else 1

    if action == "shell":
        info = mgr.inspect_task(task_id)
        if not info or not info.worktree_dir.exists():
            print(f"❌ No worktree found for {task_id}.")
            return 1
        print(f"Entering shell for {info.task_id} at {info.worktree_dir}")
        print(f"Run 'spec-ops rescue {info.task_id} --complete' after completing your fixes.")
        return 0

    if action == "triage":
        from ..rescue.triage import (
            analyze_worktree,
            calculate_file_diff,
            format_triage_table,
            get_targeted_recommendation,
        )

        info = mgr.inspect_task(task_id)
        if not info or not info.worktree_dir.exists():
            print(f"❌ No worktree found for {task_id}.")
            return 1

        findings = analyze_worktree(info.worktree_dir, info.failure_feedback)
        print(f"=== Preserved Worktree Failure Triage: {info.task_id} ===")
        print("Categorized Diagnostic Summary:")
        print(format_triage_table(findings))
        print()
        print(get_targeted_recommendation(findings, info.task_id))
        print("Interactive triage menu with options: [d]iff, [p]atch, [s]hell, [r]eset, [c]omplete, [q]uit")

        triage_action = getattr(args, "action", None)
        target_file = getattr(args, "file", None)
        if triage_action == "diff" or target_file:
            diff_file = target_file or (findings[0].file_path if findings and findings[0].file_path else "")
            if diff_file:
                metrics = calculate_file_diff(info.worktree_dir, diff_file)
                delta_str = f"+{metrics.net_delta} lines" if metrics.net_delta >= 0 else f"{metrics.net_delta} lines"
                hr = metrics.headroom
                hr_desc = f"{hr} lines headroom, VIOLATION" if hr < 0 else (f"+{hr} lines headroom, WARNING" if hr <= 100 else f"+{hr} lines headroom, COMPLIANT")
                print(f"\n--- File Diff: {metrics.file_path} ---")
                print(f"Syntax-highlighted diff comparing the worktree file against HEAD:")
                if metrics.diff_text:
                    print(metrics.diff_text)
                print(f"Net line delta ({delta_str}) and headroom to the 500-line invariant limit ({hr_desc}).")
                print(f"AST Structural Diff:\n{metrics.ast_diff_summary}")
        return 0

    info = mgr.inspect_task(task_id)
    if not info:
        print(f"❌ No worktree found for {task_id}.")
        return 1

    last_commit_res = subprocess.run(["git", "log", "-1", "--oneline"], cwd=info.worktree_dir, capture_output=True, text=True)
    last_commit = last_commit_res.stdout.strip() or "No commits yet"

    diff_stat_res = subprocess.run(["git", "diff", "--stat", "HEAD"], cwd=info.worktree_dir, capture_output=True, text=True)
    diff_stat = diff_stat_res.stdout.strip() or "(No file diffs against HEAD)"

    print(f"=== Stalled Worktree: {info.task_id} ===")
    print(f"Directory:   {info.worktree_dir}")
    print(f"Branch:      {info.branch}")
    print(f"Dirty:       {info.is_dirty}")
    print(f"Last commit: {last_commit}")
    print(f"\nFile diffs:\n{diff_stat}")
    if info.failure_feedback:
        print(f"\nLast Diagnostics:\n{info.failure_feedback}\n")

    from ..rescue.handover import render_quickstart_cheatsheet

    cheatsheet = render_quickstart_cheatsheet(info.task_id, info.worktree_dir, failure_log=info.failure_feedback)
    print(f"\n{cheatsheet}\n")

    print(f"👉 To finish and integrate: run 'spec-ops rescue {info.task_id} --complete'")
    print(f"👉 To discard: run 'spec-ops rescue {info.task_id} --discard'")
    return 0
