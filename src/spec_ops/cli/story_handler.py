"""CLI command handlers for BDD user story generation and traceability."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.story_engine import StoryEngine


def _extract_scenarios(raw_scenarios: list[str] | None) -> list[str] | None:
    if not raw_scenarios:
        return None
    scenarios: list[str] = []
    for item in raw_scenarios:
        for part in str(item).split(","):
            s = part.strip()
            if s and s not in scenarios:
                scenarios.append(s)
    return scenarios or None


def handle_story_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser | None = None,
) -> int:
    """Dispatches spec-ops story subcommands (create and trace)."""
    action = getattr(args, "story_action", None)
    if not action:
        if parser:
            try:
                parser.parse_args(["story", "--help"])
            except SystemExit:
                pass
        return 0

    engine = StoryEngine(config.root_dir, config=config)

    if action == "create":
        title = getattr(args, "title", None) or "New User Story"
        prd = getattr(args, "prd", None) or "PRD-0001"
        persona = getattr(args, "persona", None) or "Alex (The Agentic Systems Architect)"
        bc = getattr(args, "bc", "core") or "core"
        story_id = getattr(args, "id", None)
        feature = getattr(args, "feature", None)
        scenarios = _extract_scenarios(getattr(args, "scenarios", None))
        dry_run = getattr(args, "dry_run", False)

        res = engine.create_story(
            title=title,
            prd=prd,
            persona=persona,
            bc=bc,
            story_id=story_id,
            feature=feature,
            scenarios=scenarios,
            dry_run=dry_run,
        )

        if dry_run:
            print(f"[DRY RUN] Would scaffold BDD user story {res.id}: {res.file_path}")
            print("\nProposed User Story Content:")
            print(res.content)
            return 0

        print(f"✨ Scaffolded BDD user story {res.id}: {res.file_path}")
        print("✅ Atomically synchronized docs/project/user_stories/REGISTRY.md")
        return 0

    if action == "trace":
        story_filter = getattr(args, "story", None)
        prd_filter = getattr(args, "prd", None)
        json_output = getattr(args, "json", False)

        report = engine.trace(story_filter=story_filter, prd_filter=prd_filter)

        if json_output:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.format_text())

        return 0 if report.is_clean else 1

    return 0
