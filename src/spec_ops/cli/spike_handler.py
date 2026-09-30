"""CLI command handler for governed architectural spike commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..spike.graduate import graduate_spike
from ..spike.sandbox import SpikeSandbox, start_spike


def _resolve_sandbox_from_context(root: Path, spike_id: str | None) -> SpikeSandbox | None:
    """Detects active spike sandbox from command arguments or cwd context."""
    if spike_id:
        return SpikeSandbox(root, spike_id)

    cwd = Path.cwd().resolve()
    for part in cwd.parts:
        if part.startswith("spike-"):
            num = part.replace("spike-", "")
            return SpikeSandbox(root, num, worktree_dir=cwd)

    meta_path = cwd / ".specops" / "spike.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            sid = data.get("spike_id") or data.get("num")
            if sid:
                return SpikeSandbox(root, sid, worktree_dir=cwd)
        except Exception:
            pass

    return None


def handle_spike_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Dispatches spike lifecycle subcommands."""
    action = getattr(args, "spike_action", None)
    if not action:
        print("❌ Missing spike subcommand. Available: start, check, preflight, graduate")
        return 1

    root = config.root_dir

    if action == "start":
        try:
            sandbox = start_spike(
                root,
                args.spike_id,
                hypothesis=getattr(args, "hypothesis", None),
                timebox=getattr(args, "timebox", None),
            )
            print(f"✨ Created isolated spike worktree at .worktrees/spike-{sandbox.num} on branch {sandbox.branch}")
            print(f"📁 Scaffolded benchmark test harness in spikes/spike_{sandbox.num}/")
            return 0
        except Exception as err:
            print(f"❌ Failed to start spike {args.spike_id}: {err}", file=sys.stderr)
            return 1

    if action == "check":
        sandbox = _resolve_sandbox_from_context(root, getattr(args, "spike_id", None))
        if not sandbox:
            print("❌ Spike ID not specified and could not be detected from current directory context.")
            return 1

        iso_ok, iso_msg = sandbox.check_write_isolation()
        if not iso_ok:
            print(f"❌ {iso_msg}", file=sys.stderr)
            print(iso_msg)
            return 1

        simulated_elapsed = getattr(args, "elapsed", None)
        tb_ok, tb_msg = sandbox.check_timebox(simulated_elapsed=simulated_elapsed)
        if not tb_ok:
            print(f"⚠️ {tb_msg}")
            print(tb_msg)
            return 0

        print(f"✅ Spike {sandbox.canonical_id} is healthy and within its declared timebox.")
        return 0

    if action == "preflight":
        sandbox = _resolve_sandbox_from_context(root, getattr(args, "spike_id", None))
        if not sandbox:
            print("❌ Spike ID not specified and could not be detected from current directory context.")
            return 1

        iso_ok, iso_msg = sandbox.check_write_isolation()
        if not iso_ok:
            print(iso_msg, file=sys.stderr)
            print(iso_msg)
            return 1
        return 0

    if action == "graduate":
        try:
            res = graduate_spike(
                root,
                args.spike_id,
                result=args.result,
                title=getattr(args, "title", None),
                notes=getattr(args, "notes", None),
                findings=getattr(args, "findings", None),
                status=getattr(args, "status", None),
            )
            print(res.message)
            return 0 if res.success else 1
        except Exception as err:
            print(f"❌ Failed to graduate spike {args.spike_id}: {err}", file=sys.stderr)
            return 1

    return 0
