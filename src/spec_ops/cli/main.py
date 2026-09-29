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
from ..config.loader import load_config
from ..core.graph import process_project_graph
from ..core.parser import SpecOpsParser
from ..prd.decomposer import PRDDecomposer
from ..prd.manager import PRDManager
from ..scaffold.init import init_project
from ..visualizer.generator import generate_standalone_html
from ..visualizer.server import serve_visualizer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-ops",
        description="SpecOps: Opinionated Project Management as Code and Autonomous Delivery Engine",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize SpecOps structure in target directory")
    p_init.add_argument("--name", help="Project name (defaults to directory name)")
    p_init.add_argument("--dir", default=".", help="Target directory (default: current directory)")
    p_init.add_argument("--profile", default="core,bdd,ddd", help="Comma-separated architectural profiles to install (default: core,bdd,ddd)")

    # profiles
    p_prof = subparsers.add_parser("profiles", help="Inspect and list architectural profiles and baseline ADRs")
    prof_subs = p_prof.add_subparsers(dest="profile_action", help="Profile action")
    prof_subs.add_parser("list", help="List all available profiles and their baseline ADRs")

    # health
    subparsers.add_parser("health", help="Check file length invariants, buffer health, and priority sync")

    # stats
    subparsers.add_parser("stats", help="Inspect entity counts, graph metrics, and buffer state")

    # prd
    p_prd = subparsers.add_parser("prd", help="PRD management commands")
    prd_subs = p_prd.add_subparsers(dest="prd_action", help="PRD action")

    p_create = prd_subs.add_parser("create", help="Scaffold a new PRD")
    p_create.add_argument("--title", required=True, help="PRD title")
    p_create.add_argument("--persona", default="", help="Target persona")
    p_create.add_argument("--component", default="", help="Owning component / bounded context")
    p_create.add_argument("--summary", default="", help="Brief summary of problem statement")
    p_create.add_argument("--stage", default="accepted", help="Stage (accepted, idea, shaped)")

    prd_subs.add_parser("audit", help="Audit PRD decomposition state and buffer readiness")

    p_decompose = prd_subs.add_parser("decompose", help="Decompose a PRD into vertical slices and stories")
    p_decompose.add_argument("prd_id", help="PRD canonical identifier (e.g. PRD-0001 or 0001)")
    p_decompose.add_argument("--no-spike", action="store_true", help="Omit initial architectural spike")

    # curate
    subparsers.add_parser("curate", help="Perform JIT backlog refinement to target buffer size")

    # visualizer
    p_viz = subparsers.add_parser("visualizer", help="Living 2D graph visualizer")
    p_viz.add_argument("--serve", action="store_true", help="Run local interactive web server")
    p_viz.add_argument("--port", type=int, default=8787, help="Server port (default: 8787)")
    p_viz.add_argument("--build", metavar="OUT_FILE", help="Generate standalone single-file HTML bundle")

    # worker
    p_worker = subparsers.add_parser("worker", help="Execute backlog task in isolated worktree")
    p_worker.add_argument("--task", help="Target task canonical ID (e.g. TASK-0009)")
    p_worker.add_argument("--dry-run", action="store_true", help="Generate prompt without invoking agent")
    p_worker.add_argument("--no-merge", action="store_true", help="Do not merge branch to main on completion")

    # cycle
    p_cycle = subparsers.add_parser("cycle", help="Execute end-to-end autonomous development cycle")
    p_cycle.add_argument("--max-tasks", type=int, default=1, help="Maximum number of ready tasks to execute (default: 1)")
    p_cycle.add_argument("--dry-run", action="store_true", help="Run without invoking agents")
    p_cycle.add_argument("--no-merge", action="store_true", help="Do not squash-merge branches to main")
    p_cycle.add_argument("--build-docs", action="store_true", help="Recompile documentation site and visualizer")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "profiles":
        from ..profiles.registry import list_profiles
        profiles = list_profiles()
        print("=== SpecOps Architectural Profiles & Baseline ADRs ===")
        for p in profiles:
            print(f"\n📦 Profile: {p.id} — {p.name}")
            print(f"   {p.description}")
            print("   Baseline ADRs:")
            for adr in p.adrs:
                print(f"     • {adr.canonical_id}: {adr.title}")
        return 0

    if args.command == "init":
        target = Path(args.dir).resolve()
        profile_list = [p.strip() for p in args.profile.split(",") if p.strip()]
        created = init_project(target, name=args.name, profiles=profile_list)
        print(f"✨ Initialized SpecOps in {target}")
        print(f"📋 Installed Profiles: {', '.join(profile_list)}")
        print(f"📁 Created {len(created)} file(s) and directory structures.")
        print("👉 Run 'spec-ops health' to verify repository invariants.")
        return 0

    config = load_config()

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

        return 0 if report.is_healthy else 1

    if args.command == "stats":
        p_data = SpecOpsParser(config.project_docs_dir).parse_all()
        process_project_graph(p_data, target_buffer=config.architecture.buffer_target)
        m = p_data.health_metrics
        print(f"=== SpecOps Project Statistics ({config.project.name}) ===")
        print(f"Total Tasks: {m['total_tasks']} ({m['complete_tasks']} Complete, {m['refined_tasks']} Refined, {m['proposed_tasks']} Proposed)")
        print(f"User Stories: {m['total_stories']}")
        print(f"PRDs: {m['total_prds']}")
        print(f"ADRs: {m['total_adrs']}")
        print(f"Personas: {m['total_personas']}")
        print(f"Traceability Edges: {m['total_edges']}")
        print(f"Ready Buffer Health: {m['ready_buffer_health']}")
        return 0

    if args.command == "prd":
        mgr = PRDManager(config)
        if args.prd_action == "create":
            p = mgr.create_prd(
                title=args.title,
                persona=args.persona,
                component=args.component,
                summary=args.summary,
                stage=args.stage,
            )
            print(f"✅ Created PRD at {p}")
            return 0
        elif args.prd_action == "audit":
            res = mgr.audit()
            print(f"=== PRD Audit ===")
            print(f"Total PRDs: {res.total_prds}")
            print(f"Undecomposed PRDs: {len(res.undecomposed_prds)} ({', '.join(res.undecomposed_prds) or 'None'})")
            print(f"Ready Tasks Buffer: {res.ready_tasks_count} ({res.buffer_status})")
            if res.warnings:
                for w in res.warnings:
                    print(f"⚠️ {w}")
            return 0
        elif args.prd_action == "decompose":
            decomposer = PRDDecomposer(config)
            tasks = decomposer.decompose(args.prd_id, include_spike=not args.no_spike)
            print(f"✅ Decomposed {args.prd_id} into {len(tasks)} task(s):")
            for t in tasks:
                print(f"   - {t.name}")
            return 0
        else:
            parser.parse_args(["prd", "--help"])
            return 0

    if args.command == "curate":
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
        worker = BacklogWorkerEngine(config)
        queue = BacklogQueue(config.backlog_dir)
        target_task = None
        if args.task:
            clean_id = args.task.upper()
            if not clean_id.startswith("TASK-") and clean_id.isdigit():
                clean_id = f"TASK-{clean_id.zfill(4)}"
            for t in queue.list_all_tasks():
                if t.canonical_id == clean_id:
                    target_task = t
                    break
            if not target_task:
                print(f"❌ Task {args.task} not found in backlog.")
                return 1
        else:
            ready = queue.get_ready_unblocked_tasks()
            if not ready:
                print("ℹ️ No ready, unblocked tasks in refined/ buffer. Run 'spec-ops curate' first.")
                return 0
            target_task = ready[0]

        res = worker.execute_task(target_task, local_merge=not args.no_merge, dry_run=args.dry_run)
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
        queue = BacklogQueue(config.backlog_dir)
        ready_tasks = queue.get_ready_unblocked_tasks()
        if not ready_tasks:
            print("ℹ️ No ready unblocked tasks to execute.")
        else:
            limit = args.max_tasks if hasattr(args, "max_tasks") and args.max_tasks else 1
            tasks_to_run = ready_tasks[:limit]
            worker = BacklogWorkerEngine(config)
            for task in tasks_to_run:
                print(f"\n🚀 Executing next ready task: {task.canonical_id} — {task.title}")
                res = worker.execute_task(task, local_merge=not args.no_merge, dry_run=args.dry_run)
                if not res.success:
                    print(f"❌ Worker failed on {task.canonical_id}: {res.message}")
                    return 1
                print(f"✅ Successfully integrated {task.canonical_id}.")

        # Step 5: Visualizer & Docs build
        if getattr(args, "build_docs", False):
            print("📚 Compiling documentation and living 2D visualizer...")
            build_script = config.root_dir / "scripts" / "build_docs.py"
            if build_script.exists():
                subprocess.run([sys.executable, str(build_script)], cwd=config.root_dir, check=False)

        print("\n🎉 Autonomous cycle completed cleanly.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
