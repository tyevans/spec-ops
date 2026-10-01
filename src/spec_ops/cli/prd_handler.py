"""PRD CLI command dispatching and handler."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..prd.decomposer import PRDDecomposer
from ..prd.delta import FalsifiabilityError
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

    if action == "uat":
        from ..prd.uat_cli import dispatch_uat_command
        return dispatch_uat_command(args, config, parser)

    if action == "studio":
        open_browser = getattr(args, "open", False)
        port = getattr(args, "port", 8787)
        host = getattr(args, "host", "127.0.0.1")
        if open_browser:
            import threading
            import webbrowser

            def _open() -> None:
                import time
                time.sleep(0.5)
                webbrowser.open(f"http://{host}:{port}/studio")

            threading.Thread(target=_open, daemon=True).start()
        from ..visualizer.server import serve_visualizer
        serve_visualizer(config, host=host, port=port, default_view="studio")
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
        if getattr(args, "deep", False):
            from ..prd.audit import run_deep_audit
            return run_deep_audit(config, prd_id=getattr(args, "prd_id", None))

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
        by_outcomes = getattr(args, "by_outcomes", False)
        diff = getattr(args, "diff", False)
        include_spike = not getattr(args, "no_spike", False)

        try:
            if by_outcomes:
                tasks, stories = decomposer.decompose_by_outcomes(args.prd_id, include_spike=include_spike)
                print(f"✅ Decomposed {args.prd_id} into {len(stories)} story/stories and {len(tasks)} task(s):")
                for s in stories:
                    print(f"   - Story: {s.name}")
                for t in tasks:
                    print(f"   - Task: {t.name}")
                return 0

            if diff:
                delta_res, tasks, stories = decomposer.decompose_diff(args.prd_id, include_spike=include_spike)
                if delta_res.warnings:
                    for w in delta_res.warnings:
                        print(f"⚠️ {w}")
                    for pt in delta_res.pending_tasks_for_removed:
                        print(f"   Prompt: Please either archive {pt['id']} or re-link it to another outcome.")

                if not delta_res.added_outcomes:
                    print(f"ℹ️ No new scope deltas detected for {args.prd_id}. Backlog is up to date.")
                else:
                    print(f"✅ Decomposed {args.prd_id} delta into {len(stories)} story/stories and {len(tasks)} task(s):")
                    for s in stories:
                        print(f"   - Story: {s.name}")
                    for t in tasks:
                        print(f"   - Task: {t.name}")
                return 0

            tasks = decomposer.decompose(args.prd_id, include_spike=include_spike)
            print(f"✅ Decomposed {args.prd_id} into {len(tasks)} task(s):")
            for t in tasks:
                print(f"   - {t.name}")
            return 0
        except FalsifiabilityError as exc:
            for err in exc.errors:
                print(f"❌ Falsifiability failure: {err}")
            return 1
        except Exception as exc:
            print(f"❌ Error decomposing {args.prd_id}: {exc}")
            return 1

    parser.parse_args(["prd", "--help"])
    return 0
