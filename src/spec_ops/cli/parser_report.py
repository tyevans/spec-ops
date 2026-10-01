"""Subparser registration helpers for executive reporting commands."""

from __future__ import annotations

import argparse


def register_report_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers executive reporting, burndown velocity, and team delivery telemetry commands."""
    p_report = subparsers.add_parser(
        "report",
        aliases=["metrics"],
        help="Executive milestone reports, burndown velocity, and presentation decks",
    )
    report_subs = p_report.add_subparsers(dest="report_action", help="Reporting action")

    p_rep_bd = report_subs.add_parser("burndown", help="Milestone burndown velocity and presentation slide deck export")
    p_rep_bd.add_argument("--milestone", default="M1-MVP", help="Target milestone name or ID (default: M1-MVP)")
    p_rep_bd.add_argument("--format", choices=["deck", "html", "digest"], default="deck", help="Report export format (default: deck)")
    p_rep_bd.add_argument("-o", "--output", help="Output file path (default: dist/<milestone>-executive-briefing.html)")
    p_rep_bd.add_argument("--check-alignment", action="store_true", help="Audit completed tasks unanchored from ROADMAP.md")

    p_rep_ms = report_subs.add_parser("milestone", help="Milestone executive briefing digest and scope alignment")
    p_rep_ms.add_argument("--milestone", default="M1-MVP", help="Target milestone name or ID (default: M1-MVP)")
    p_rep_ms.add_argument("--format", choices=["digest", "deck", "html"], default="digest", help="Report format (default: digest)")
    p_rep_ms.add_argument("-o", "--output", help="Output file path")
    p_rep_ms.add_argument("--check-alignment", action="store_true", help="Audit completed tasks unanchored from ROADMAP.md")

    p_rep_vel = report_subs.add_parser("velocity", help="Hybrid delivery velocity and autonomous worker rescue analytics")
    p_rep_vel.add_argument("--window", default="14d", help="Evaluation time window (e.g. 14d, 30d; default: 14d)")
    p_rep_vel.add_argument("--rescues", action="store_true", help="Include worktree rescue frequency and failure clustering analytics")
    p_rep_vel.add_argument("--json", action="store_true", help="Output velocity metrics as structured JSON")
    p_rep_vel.add_argument("--export", default=None, help="Export format or destination (e.g. html, json)")
    p_rep_vel.add_argument("--format", choices=["table", "json", "html"], default=None, help="Report format (table, json, html)")
    p_rep_vel.add_argument("-o", "--out", "--output", dest="output", default=None, help="Output destination file path (default: dist/velocity-report.html)")
