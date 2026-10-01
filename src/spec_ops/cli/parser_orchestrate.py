"""Orchestrate CLI argument subparser definition."""

from __future__ import annotations

import argparse


def register_orchestrate_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers orchestrate command with retrospect and health subcommands."""
    p_orch = subparsers.add_parser(
        "orchestrate",
        help="Continuous SDLC orchestration retrospective and self-healing engine",
    )
    orch_subs = p_orch.add_subparsers(dest="orchestrate_action", help="Orchestration action")

    p_retro = orch_subs.add_parser(
        "retrospect",
        help="Analyze session artifacts and failure logs to categorize invariant breaches and synthesize proposed remediation tasks",
    )
    p_retro.add_argument(
        "--log-dir",
        default=None,
        help="Directory containing failure logs and worktree artifacts",
    )
    p_retro.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate retrospective analysis without writing proposed tasks",
    )
    p_retro.add_argument(
        "--json",
        action="store_true",
        help="Output retrospective analysis as JSON",
    )

    p_health = orch_subs.add_parser(
        "health",
        help="Summarize orchestration health, pass/fail rates, stalled worktrees, and unaddressed bugs",
    )
    p_health.add_argument(
        "--log-dir",
        default=None,
        help="Directory containing failure logs and worktree artifacts",
    )
    p_health.add_argument(
        "--json",
        action="store_true",
        help="Output orchestration health summary as JSON",
    )
