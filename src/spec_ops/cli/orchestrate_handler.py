"""CLI command handlers for spec-ops orchestrate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..worker.retrospective import get_orchestration_health, run_retrospective


def handle_orchestrate_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Dispatches spec-ops orchestrate subcommands."""
    action = getattr(args, "orchestrate_action", None)
    if not action:
        parser.parse_args(["orchestrate", "--help"])
        return 0

    log_dir_arg = getattr(args, "log_dir", None)
    log_dir = Path(log_dir_arg).resolve() if log_dir_arg else None

    if action == "retrospect":
        dry_run = bool(getattr(args, "dry_run", False))
        is_json = bool(getattr(args, "json", False))

        result = run_retrospective(
            backlog_dir=config.backlog_dir,
            log_dir=log_dir,
            repo_root=config.root_dir,
            dry_run=dry_run,
        )

        if is_json:
            print(json.dumps(result, indent=2))
            return 0

        print("=== Orchestration Retrospective Report ===")
        failures = result.get("failures_detected", [])
        if not failures:
            print("✨ No recurring invariant breaches detected in scanned failure logs.")
            return 0

        print(f"Detected {len(failures)} failure pattern(s) across scanned worktrees/artifacts:\n")
        for f in failures:
            print(f"  • [{f['invariant_id']}] {f['category']}")
            if f.get("source_file"):
                print(f"    Source: {f['source_file']}")
            print(f"    Mandate: {f['mandate']}")

        tasks = result.get("details", [])
        if tasks:
            header = "Simulated remediation task(s) (--dry-run):" if dry_run else "Scaffolded proposed remediation task(s):"
            print(f"\n{header}")
            for t in tasks:
                loc = f" -> {t['file']}" if t.get("file") else ""
                print(f"  ✓ {t['task_id']}: Remediate {t['invariant_id']} violation ({t['category']}){loc}")
        return 0

    if action == "health":
        is_json = bool(getattr(args, "json", False))
        summary = get_orchestration_health(
            repo_root=config.root_dir,
            log_dir=log_dir,
        )

        if is_json:
            print(json.dumps(summary.to_dict(), indent=2))
            return 0

        print("=== Orchestration Health Summary ===")
        print("Fleet Status:")
        print(f"  Total Worktree Attempts: {summary.total_attempts}")
        print(f"  Passed: {summary.passed_attempts} | Failed: {summary.failed_attempts} (Pass Rate: {summary.pass_rate}%)")
        print(f"  Active Worktrees: {len(summary.active_worktrees)}")
        print(f"  Stalled Worktrees: {len(summary.stalled_worktrees)}")

        if summary.stalled_worktrees:
            print("\nStalled Worktree Details:")
            for sw in summary.stalled_worktrees:
                reason = f" - {sw['reason']}" if sw.get("reason") else ""
                print(f"  ⚠️  {sw['name']}: {sw.get('status', 'Stalled')}{reason}")

        print(f"\nUnaddressed Orchestration Bugs ({len(summary.unaddressed_bugs)}):")
        if summary.unaddressed_bugs:
            for b in summary.unaddressed_bugs:
                print(f"  📌 {b['task_id']}: {b['title']} [{b.get('invariant_id', 'ADR-0020')}] ({b.get('status', 'Proposed')})")
        else:
            print("  ✨ All orchestration bugs and invariant failures are addressed.")

        health_badge = "✅ HEALTHY" if summary.is_healthy else "⚠️ ATTENTION REQUIRED"
        print(f"\nOverall Health: {health_badge}")
        return 0

    return 0
