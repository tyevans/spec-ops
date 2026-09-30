"""CLI command handler for spec-ops worktree."""

from __future__ import annotations

import argparse

from ..config.models import SpecOpsConfig
from ..rescue.sandbox import finish_human_worktree, start_human_worktree


def handle_worktree_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Dispatches human worktree sandboxing subcommands."""
    action = getattr(args, "worktree_action", None)
    if action == "start":
        ok, msg, _wt_dir = start_human_worktree(config, args.task_id)
        print(msg)
        return 0 if ok else 1

    if action == "finish":
        ok, msg = finish_human_worktree(config, getattr(args, "task_id", None))
        print(msg)
        return 0 if ok else 1

    print("Usage: spec-ops worktree {start|finish} ...")
    return 1
