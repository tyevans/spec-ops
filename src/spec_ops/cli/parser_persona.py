"""Persona discovery and living maintenance CLI parser."""

from __future__ import annotations

import argparse


def register_persona_subparsers(subparsers: argparse._SubParsersAction) -> None:
    p_persona = subparsers.add_parser(
        "persona",
        help="Autonomous persona discovery, coverage audit, and living maintenance engine",
    )
    persona_subs = p_persona.add_subparsers(dest="persona_action", help="Persona action")

    # audit
    p_audit = persona_subs.add_parser(
        "audit",
        help="Inspect accepted PRDs, stories, and git commits against PERSONAS.md, identify uncovered or emerging archetypes, and report coverage statistics",
    )
    p_audit.add_argument("--json", action="store_true", help="Output persona audit results as structured JSON")

    # sync
    p_sync = persona_subs.add_parser(
        "sync",
        help="Generate synthesized persona profile additions for emerging archetypes, preview diff, or apply updates to PERSONAS.md",
    )
    p_sync.add_argument("--diff", action="store_true", help="Show interactive diff preview of proposed persona updates")
    p_sync.add_argument("--apply", action="store_true", help="Apply synthesized persona additions directly to docs/project/user_stories/PERSONAS.md")
    p_sync.add_argument("--json", action="store_true", help="Output persona synchronization results as structured JSON")
