"""SpecOps unified command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

from ..backlog.curator import BacklogCurator
from ..backlog.health import HealthChecker
from ..config.loader import load_config
from .parser import build_parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    config = load_config()

    if args.command in ("profile", "profiles"):
        from .profile_handler import handle_profile_command
        return handle_profile_command(args, config)

    if args.command == "adr":
        from .adr_handler import handle_adr_command
        return handle_adr_command(args, config)

    if args.command == "scaffold":
        from .scaffold_handler import handle_scaffold_command
        return handle_scaffold_command(args, config, parser)

    if args.command == "constitution":
        from ..scaffold.constitution_sync import check_constitution, sync_constitution

        repo_root = Path(getattr(args, "repo", ".")) if getattr(args, "repo", ".") != "." else config.root_dir
        if args.constitution_action == "sync":
            _, msg = sync_constitution(repo_root)
            print(f"✨ {msg}")
            return 0
        elif args.constitution_action == "check":
            in_sync, diff, msg = check_constitution(repo_root)
            if not in_sync:
                if diff:
                    print(diff)
                print(msg)
                return 1
            print(msg)
            return 0

    if args.command == "adopt":
        from .adopt_handler import handle_adopt_command
        return handle_adopt_command(args)

    if args.command == "decompose":
        from .decompose_handler import handle_decompose_command
        return handle_decompose_command(args)

    if args.command == "init":
        from ..scaffold.wizard import handle_init_command
        return handle_init_command(args)

    if args.command == "docs":
        if args.docs_action == "check":
            from ..docs.checker import run_docs_check

            docs_dir = Path(args.dir).resolve() if getattr(args, "dir", None) else config.docs_dir
            return run_docs_check(docs_dir, parser=parser)
        elif args.docs_action == "audit":
            from ..docs.auditor import DocsAuditor
            docs_dir = Path(args.dir).resolve() if getattr(args, "dir", None) else config.docs_dir
            auditor = DocsAuditor(docs_dir, parser=parser)
            report = auditor.run_audit()
            auditor.print_report(report)
            return 0 if report.is_clean else 1
        elif args.docs_action == "build" or not args.docs_action:
            from ..docs.builder import build_docs_site
            out_dir = Path(args.out).resolve() if getattr(args, "out", None) else None
            base_url = getattr(args, "base_url", "/spec-ops/")
            include_viz = getattr(args, "include_visualizer", True)
            site_dir = build_docs_site(config, out_dir=out_dir, base_url=base_url, include_visualizer=include_viz)
            print(f"🎉 Compiled Diataxis documentation and living 2D visualizer to {site_dir}")
            return 0
        else:
            parser.parse_args(["docs", "--help"])
            return 0

    if args.command == "health":
        from .health_handler import handle_health_command
        return handle_health_command(args, config)

    if args.command == "stats":
        from .parse_handler import handle_stats_command
        return handle_stats_command(args, config)

    if args.command == "parse":
        from .parse_handler import handle_parse_command
        return handle_parse_command(args, config)

    if args.command == "graph":
        from .graph_handler import handle_graph_command
        return handle_graph_command(args, config)

    if args.command == "prd":
        from .prd_handler import handle_prd_command
        return handle_prd_command(args, config, parser)

    if args.command == "export":
        from .export_handler import handle_export_command
        return handle_export_command(args, config, parser)

    if args.command == "release":
        from .release_handler import handle_release_command
        return handle_release_command(args, config, parser)

    if args.command == "milestone":
        from .milestone_handler import handle_milestone_command
        return handle_milestone_command(args, config, parser)

    if args.command == "curate":
        if getattr(args, "curate_action", None) == "next":
            from ..backlog.queue import BacklogQueue
            queue = BacklogQueue(config.backlog_dir)
            ready = queue.get_ready_unblocked_tasks()
            target = ready[0] if ready else None
            if not target:
                for t in queue.list_all_tasks():
                    if t.status == "Refined":
                        target = t
                        break
            if getattr(args, "json", False):
                from .formatters import format_task_json
                print(format_task_json(target, config))
                return 0
            if not target:
                print("ℹ️ No ready, unblocked tasks in refined/ buffer. Run 'spec-ops curate' first.")
                return 0
            clean_id = target.canonical_id.lower().replace("task-", "").replace("spike-", "")
            branch = target.branch or f"{config.execution.git_branch_prefix}task-{clean_id}"
            print(f"=== Next Backlog Task ({target.canonical_id}) ===")
            print(f"Title:        {target.title}")
            print(f"Branch:       {branch}")
            return 0

        if getattr(args, "infer", False):
            from ..backlog.inference_curator import InferenceCurator

            inf_curator = InferenceCurator(config, model=getattr(args, "model", None))
            inf_res = inf_curator.curate(dry_run=getattr(args, "dry_run", False))
            if getattr(args, "dry_run", False):
                print(inf_res.diff_output)
                print(f"\n{inf_res.message}")
            else:
                print("=== Backlog Curation (Inference-Driven) ===")
                print(inf_res.message)
                if inf_res.tasks_sliced:
                    print("Decomposed oversized tasks:")
                    for tid in inf_res.tasks_sliced:
                        print(f"   ✂ {tid}")
                if inf_res.tasks_reconciled:
                    print("Reconciled architectural drift:")
                    for tid in inf_res.tasks_reconciled:
                        print(f"   ⟳ {tid}")
                if inf_res.tasks_refined:
                    print("Refined tasks:")
                    for tid in inf_res.tasks_refined:
                        print(f"   ✓ {tid}")
                if inf_res.audit_trail:
                    print("\nCuration Audit Trail:")
                    for entry in inf_res.audit_trail:
                        print(f"   • {entry}")
            return 0

        curator = BacklogCurator(config)
        is_dry = getattr(args, "dry_run", False)
        res = curator.curate(dry_run=is_dry)
        if is_dry:
            print("=== Backlog Curation (Dry Run) ===")
        else:
            print("=== Backlog Curation ===")
        print(res.message)
        if res.tasks_refined:
            header = "Candidate tasks for refinement:" if is_dry else "Refined tasks:"
            print(header)
            for tid in res.tasks_refined:
                print(f"   ✓ {tid}")
        return 0

    if args.command == "visualizer":
        from ..visualizer.cli_bridge import handle_visualizer_command

        return handle_visualizer_command(args, config)

    if args.command == "worker":
        from .cycle_handler import handle_worker_command
        return handle_worker_command(args, config)

    if args.command == "cycle":
        from .cycle_handler import handle_cycle_command
        return handle_cycle_command(args, config)

    if args.command == "rescue":
        from .rescue_handler import handle_rescue_command
        return handle_rescue_command(args, config)

    if args.command == "worktree":
        from .worktree_handler import handle_worktree_command
        return handle_worktree_command(args, config)

    if args.command == "spike":
        from .spike_handler import handle_spike_command
        return handle_spike_command(args, config)

    if args.command == "tui":
        from ..tui import TUIDashboard

        dashboard = TUIDashboard(config)
        if getattr(args, "once", False):
            dashboard.render_snapshot(view=getattr(args, "view", "overview"))
            return 0
        return dashboard.run(initial_view=getattr(args, "view", "overview"))

    if args.command == "audit":
        from .security_handler import handle_audit_command
        return handle_audit_command(args, config, parser)

    if args.command == "security":
        from .security_handler import handle_security_command
        return handle_security_command(args, config, parser)

    if args.command == "queue":
        from .queue_handler import handle_queue_command
        return handle_queue_command(args, config, parser)

    if args.command == "spike":
        from .spike_handler import handle_spike_command
        return handle_spike_command(args, config)

    if args.command == "review":
        from .review_handler import handle_review_command
        return handle_review_command(args, config, parser)

    if args.command == "report":
        from .report_handler import handle_report_command
        return handle_report_command(args, config, parser)

    if args.command == "trace":
        from .graph_handler import handle_trace_command
        return handle_trace_command(args, config)

    if args.command == "bridge":
        from .bridge_handler import handle_bridge_command
        return handle_bridge_command(args, config, parser)

    if args.command == "backlog":
        if getattr(args, "backlog_action", None) in ("import", "export"):
            from .bridge_handler import handle_bridge_command
            return handle_bridge_command(args, config, parser)

        if getattr(args, "backlog_action", None) == "doctor":
            from .queue_handler import handle_queue_command
            setattr(args, "queue_action", "doctor")
            return handle_queue_command(args, config, parser)

        if getattr(args, "backlog_action", None) == "reorder":
            from .queue_handler import handle_queue_command
            setattr(args, "queue_action", "reorder")
            return handle_queue_command(args, config, parser)

        if getattr(args, "backlog_action", None) == "bottlenecks":
            from .graph_handler import handle_backlog_command
            return handle_backlog_command(args, config)

        if getattr(args, "backlog_action", None) == "sweep":
            from .queue_handler import handle_queue_command
            setattr(args, "queue_action", "digest")
            return handle_queue_command(args, config, parser)


        from ..tui.flow_monitor import FlowMonitor

        monitor = FlowMonitor(config)
        if getattr(args, "once", False):
            monitor.render_snapshot()
            return 0
        return monitor.run()

    if args.command == "task":
        from .task_handler import handle_task_command
        return handle_task_command(args, config, parser)

    if args.command == "check":
        from ..rescue.fast_check import handle_fast_check_command
        return handle_fast_check_command(args, config)

    if args.command == "doctor":
        from ..rescue.doctor import handle_doctor_command
        return handle_doctor_command(args, config)

    if args.command == "test":
        from .test_handler import handle_test_command
        return handle_test_command(args, config, parser)

    if args.command == "schema":
        from .schema_handler import handle_schema_command
        return handle_schema_command(args, config)

    if args.command == "verify":
        from ..core.properties_runner import handle_properties_command
        return handle_properties_command(args, config)

    if args.command == "watch":
        from .graph_handler import handle_watch_command
        return handle_watch_command(args, config)

    if args.command == "invariants":
        from .test_handler import handle_mutation_command
        if getattr(args, "invariants_action", None) == "verify-mutations":
            return handle_mutation_command(args, config)
        parser.parse_args(["invariants", "--help"])
    if args.command == "persona":
        from .persona_handler import handle_persona_command
        return handle_persona_command(args, config, parser)

    return 0


if __name__ == "__main__":
    sys.exit(main())
