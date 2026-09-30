"""SpecOps unified command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

from ..backlog.curator import BacklogCurator
from ..backlog.health import HealthChecker
from ..config.loader import load_config
from ..scaffold.init import init_project
from ..visualizer.generator import generate_standalone_html
from ..visualizer.server import serve_visualizer
from .parser import build_parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    config = load_config()

    if args.command in ("profile", "profiles"):
        from .profile_handler import handle_profile_command
        return handle_profile_command(args, config)

    if args.command == "scaffold":
        if args.scaffold_action == "agents":
            from ..scaffold.agents_md import scaffold_agents_command
            msg = scaffold_agents_command(config.root_dir)
            print(f"✨ {msg}")
            return 0
        else:
            parser.parse_args(["scaffold", "--help"])
            return 0

    if args.command == "adopt":
        from .adopt_handler import handle_adopt_command
        return handle_adopt_command(args)

    if args.command == "decompose":
        from .decompose_handler import handle_decompose_command
        return handle_decompose_command(args)

    if args.command == "init":
        target = Path(args.dir).resolve()
        profile_list = [p.strip() for p in args.profile.split(",") if p.strip()]
        try:
            created = init_project(
                target,
                name=args.name,
                profiles=profile_list,
                diataxis=args.diataxis,
                github_pages=args.github_pages,
                pre_commit=args.pre_commit,
                agents=args.agent,
            )
        except Exception as err:
            from ..profiles.models import ProfileError

            if isinstance(err, ProfileError):
                print(f"{err}", file=sys.stderr)
            else:
                print(f"❌ Initialization error: {err}", file=sys.stderr)
            return 1
        print(f"✨ Initialized SpecOps in {target}")
        print(f"📋 Installed Profiles: {', '.join(profile_list)}")
        if args.agent:
            from ..scaffold.adapters import parse_target_agents

            configured_agents = parse_target_agents(args.agent)
            if configured_agents:
                print(f"🤖 Configured Agent Adapters: {', '.join(configured_agents)}")
        print(f"📁 Created {len(created)} file(s) and directory structures.")
        print("👉 Run 'spec-ops health' to verify repository invariants.")
        return 0

    if args.command == "docs":
        if args.docs_action == "audit":
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
        if getattr(args, "architecture", False):
            from .health_handler import handle_health_architecture
            return handle_health_architecture(config)

        if getattr(args, "suggest_splits", False):
            from .health_handler import handle_health_suggest_splits
            return handle_health_suggest_splits(config, emit_task=getattr(args, "emit_task", False))

        if getattr(args, "generate_refactor_tasks", False):
            from .health_handler import handle_health_generate_refactor_tasks
            return handle_health_generate_refactor_tasks(config)

        if getattr(args, "check_uat", False):
            from ..prd.uat import handle_check_uat
            return handle_check_uat(config)


        checker = HealthChecker(config)
        report = checker.run_check()
        if getattr(args, "json", False):
            from .formatters import format_health_json
            print(format_health_json(report, config))
            return 0 if report.is_healthy else 1

        print(f"=== SpecOps Health Check ({config.project.name}) ===")
        print(f"Limit: <{config.architecture.file_length_limit} lines per file")
        if report.violations:
            print(f"❌ {len(report.violations)} File Length Violation(s):")
            for v in report.violations:
                print(f"File Length Violation: {v.path} ({v.lines} lines > {v.limit} line limit)")
                if getattr(v, "is_expanded", False):
                    print(f"   {v.path}: {v.lines} lines (expanded beyond recorded baseline {v.limit} lines)")
                else:
                    print(f"   {v.path}: {v.lines} lines (limit: {v.limit}) - unexempt file limit violation (>500 lines)")
        else:
            print("✅ Invariant Met: Zero source files exceed length limit.")

        if getattr(report, "grandfathered_debt", None):
            print(f"ℹ️ {len(report.grandfathered_debt)} grandfathered files remain tracked debt items.")

        if report.warnings:
            print(f"\n⚠️ {len(report.warnings)} Proactive Refactoring Warning(s) (approaching limit):")
            for w in report.warnings:
                print(f"⚠️ Proactive Refactoring Warning: {w.path} ({w.lines} lines >= {w.threshold} line warning threshold)")
                print(f"   {w.path}: {w.lines} lines (warning threshold: {w.threshold}, limit: {w.limit})")

        if report.constitution_drift_warnings:
            print(f"\n⚠️ {len(report.constitution_drift_warnings)} Constitution Drift Warning(s):")
            for cw in report.constitution_drift_warnings:
                print(f"   - {cw}")
        else:
            print("✅ 0 file limit violations (<500 lines) and 0 constitution drift warnings.")

        print("\nBacklog State:")
        print(f"   Complete Tasks: {report.completed_tasks}")
        print(f"   Refined Buffer: {report.refined_tasks} ({report.buffer_status})")
        print(f"   Proposed Tasks: {report.proposed_tasks}")

        if not report.priority_sync_ok:
            print("❌ PRIORITY.md Sync Errors:")
            for err in report.sync_errors:
                print(f"   - {err}")
        else:
            print("✅ PRIORITY.md is synchronized with disk state.")

        if getattr(args, "security", False):
            has_sec = (
                config.security is not None
                or (config.root_dir / "docs" / "project" / "SECURITY.md").exists()
                or (
                    (config.root_dir / "specops.toml").is_file()
                    and "[security]" in (config.root_dir / "specops.toml").read_text(encoding="utf-8")
                )
            )
            if has_sec:
                sec_ok, sec_msg = checker.check_security_policy()
                if not sec_ok:
                    print(f"❌ {sec_msg}")
                    return 1
                print(f"✅ {sec_msg}")

            from ..security.secrets.scanner import scan_worktree

            scan_report = scan_worktree(config.root_dir)
            if not scan_report.is_clean:
                print(scan_report.format_diagnostics())
                return 1
            print("✅ Security Invariant Met: 0 credential leaks detected in working tree.")

        return 0 if report.is_healthy else 1

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
        res = curator.curate()
        print("=== Backlog Curation ===")
        print(res.message)
        if res.tasks_refined:
            print("Refined tasks:")
            for tid in res.tasks_refined:
                print(f"   ✓ {tid}")
        return 0

    if args.command == "visualizer":
        from ..visualizer.bundle import export_bundle

        if getattr(args, "viz_action", None) == "export":
            target = getattr(args, "out_pos", None) or getattr(args, "output", "dist/index.html")
            out_file = export_bundle(config, output_path=target)
            print(f"✅ Exported standalone visualizer bundle to {out_file}")
            return 0
        elif args.build:
            out_file = export_bundle(config, output_path=args.build)
            print(f"✅ Exported standalone visualizer bundle to {out_file}")
            return 0
        else:
            serve_visualizer(config, port=args.port)
            return 0

    if args.command == "worker":
        from .cycle_handler import handle_worker_command
        return handle_worker_command(args, config)

    if args.command == "cycle":
        from .cycle_handler import handle_cycle_command
        return handle_cycle_command(args, config)

    if args.command == "rescue":
        from .rescue_handler import handle_rescue_command
        return handle_rescue_command(args, config)

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

    if args.command == "backlog":
        from ..tui.flow_monitor import FlowMonitor

        monitor = FlowMonitor(config)
        if getattr(args, "once", False):
            monitor.render_snapshot()
            return 0
        return monitor.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
