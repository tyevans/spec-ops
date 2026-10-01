"""Subparser definition for spec-ops rescue commands and workflows."""

from __future__ import annotations

import argparse


class FlexibleRescueParser(argparse.ArgumentParser):
    """Subparser for spec-ops rescue that supports both subcommand and positional task syntax."""

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = []
        if namespace is None:
            namespace = argparse.Namespace()

        if any(isinstance(a, argparse._SubParsersAction) for a in self._actions):
            first_pos = None
            for a in args:
                if not a.startswith("-"):
                    first_pos = a
                    break

            if first_pos not in ("reset", "salvage", "patch", "quota", "prune", "cluster"):
                sub_action = None
                for act in list(self._actions):
                    if isinstance(act, argparse._SubParsersAction):
                        sub_action = act
                        self._actions.remove(act)
                        break

                t1 = self.add_argument("task_id", nargs="?", default=None)
                t2 = self.add_argument("target", nargs="?", default=None)
                try:
                    return super().parse_known_args(args, namespace)
                finally:
                    self._actions.remove(t1)
                    self._actions.remove(t2)
                    if sub_action:
                        self._actions.append(sub_action)

        return super().parse_known_args(args, namespace)


def register_rescue_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers rescue commands, subcommands, and options (US-0089, US-0092)."""
    p_rescue = subparsers.add_parser("rescue", help="Inspect and recover stalled or failed autonomous worktrees")
    p_rescue.__class__ = FlexibleRescueParser

    p_rescue.add_argument("--list", action="store_true", help="List all active/stalled worktrees")
    p_rescue.add_argument("--complete", action="store_true", help="Verify preflight and merge rescued worktree into main")
    p_rescue.add_argument("--discard", action="store_true", help="Discard worktree and branch")
    p_rescue.add_argument("--reset", action="store_true", help="Reset worktree and capture failure memory")
    p_rescue.add_argument("--reason", default="", help="Failure post-mortem reason description")
    p_rescue.add_argument("--demote", action="store_true", help="Demote task to proposed/ on reset")
    p_rescue.add_argument("--prune", action="store_true", help="Prune and clean up all stale/orphaned worktrees")
    p_rescue.add_argument("--dry-run", action="store_true", help="Dry-run preview of candidate worktrees and disk space")
    p_rescue.add_argument("--file", default=None, help="Target file for AST / line count diff inspection in triage")
    p_rescue.add_argument("--action", default=None, help="Direct triage action ([d]iff, [p]atch, [s]hell, [r]eset, [c]omplete, [q]uit)")
    p_rescue.add_argument("--step", default=None, help="Designated preflight step to run in isolation")
    p_rescue.add_argument("--only-failed", action="store_true", help="Re-run only previously failed preflight step")
    p_rescue.add_argument("--salvage", action="store_true", help="Curated preflight verification and merge solely on staged files")

    rescue_subs = p_rescue.add_subparsers(dest="rescue_action", help="Rescue action")

    p_reset = rescue_subs.add_parser("reset", help="Safe worktree discard with anti-loop failure memory and task reset")
    p_reset.add_argument("task_id", help="Target task canonical ID (e.g. TASK-0024)")
    p_reset.add_argument("--reason", default="", help="Failure post-mortem reason description")
    p_reset.add_argument("--demote", action="store_true", help="Demote task to proposed/ on reset")

    p_salv = rescue_subs.add_parser("salvage", help="Selectively salvage specified files from stalled worktree into clean rescue branch")
    p_salv.add_argument("task_id", help="Target task canonical ID (e.g. TASK-0018)")
    p_salv.add_argument("--files", nargs="+", default=[], help="File paths to salvage into clean rescue branch")

    p_patch = rescue_subs.add_parser("patch", help="Incrementally stage files into the rescue index")
    p_patch.add_argument("task_id", help="Target task canonical ID (e.g. TASK-0018)")
    p_patch.add_argument("--include", action="append", default=[], help="File path to include in rescue patch")

    p_quota = rescue_subs.add_parser("quota", help="Worktree disk quota monitor and storage consumption audit")
    p_quota.add_argument("--threshold", default=None, help="Warning threshold for aggregate worktree disk quota (e.g. 5GB, 1GB)")
    p_quota.add_argument("--json", action="store_true", help="Output disk quota metrics in JSON format")

    p_prune = rescue_subs.add_parser("prune", help="Safely prune merged or abandoned orphan worktrees and reclaim disk space")
    p_prune.add_argument("--older-than", default=None, help="Prune worktrees older than duration (e.g. 7d, 24h, 1d)")
    p_prune.add_argument("--dry-run", action="store_true", help="Dry-run preview of candidate worktrees and disk space")
    p_prune.add_argument("--force", action="store_true", help="Force prune worktrees with uncommitted or unmerged changes")
    p_prune.add_argument("--json", action="store_true", help="Output pruned worktree results in JSON format")

    p_cluster = rescue_subs.add_parser("cluster", help="Autonomous failure post-mortem clustering and prompt anti-loop synthesizer")
    p_cluster.add_argument("--json", action="store_true", help="Output failure clusters and negative constraints in JSON format")
    p_cluster.add_argument("--task", default=None, help="Target task canonical ID to filter failure clusters")
