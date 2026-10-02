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

    if action == "coverage":
        import json
        from ..prd.bdd_matrix import BDDCoverageAuditor

        stories_dir = config.root_dir / "docs" / "project" / "user_stories" / "accepted"
        tests_dir = config.root_dir / "tests"
        target_bc = getattr(args, "target_bc", None)
        strict = getattr(args, "strict", False)
        json_flag = getattr(args, "json", False)

        auditor = BDDCoverageAuditor(config.root_dir)
        matrix = auditor.audit(stories_dir=stories_dir, tests_dir=tests_dir, target_bc=target_bc)

        if json_flag:
            print(json.dumps(matrix.to_dict(), indent=2))
        else:
            print(matrix.summary())

        if strict:
            has_missing = any(s.covered_scenarios < s.total_scenarios for s in matrix.stories)
            if has_missing or (matrix.total_scenarios > 0 and matrix.covered_scenarios < matrix.total_scenarios):
                return 1

        return 0

    if action == "journey":
        from ..prd.journey_map import handle_journey_command
        fmt = "json" if getattr(args, "json_flag", False) else getattr(args, "format", "markdown")
        return handle_journey_command(
            config,
            persona=getattr(args, "persona", None),
            fmt=fmt,
            output=getattr(args, "output", None),
        )

    if action == "friction":
        import json
        from ..prd.persona_friction import PersonaFrictionAuditor

        auditor = PersonaFrictionAuditor(config.root_dir)
        persona_filter = getattr(args, "persona", None)
        threshold = getattr(args, "threshold", None)
        json_flag = getattr(args, "json", False)

        report = auditor.audit(parser=parser, persona_filter=persona_filter, threshold=threshold)

        if json_flag:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.format_text())

        if threshold is not None and report.has_violations:
            return 1

        return 0

    if action == "uat":
        from ..prd.uat_cli import dispatch_uat_command
        return dispatch_uat_command(args, config, parser)

    if action == "studio":
        from ..prd.studio_runner import launch_prd_studio

        return launch_prd_studio(
            config,
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8787),
            open_browser=getattr(args, "open", False),
        )

    if action == "discover":
        from ..prd.discovery_workflow import discover_prd

        p = discover_prd(
            config,
            title=getattr(args, "title", None),
            persona=getattr(args, "persona", None),
            bc=getattr(args, "bc", None),
            summary=getattr(args, "summary", None),
            non_interactive=getattr(args, "non_interactive", False),
        )
        print(f"✨ Scaffolding complete: Created PRD draft under {p}")
        return 0

    if action == "shape":
        from ..prd.discovery_workflow import shape_prd

        prd_id = getattr(args, "prd_id", None) or getattr(args, "pos_id", None)
        if not prd_id:
            print("❌ Error: Missing PRD ID or path. Specify --id <PRD_ID> or provide it as an argument.")
            return 1

        ok, msg = shape_prd(
            config,
            prd_id_or_path=prd_id,
            outcomes=getattr(args, "outcomes", None),
            anti_goals=getattr(args, "anti_goals", None),
            target_stage=getattr(args, "stage", None),
            accept=getattr(args, "accept", False),
        )
        print(msg)
        return 0 if ok else 1

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

    if action == "gate":
        from ..prd.uat_gatekeeper import handle_prd_gate

        return handle_prd_gate(
            config,
            prd=args.prd,
            strict=getattr(args, "strict", False),
            json_output=getattr(args, "json", False),
            export=getattr(args, "export", False),
        )

    parser.parse_args(["prd", "--help"])
    return 0

