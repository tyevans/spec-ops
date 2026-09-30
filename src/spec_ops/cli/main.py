"""SpecOps unified command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import subprocess
from ..backlog.curator import BacklogCurator
from ..backlog.health import HealthChecker
from ..backlog.queue import BacklogQueue
from ..backlog.worker import BacklogWorkerEngine
from ..worker import BatchCycleOrchestrator
from ..config.loader import load_config
from ..core.graph import process_project_graph
from ..core.parser import SpecOpsParser
from ..prd.decomposer import PRDDecomposer
from ..prd.manager import PRDManager
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
        except ValueError as err:
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
            site_dir = build_docs_site(config, out_dir=out_dir, base_url=base_url)
            print(f"🎉 Compiled Diataxis documentation and living 2D visualizer to {site_dir}")
            return 0
        else:
            parser.parse_args(["docs", "--help"])
            return 0

    if args.command == "health":
        checker = HealthChecker(config)
        report = checker.run_check()
        print(f"=== SpecOps Health Check ({config.project.name}) ===")
        print(f"Limit: <{config.architecture.file_length_limit} lines per file")
        if report.violations:
            print(f"❌ {len(report.violations)} File Length Violation(s):")
            for v in report.violations:
                print(f"   {v.path}: {v.lines} lines (limit: {v.limit})")
        else:
            print("✅ Invariant Met: Zero source files exceed length limit.")

        if report.warnings:
            print(f"\n⚠️ {len(report.warnings)} Proactive Refactoring Warning(s) (approaching limit):")
            for w in report.warnings:
                print(f"   {w.path}: {w.lines} lines (warning threshold: {w.threshold}, limit: {w.limit})")

        if report.constitution_drift_warnings:
            print(f"\n⚠️ {len(report.constitution_drift_warnings)} Constitution Drift Warning(s):")
            for cw in report.constitution_drift_warnings:
                print(f"   - {cw}")
        else:
            print("✅ 0 file limit violations (<500 lines) and 0 constitution drift warnings.")

        print(f"\nBacklog State:")
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
        p_data = SpecOpsParser(config.project_docs_dir).parse_all()
        process_project_graph(p_data, target_buffer=config.architecture.buffer_target)
        m = p_data.health_metrics
        print(f"=== SpecOps Project Statistics ({config.project.name}) ===")
        print(f"Total Tasks: {m['total_tasks']} ({m['complete_tasks']} Complete, {m['refined_tasks']} Refined, {m['proposed_tasks']} Proposed)")
        print(f"User Stories: {m['total_stories']} | PRDs: {m['total_prds']} | ADRs: {m['total_adrs']} | Personas: {m['total_personas']}")
        print(f"Traceability Edges: {m['total_edges']} | Ready Buffer Health: {m['ready_buffer_health']}")
        return 0

    if args.command == "prd":
        from .prd_handler import handle_prd_command
        return handle_prd_command(args, config, parser)

    if args.command == "curate":
        if getattr(args, "infer", False):
            from ..backlog.inference_curator import InferenceCurator

            inf_curator = InferenceCurator(config, model=getattr(args, "model", None))
            inf_res = inf_curator.curate(dry_run=getattr(args, "dry_run", False))
            if getattr(args, "dry_run", False):
                print(inf_res.diff_output)
                print(f"\n{inf_res.message}")
            else:
                print(f"=== Backlog Curation (Inference-Driven) ===")
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
        print(f"=== Backlog Curation ===")
        print(res.message)
        if res.tasks_refined:
            print("Refined tasks:")
            for tid in res.tasks_refined:
                print(f"   ✓ {tid}")
        return 0

    if args.command == "visualizer":
        if args.build:
            html = generate_standalone_html(config)
            out_file = Path(args.build).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(html, encoding="utf-8")
            print(f"✅ Exported standalone visualizer bundle to {out_file}")
            return 0
        else:
            serve_visualizer(config, port=args.port)
            return 0

    if args.command == "worker":
        if getattr(args, "drain", False) or getattr(args, "max_tasks", None) is not None or getattr(args, "max_concurrency", 1) > 1:
            orchestrator = BatchCycleOrchestrator(
                config,
                max_concurrency=getattr(args, "max_concurrency", 1),
                max_tasks=getattr(args, "max_tasks", None),
                drain=getattr(args, "drain", False),
                dry_run=args.dry_run,
                no_merge=args.no_merge,
            )
            report = orchestrator.run()
            return 0 if not report.tasks_failed else 1

        worker = BacklogWorkerEngine(config)
        queue = BacklogQueue(config.backlog_dir)
        target_task = None
        target_task_id = args.task
        action_or_task = getattr(args, "action_or_task", None)
        task_pos = getattr(args, "task_pos", None)
        if action_or_task:
            if action_or_task.lower() == "execute":
                target_task_id = task_pos or target_task_id
            else:
                target_task_id = action_or_task or target_task_id
        elif task_pos:
            target_task_id = task_pos

        if target_task_id:
            clean_id = target_task_id.upper()
            if not clean_id.startswith("TASK-") and clean_id.isdigit():
                clean_id = f"TASK-{clean_id.zfill(4)}"
            for t in queue.list_all_tasks():
                if t.canonical_id == clean_id:
                    target_task = t
                    break
            if not target_task:
                print(f"❌ Task {target_task_id} not found in backlog.")
                return 1
        else:
            ready = queue.get_ready_unblocked_tasks()
            if not ready:
                print("ℹ️ No ready, unblocked tasks in refined/ buffer. Run 'spec-ops curate' first.")
                return 0
            target_task = ready[0]

        res = worker.execute_task(
            target_task,
            local_merge=not args.no_merge,
            dry_run=args.dry_run,
            skip_review=getattr(args, "no_review", False),
        )
        print(f"=== Worker Result ({target_task.canonical_id}) ===")
        print(f"Status: {'✅ SUCCESS' if res.success else '❌ FAILED'}")
        print(f"Message: {res.message}")
        return 0 if res.success else 1

    if args.command == "cycle":
        print(f"🔄 Starting autonomous SpecOps development lifecycle ({config.project.name})...")
        # Step 1: PRD Audit & Decompose
        mgr = PRDManager(config)
        audit_res = mgr.audit()
        if audit_res.undecomposed_prds:
            decomposer = PRDDecomposer(config)
            for prd_id in audit_res.undecomposed_prds:
                print(f"📄 Decomposing accepted PRD {prd_id}...")
                decomposer.decompose(prd_id)

        # Step 2: JIT Curate Backlog
        curator = BacklogCurator(config)
        cur_res = curator.curate()
        print(f"📋 Backlog Curation: {cur_res.message}")

        # Step 3: Health Check
        checker = HealthChecker(config)
        h_report = checker.run_check()
        if not h_report.is_healthy:
            print("❌ Invariant health check failed. Stopping cycle.")
            for v in h_report.violations:
                print(f"   Violation: {v.path} ({v.lines} lines > {v.limit})")
            for err in h_report.sync_errors:
                print(f"   Sync Error: {err}")
            return 1
        print("✅ Health invariants verified: 0 file violations, PRIORITY.md synchronized.")

        # Step 4: Worker Execution
        max_concurrency = getattr(args, "max_concurrency", 3)
        drain = getattr(args, "drain", False)
        max_tasks = getattr(args, "max_tasks", None)
        if not drain and max_tasks is None:
            max_tasks = 1

        orchestrator = BatchCycleOrchestrator(
            config,
            max_concurrency=max_concurrency,
            max_tasks=max_tasks,
            drain=drain,
            dry_run=args.dry_run,
            no_merge=args.no_merge,
            skip_review=getattr(args, "no_review", False),
        )
        report = orchestrator.run()
        if report.tasks_failed:
            print(f"❌ Cycle finished with {len(report.tasks_failed)} failure(s).")
            return 1

        # Step 5: Visualizer & Docs build
        if getattr(args, "build_docs", False):
            print("📚 Compiling documentation and living 2D visualizer...")
            from ..docs.builder import build_docs_site
            build_docs_site(config)

        print("\n🎉 Autonomous cycle completed cleanly.")
        return 0

    if args.command == "rescue":
        from ..backlog.rescue import WorktreeRescueManager

        mgr = WorktreeRescueManager(config)

        if getattr(args, "prune", False):
            count = mgr.prune_all_worktrees()
            print(f"🧹 Pruned and cleaned up {count} worktree(s).")
            return 0

        if args.list or not args.task_id:
            wts = mgr.list_active_worktrees()
            print("=== Active / Stalled Worktrees (.worktrees/) ===")
            if not wts:
                print("No active or stalled worktrees found.")
                return 0
            for w in wts:
                dirty = " [DIRTY]" if w.is_dirty else ""
                print(f"• {w.task_id} ({w.branch}){dirty} at {w.worktree_dir}")
                if w.failure_feedback:
                    print(f"  Diagnostics: {w.failure_feedback[:100]}...")
            return 0

        if args.complete:
            ok, msg = mgr.complete_rescue(args.task_id)
            print(f"=== Worktree Rescue: {args.task_id} ===")
            print(f"Status: {'✅ SUCCESS' if ok else '❌ FAILED'}")
            print(msg)
            return 0 if ok else 1

        if args.discard:
            ok, msg = mgr.discard_worktree(args.task_id)
            print(msg)
            return 0 if ok else 1

        info = mgr.inspect_task(args.task_id)
        if not info:
            print(f"❌ No worktree found for {args.task_id}.")
            return 1

        print(f"=== Stalled Worktree: {info.task_id} ===")
        print(f"Directory: {info.worktree_dir}")
        print(f"Branch:    {info.branch}")
        print(f"Dirty:     {info.is_dirty}")
        if info.failure_feedback:
            print(f"\nLast Diagnostics:\n{info.failure_feedback}\n")
        print("👉 To finish and integrate: run 'spec-ops rescue <task-id> --complete'")
        print("👉 To discard: run 'spec-ops rescue <task-id> --discard'")
        return 0

    if args.command == "tui":
        from ..tui import TUIDashboard

        dashboard = TUIDashboard(config)
        if getattr(args, "once", False):
            dashboard.render_snapshot(view=getattr(args, "view", "overview"))
            return 0
        return dashboard.run(initial_view=getattr(args, "view", "overview"))

    if args.command == "security":
        from .security_handler import handle_security_command
        return handle_security_command(args, config, parser)

    if args.command == "queue":
        from .security_handler import handle_queue_command
        return handle_queue_command(args, config, parser)

    return 0


if __name__ == "__main__":
    sys.exit(main())
