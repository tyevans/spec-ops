"""Task subparser registration for ergonomic task authoring, INVEST decomposition, and DoR synthesis."""

from __future__ import annotations

import argparse


def register_task_subparsers(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Registers 'spec-ops task' subcommands."""
    p_task = subparsers.add_parser(
        "task",
        help="Ergonomic PMaC task authoring, INVEST decomposition, and Definition of Ready scaffolding",
    )
    task_subs = p_task.add_subparsers(dest="task_action", help="Task action")

    # task create
    p_task_create = task_subs.add_parser(
        "create",
        help="Scaffold a new PMaC task with Definition of Ready scaffolding",
    )
    p_task_create.add_argument("--title", help="Task title")
    p_task_create.add_argument("--bc", dest="target_bc", help="Target bounded context")
    p_task_create.add_argument("--prd", action="append", help="Governing PRD (repeatable or comma-separated)")
    p_task_create.add_argument("--story", action="append", help="Governing BDD user story (repeatable or comma-separated)")
    p_task_create.add_argument("--adr", action="append", help="Governing ADR (repeatable or comma-separated)")
    p_task_create.add_argument(
        "--deps",
        "--dependencies",
        dest="dependencies",
        action="append",
        help="Task dependencies (repeatable or comma-separated)",
    )
    p_task_create.add_argument(
        "--stage",
        choices=["proposed", "refined"],
        default="proposed",
        help="Task backlog stage (default: proposed)",
    )
    p_task_create.add_argument("--non-interactive", action="store_true", help="Do not prompt interactively")

    # task decompose
    p_task_decomp = task_subs.add_parser(
        "decompose",
        help="Decompose PRD into INVEST-compliant vertical tasks and architectural spikes",
    )
    p_task_decomp.add_argument("prd_id", nargs="?", default=None, help="Governing PRD ID (e.g. PRD-0006 or 0006)")
    p_task_decomp.add_argument("--prd", dest="opt_prd", default=None, help="Governing PRD ID (e.g. PRD-0006 or 0006)")
    p_task_decomp.add_argument(
        "--output-dir",
        default=None,
        help="Target output directory for task files (default: docs/project/backlog/proposed)",
    )
    p_task_decomp.add_argument("--dry-run", action="store_true", help="Preview generated tasks without writing to disk")

    # task synthesize-dor
    p_task_synth = task_subs.add_parser(
        "synthesize-dor",
        help="Evaluate task Definition of Ready completeness and synthesize missing contracts",
    )
    p_task_synth.add_argument("task_id", nargs="?", default=None, help="Target task canonical ID (e.g. TASK-0025 or 0025)")
    p_task_synth.add_argument("--task", dest="opt_task", default=None, help="Target task canonical ID (e.g. TASK-0025 or 0025)")
    p_task_synth.add_argument("--dry-run", action="store_true", help="Preview synthesized DoR contracts without writing to disk")

    return p_task
