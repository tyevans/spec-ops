"""CLI argument parser for spec-ops monitor command."""

from __future__ import annotations

import argparse


def register_monitor_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers 'spec-ops monitor' subcommands."""
    p_mon = subparsers.add_parser(
        "monitor",
        help="Interactive terminal dashboard multi-tab live monitor and status streamer",
    )
    mon_subs = p_mon.add_subparsers(dest="monitor_action", help="Monitor action")
    p_live = mon_subs.add_parser(
        "live",
        help="Multi-tab interactive terminal dashboard streaming real-time events and worker status",
    )
    p_live.add_argument(
        "--headless",
        action="store_true",
        help="Print single-shot terminal summary table and exit",
    )
    p_live.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Refresh polling interval in seconds (default: 1.0)",
    )
    p_live.add_argument(
        "--tab",
        choices=["workers", "events", "health"],
        default="workers",
        help="Initial tab to display (default: workers)",
    )
    p_live.add_argument(
        "--json",
        action="store_true",
        help="Output monitor state snapshot as JSON",
    )
