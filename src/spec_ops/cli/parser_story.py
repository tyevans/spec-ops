"""BDD user story generation and traceability CLI parser."""

from __future__ import annotations

import argparse


def register_story_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers spec-ops story CLI subparsers."""
    p_story = subparsers.add_parser(
        "story",
        help="Multi-faceted BDD user story generation and cross-cutting traceability engine",
    )
    story_subs = p_story.add_subparsers(dest="story_action", help="Story action")

    # create
    p_create = story_subs.add_parser(
        "create",
        help="Scaffold a new BDD user story specification with Gherkin acceptance criteria",
    )
    p_create.add_argument("--title", help="Story title")
    p_create.add_argument("--prd", help="Governing PRD canonical ID (e.g. PRD-0006)")
    p_create.add_argument("--persona", help="Target user persona (e.g. Jordan)")
    p_create.add_argument("--bc", "--target-bc", dest="bc", default="core", help="Target bounded context (default: core)")
    p_create.add_argument("--id", help="Story canonical ID (e.g. US-0118, auto-allocated if omitted)")
    p_create.add_argument("--feature", help="Feature identifier (e.g. FEAT-ORCH-01)")
    p_create.add_argument("--scenarios", action="append", help="Scenario titles to include (repeatable or comma-separated)")
    p_create.add_argument("--dry-run", action="store_true", help="Simulate creation without writing to disk or updating REGISTRY.md")

    # trace
    p_trace = story_subs.add_parser(
        "trace",
        help="Audit end-to-end bidirectional traceability across Personas, PRDs, Stories, Tasks, and Commits",
    )
    p_trace.add_argument("--story", help="Target user story ID to trace (e.g. US-0117)")
    p_trace.add_argument("--prd", help="Target PRD ID to filter trace (e.g. PRD-0006)")
    p_trace.add_argument("--json", action="store_true", help="Output story traceability report as structured JSON")
