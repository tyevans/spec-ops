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
    p_init.add_argument("--diataxis", action="store_true", default=True, help="Scaffold Diataxis documentation structure (default: True)")
    p_init.add_argument("--no-diataxis", dest="diataxis", action="store_false", help="Skip Diataxis documentation scaffolding")
    p_init.add_argument("--github-pages", action="store_true", default=True, help="Scaffold GitHub Pages deployment workflow (default: True)")
    p_init.add_argument("--no-github-pages", dest="github_pages", action="store_false", help="Skip GitHub Pages deployment workflow scaffolding")
    p_init.add_argument("--pre-commit", action="store_true", default=True, help="Scaffold .pre-commit-config.yaml hook configuration (default: True)")
    p_init.add_argument("--no-pre-commit", dest="pre_commit", action="store_false", help="Skip .pre-commit-config.yaml scaffolding")

    # docs
    p_docs = subparsers.add_parser("docs", help="Compile Diataxis documentation and static site")
    docs_subs = p_docs.add_subparsers(dest="docs_action", help="Documentation action")
    p_build = docs_subs.add_parser("build", help="Compile static HTML documentation site and living 2D visualizer")
    p_build.add_argument("--out", help="Output directory for static site (default: site/)")
    p_build.add_argument("--base-url", default="/spec-ops/", help="Base URL path for links (default: /spec-ops/)")

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
    # rescue
    p_rescue = subparsers.add_parser("rescue", help="Inspect and recover stalled or failed autonomous worktrees")
    p_rescue.add_argument("task_id", nargs="?", help="Target task canonical ID (e.g. TASK-0011 or 0011)")
    p_rescue.add_argument("--list", action="store_true", help="List all active/stalled worktrees")
    p_rescue.add_argument("--complete", action="store_true", help="Verify preflight and merge rescued worktree into main")
    p_rescue.add_argument("--discard", action="store_true", help="Discard worktree and branch")
    p_rescue.add_argument("--prune", action="store_true", help="Prune and clean up all stale/orphaned worktrees")

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
        created = init_project(
            target,
            name=args.name,
            profiles=profile_list,
            diataxis=args.diataxis,
            github_pages=args.github_pages,
            pre_commit=args.pre_commit,
        )
        print(f"✨ Initialized SpecOps in {target}")
        print(f"📋 Installed Profiles: {', '.join(profile_list)}")
        print(f"📁 Created {len(created)} file(s) and directory structures.")
        print("👉 Run 'spec-ops health' to verify repository invariants.")
        return 0

    config = load_config()

    if args.command == "docs":
        if args.docs_action == "build" or not args.docs_action:
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
        print(f"User Stories: {m['total_stories']} | PRDs: {m['total_prds']} | ADRs: {m['total_adrs']} | Personas: {m['total_personas']}")
        print(f"Traceability Edges: {m['total_edges']} | Ready Buffer Health: {m['ready_buffer_health']}")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
