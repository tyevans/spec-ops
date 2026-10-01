"""CLI argument parsers for milestone management and planning studio.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0025, US-0077.
Target Bounded Context: backlog. Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import argparse


def register_milestone_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers milestone lifecycle, rollover, and planning studio commands."""
    p_ms = subparsers.add_parser(
        "milestone",
        help="Milestone lifecycle, scope transitions, planning studio, and rollover",
    )
    ms_subs = p_ms.add_subparsers(dest="milestone_action", help="Milestone action")

    # spec-ops milestone rollover
    p_roll = ms_subs.add_parser(
        "rollover",
        help="Transition uncompleted tasks from one milestone to another",
    )
    p_roll.add_argument(
        "--from",
        dest="from_m",
        required=True,
        help="Source milestone to rollover unfinished tasks from",
    )
    p_roll.add_argument(
        "--to",
        dest="to_m",
        required=True,
        help="Target milestone to assign unfinished tasks to",
    )
    p_roll.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview task milestone updates without modifying disk",
    )
    p_roll.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output rollover results as structured JSON",
    )

    # spec-ops milestone plan
    p_plan = ms_subs.add_parser(
        "plan",
        help="Interactive milestone planning studio, workload balancing, and capacity simulation",
    )
    p_plan.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help="Run delivery horizon capacity simulation and bottleneck feasibility",
    )
    p_plan.add_argument(
        "-a",
        "--assign",
        action="append",
        default=[],
        metavar="TASK=MILESTONE",
        help="Assign task to milestone (repeatable, format: TASK=MILESTONE)",
    )
    p_plan.add_argument(
        "--save",
        action="store_true",
        default=False,
        help="Atomically commit milestone changes to task frontmatter and ROADMAP.md",
    )
    p_plan.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output milestone planning matrix and simulation as structured JSON",
    )
    p_plan.add_argument(
        "--non-interactive",
        action="store_true",
        default=False,
        help="Run headless without interactive terminal prompts",
    )
