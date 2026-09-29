"""PRD CLI command dispatching and handler."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..prd.decomposer import PRDDecomposer
from ..prd.discovery import interactive_new_prd
from ..prd.lifecycle import PRDLifecycleManager
from ..prd.linter import PRDLinter
from ..prd.manager import PRDManager


def handle_prd_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Dispatches PRD CLI subcommands."""
    action = getattr(args, "prd_action", None)
    if not action:
        parser.parse_args(["prd", "--help"])
        return 0

    if action == "new":
        p = interactive_new_prd(
            config,
            title=getattr(args, "title", None),
            persona=getattr(args, "persona", None),
            component=getattr(args, "component", None),
            friction=getattr(args, "friction", None),
            good=getattr(args, "good", None),
            anti_goals=getattr(args, "anti_goals", None),
            outcomes=getattr(args, "outcomes", None),
            non_interactive=getattr(args, "non_interactive", False),
        )
        print(f"✨ Scaffolding complete: Created PRD draft under {p}")
        return 0

    if action == "lint":
        linter = PRDLinter(config.root_dir)
        results = linter.lint_path(getattr(args, "path", None))
        report = linter.format_report(results)
        print(report)
        all_valid = all(r.is_valid for r in results) if results else True
        return 0 if all_valid else 1

    if action == "promote":
        lifecycle = PRDLifecycleManager(config)
        ok, msg = lifecycle.promote(args.prd_id, args.stage)
        print(msg)
        return 0 if ok else 1

    if action == "ship":
        lifecycle = PRDLifecycleManager(config)
        ok, msg = lifecycle.ship(args.prd_id)
        print(msg)
        return 0 if ok else 1

    if action == "create":
        mgr = PRDManager(config)
        p = mgr.create_prd(
            title=args.title,
            persona=args.persona,
            component=args.component,
            summary=args.summary,
            stage=args.stage,
        )
        print(f"✅ Created PRD at {p}")
        return 0

    if action == "audit":
        mgr = PRDManager(config)
        res = mgr.audit()
        print("=== PRD Audit ===")
        print(f"Total PRDs: {res.total_prds}")
        print(
            f"Undecomposed PRDs: {len(res.undecomposed_prds)} ({', '.join(res.undecomposed_prds) or 'None'})"
        )
        print(f"Ready Tasks Buffer: {res.ready_tasks_count} ({res.buffer_status})")
        if res.warnings:
            for w in res.warnings:
                print(f"⚠️ {w}")
        return 0

    if action == "decompose":
        decomposer = PRDDecomposer(config)
        tasks = decomposer.decompose(args.prd_id, include_spike=not args.no_spike)
        print(f"✅ Decomposed {args.prd_id} into {len(tasks)} task(s):")
        for t in tasks:
            print(f"   - {t.name}")
        return 0

    parser.parse_args(["prd", "--help"])
    return 0
