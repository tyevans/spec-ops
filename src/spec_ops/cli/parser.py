"""CLI argument parser definition for SpecOps."""

from __future__ import annotations

import argparse


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
    p_init.add_argument(
        "--agent",
        "--agents",
        dest="agent",
        action="append",
        default=None,
        help="Target agent platform adapters to configure (antigravity, claude, cursor). Comma-separated or repeatable.",
    )

    # docs
    p_docs = subparsers.add_parser("docs", help="Compile Diataxis documentation and static site")
    docs_subs = p_docs.add_subparsers(dest="docs_action", help="Documentation action")
    p_build = docs_subs.add_parser("build", help="Compile static HTML documentation site and living 2D visualizer")
    p_build.add_argument("--out", help="Output directory for static site (default: site/)")
    p_build.add_argument("--base-url", default="/spec-ops/", help="Base URL path for links (default: /spec-ops/)")
    p_audit = docs_subs.add_parser("audit", help="Audit Diataxis documentation structure, CLI drift, and code snippets")
    p_audit.add_argument("--dir", help="Documentation directory (default: docs/)")
    p_audit.add_argument("--strict", action="store_true", help="Fail if any warnings or drift are detected")

    # profiles
    p_prof = subparsers.add_parser("profiles", aliases=["profile"], help="Inspect and list architectural profiles and baseline ADRs")
    prof_subs = p_prof.add_subparsers(dest="profile_action", help="Profile action")
    prof_subs.add_parser("list", help="List all available profiles and their baseline ADRs")
    p_prof_apply = prof_subs.add_parser("apply", help="Apply architectural profile to current repository")
    p_prof_apply.add_argument("profile_name", help="Profile name (e.g. security)")
    p_prof_sync = prof_subs.add_parser("sync", help="Synchronize or restore architectural profile artifacts")
    p_prof_sync.add_argument("profile_name", help="Profile name (e.g. security)")

    # scaffold
    p_scaffold = subparsers.add_parser("scaffold", help="Scaffold or regenerate project components")
    scaffold_subs = p_scaffold.add_subparsers(dest="scaffold_action", help="Scaffolding action")
    scaffold_subs.add_parser("agents", help="Regenerate AGENTS.md constitution from installed profiles")

    # health
    p_health = subparsers.add_parser("health", help="Check file length invariants, buffer health, and priority sync")
    p_health.add_argument("--security", action="store_true", help="Check security profile policies and guardrails")

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
    p_worker.add_argument("--no-review", "--skip-review", dest="no_review", action="store_true", help="Skip architectural review step")

    # cycle
    p_cycle = subparsers.add_parser("cycle", help="Execute end-to-end autonomous development cycle")
    p_cycle.add_argument("--max-tasks", type=int, default=1, help="Maximum number of ready tasks to execute (default: 1)")
    p_cycle.add_argument("--dry-run", action="store_true", help="Run without invoking agents")
    p_cycle.add_argument("--no-merge", action="store_true", help="Do not squash-merge branches to main")
    p_cycle.add_argument("--build-docs", action="store_true", help="Compile documentation static site after cycle")
    p_cycle.add_argument("--no-review", "--skip-review", dest="no_review", action="store_true", help="Skip architectural review step")


    # rescue
    p_rescue = subparsers.add_parser("rescue", help="Inspect and recover stalled or failed autonomous worktrees")
    p_rescue.add_argument("task_id", nargs="?", help="Target task canonical ID (e.g. TASK-0011 or 0011)")
    p_rescue.add_argument("--list", action="store_true", help="List all active/stalled worktrees")
    p_rescue.add_argument("--complete", action="store_true", help="Verify preflight and merge rescued worktree into main")
    p_rescue.add_argument("--discard", action="store_true", help="Discard worktree and branch")
    p_rescue.add_argument("--prune", action="store_true", help="Prune and clean up all stale/orphaned worktrees")

    # tui
    p_tui = subparsers.add_parser("tui", help="Launch interactive Terminal UI (TUI) dashboard")
    p_tui.add_argument("--once", action="store_true", help="Render dashboard snapshot and exit without interactive loop")
    p_tui.add_argument("--view", choices=["overview", "backlog", "tree", "health"], default="overview", help="Initial view to display (default: overview)")

    return parser
