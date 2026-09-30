"""CLI command handlers for security and queue operations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..backlog.queue import BacklogQueue
from ..config.models import SpecOpsConfig
from ..security.lockfile import verify_lockfile


def handle_security_command(args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser) -> int:
    """Executes security subcommands including verify-lock."""
    if args.security_action == "verify-lock":
        target = Path(getattr(args, "path", ".")).resolve()
        ok, errors = verify_lockfile(target, run_uv=True)
        if not ok:
            print("❌ Supply-Chain Lockfile Verification Failed:", file=sys.stderr)
            for err in errors:
                print(f"   - {err}", file=sys.stderr)
            return 1
        print("✅ Lockfile verified: cryptographic hashes and package pins valid.")
        return 0

    parser.parse_args(["security", "--help"])
    return 0


def handle_queue_command(args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser) -> int:
    """Executes queue subcommands including gated task completion."""
    if args.queue_action == "complete":
        queue = BacklogQueue(config.backlog_dir)
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
        ok, msg = queue.complete_task_with_gate(target_task, base_branch=base, repo_root=config.root_dir)
        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            return 1
        print(f"✅ {msg}")
        return 0

    parser.parse_args(["queue", "--help"])
    return 0
