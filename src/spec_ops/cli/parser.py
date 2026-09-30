"""CLI argument parser definition for SpecOps."""

from __future__ import annotations

import argparse

from .parser_subcommands import (
    register_adr_subparsers,
    register_audit_subparsers,
    register_export_subparsers,
    register_graph_subparsers,
    register_prd_subparsers,
    register_profile_subparsers,
    register_queue_subparsers,
    register_release_subparsers,
    register_schema_subparsers,
    register_spike_subparsers,
    register_test_subparsers,
)


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
    p_init.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        default=False,
        help="Launch interactive guided initialization wizard",
    )
    p_init.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run unattended headless initialization without prompting",
    )
    p_init.add_argument(
        "--non-interactive",
        dest="headless",
        action="store_true",
        help="Alias for --headless unattended initialization",
    )
    p_init.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate initialization and output planned file manifest and specops.toml without writing to disk",
    )
    p_init.add_argument(
        "--ci",
        choices=["github", "gitlab", "all", "none"],
        default="github",
        help="CI quality gate provider workflow to scaffold (github, gitlab, all, none)",
    )
    p_init.add_argument(
        "--bc",
        "--bounded-context",
        dest="bc",
        action="append",
        default=None,
        help="Initial bounded context(s) to declare (repeatable or comma-separated)",
    )
    p_init.add_argument(
        "--yes",
        "-y",
        action="store_true",
        default=False,
        help="Automatically confirm initialization prompts",
    )

    # adopt
    p_adopt = subparsers.add_parser("adopt", help="Adopt SpecOps into an existing brownfield codebase with debt baseline")
    p_adopt.add_argument("--name", help="Project name (defaults to directory name)")
    p_adopt.add_argument("--dir", default=".", help="Target directory (default: current directory)")
    p_adopt.add_argument("--profile", default="core,bdd,ddd", help="Comma-separated architectural profiles to install (default: core,bdd,ddd)")
    p_adopt.add_argument("--grandfather-debt", action="store_true", default=True, help="Baseline existing files exceeding file limits into debt tracker (default: True)")
    p_adopt.add_argument("--no-grandfather-debt", dest="grandfather_debt", action="store_false", help="Do not grandfather existing debt")

    # docs
    p_docs = subparsers.add_parser("docs", help="Compile Diataxis documentation and static site")
    docs_subs = p_docs.add_subparsers(dest="docs_action", help="Documentation action")
    p_build = docs_subs.add_parser("build", help="Compile static HTML documentation site and living 2D visualizer")
    p_build.add_argument("--out", help="Output directory for static site (default: site/)")
    p_build.add_argument("--base-url", default="/spec-ops/", help="Base URL path for links (default: /spec-ops/)")
    p_build.add_argument("--include-visualizer", action="store_true", default=True, help="Compile living visualizer bundle into site (default: True)")
    p_audit = docs_subs.add_parser("audit", help="Audit Diataxis documentation structure, CLI drift, and code snippets")
    p_audit.add_argument("--dir", help="Documentation directory (default: docs/)")
    p_audit.add_argument("--strict", action="store_true", help="Fail if any warnings or drift are detected")
    p_check = docs_subs.add_parser("check", help="Audit public CLI commands against Diataxis documentation and flag drift")
    p_check.add_argument("--dir", help="Documentation directory (default: docs/)")

    # audit
    register_audit_subparsers(subparsers)

    # profiles
    register_profile_subparsers(subparsers)

    # adr
    register_adr_subparsers(subparsers)

    # scaffold
    p_scaffold = subparsers.add_parser("scaffold", help="Scaffold or regenerate project components")
    scaffold_subs = p_scaffold.add_subparsers(dest="scaffold_action", help="Scaffolding action")
    scaffold_subs.add_parser("agents", help="Regenerate AGENTS.md constitution from installed profiles")
    p_scaffold_docs = scaffold_subs.add_parser(
        "docs",
        aliases=["diataxis"],
        help="Scaffold 4-quadrant Diataxis documentation for a bounded context",
    )
    p_scaffold_docs.add_argument(
        "--bc",
        "--bounded-context",
        required=True,
        dest="bc",
        help="Target bounded context identifier",
    )
    p_scaffold_docs.add_argument(
        "--title",
        default=None,
        help="Human-readable title for the bounded context",
    )
    p_scaffold_docs.add_argument(
        "--force",
        "--overwrite",
        dest="force",
        action="store_true",
        help="Overwrite existing bounded context documentation",
    )

    # constitution
    p_const = subparsers.add_parser("constitution", help="Living constitution synchronization and drift verification")
    const_subs = p_const.add_subparsers(dest="constitution_action", help="Constitution action")
    p_const_sync = const_subs.add_parser("sync", help="Synchronize AGENTS.md and operating manual while preserving custom invariants")
    p_const_sync.add_argument("--repo", default=".", help="Path to repository root (default: current directory)")
    p_const_check = const_subs.add_parser("check", help="Check for drift between specops.toml and AGENTS.md")
    p_const_check.add_argument("--repo", default=".", help="Path to repository root (default: current directory)")

    # health
    p_health = subparsers.add_parser("health", help="Check file length invariants, buffer health, and priority sync")
    p_health.add_argument("--security", action="store_true", help="Check security profile policies and guardrails")
    p_health.add_argument("--architecture", action="store_true", help="Statically verify bounded context boundaries and dependency directions")
    p_health.add_argument("--suggest-splits", action="store_true", help="Analyze files in warning threshold and suggest AST submodule splits")
    p_health.add_argument("--emit-task", action="store_true", help="Emit proposed refactoring task into backlog for split suggestions")
    p_health.add_argument("--generate-refactor-tasks", action="store_true", help="Generate backlog refactoring tasks for all grandfathered debt files")
    p_health.add_argument("--check-uat", action="store_true", help="Verify PM UAT sign-off for all checkable outcomes")
    p_health.add_argument("--json", action="store_true", help="Output health inspection results as structured JSON")


    # decompose
    p_decomp = subparsers.add_parser("decompose", help="Analyze AST seams and recommend modular file decomposition")
    p_decomp.add_argument("--suggest", metavar="PATH", help="Analyze target source file AST and suggest cohesive submodule splits")
    p_decomp.add_argument("path", nargs="?", default=None, help="Target file path")

    # stats
    p_stats = subparsers.add_parser("stats", help="Inspect entity counts, graph metrics, and buffer state")
    p_stats.add_argument("--cache", action="store_true", help="Accelerate graph compilation with content-addressed cache")
    p_stats.add_argument("--persona-coverage", action="store_true", help="Audit task and story distribution across customer personas")

    # parse
    p_parse = subparsers.add_parser("parse", help="Parse specification file with resilient AST diagnostics")
    p_parse.add_argument("path", help="Path to markdown specification file to parse")

    # graph
    register_graph_subparsers(subparsers)

    # trace
    p_trace = subparsers.add_parser("trace", help="Audit end-to-end bidirectional graph linkages and traceability")
    p_trace.add_argument("--verify", action="store_true", default=True, help="Verify bidirectional graph connectivity and orphan work items")


    # prd
    register_prd_subparsers(subparsers)

    # export
    register_export_subparsers(subparsers)

    # release
    register_release_subparsers(subparsers)

    # curate
    p_curate = subparsers.add_parser("curate", help="Perform JIT backlog refinement to target buffer size")
    p_curate.add_argument("curate_action", nargs="?", default=None, help="Curation action ('next')")
    p_curate.add_argument("--json", action="store_true", help="Output next task or curation results as structured JSON")
    p_curate.add_argument("--infer", action="store_true", help="Enable cognitive inference-driven curation, architectural drift reconciliation, and scope slicing")
    p_curate.add_argument("--dry-run", action="store_true", help="Audit candidate tasks and display proposed reconciliations without modifying disk state")
    p_curate.add_argument("--model", default=None, help="LLM model name to use for inference")

    # visualizer
    p_viz = subparsers.add_parser("visualizer", help="Living 2D graph visualizer")
    p_viz.add_argument("--serve", action="store_true", help="Run local interactive web server")
    p_viz.add_argument("--port", type=int, default=8787, help="Server port (default: 8787)")
    p_viz.add_argument("--entity", default=None, help="Target entity ID to focus and inspect (e.g. TASK-0009)")
    p_viz.add_argument("--build", metavar="OUT_FILE", help="Generate standalone single-file HTML bundle")
    viz_subs = p_viz.add_subparsers(dest="viz_action", help="Visualizer subcommands")
    p_export = viz_subs.add_parser("export", help="Export standalone single-file HTML visualizer bundle")
    p_export.add_argument("out_pos", nargs="?", default=None, help="Output file path (positional)")
    p_export.add_argument("-o", "--output", default="dist/index.html", help="Output file path (default: dist/index.html)")

    # worker
    p_worker = subparsers.add_parser("worker", help="Execute backlog task in isolated worktree")
    p_worker.add_argument("action_or_task", nargs="?", default=None, help="Action ('execute', 'claim', 'ci-heal') or target task canonical ID (e.g. TASK-0009)")
    p_worker.add_argument("task_pos", nargs="?", default=None, help="Target task canonical ID when using 'execute' or 'claim'")
    p_worker.add_argument("--task", help="Target task canonical ID (e.g. TASK-0009)")
    p_worker.add_argument("--auto", action="store_true", help="Claim next ready unblocked task automatically in strict priority order")
    p_worker.add_argument("--drain", action="store_true", help="Continuously drain ready tasks until queue is empty")
    p_worker.add_argument("--max-concurrency", "--max-workers", "--concurrency", dest="max_concurrency", type=int, default=1, help="Maximum number of concurrent workers (default: 1)")
    p_worker.add_argument("--max-tasks", type=int, default=None, help="Maximum number of tasks to execute")
    p_worker.add_argument("--dry-run", action="store_true", help="Generate prompt without invoking agent")
    p_worker.add_argument("--no-merge", action="store_true", help="Do not merge branch to main on completion")
    p_worker.add_argument("--no-review", "--skip-review", dest="no_review", action="store_true", help="Skip architectural review step")
    p_worker.add_argument("--telemetry", action="store_true", help="Display live autonomous worker fleet telemetry and worktree operations")
    p_worker.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    # cycle
    p_cycle = subparsers.add_parser("cycle", help="Execute end-to-end autonomous development cycle")
    p_cycle.add_argument("--max-tasks", type=int, default=None, help="Maximum number of ready tasks to execute (default: 1)")
    p_cycle.add_argument("--max-concurrency", "--max-workers", "--concurrency", dest="max_concurrency", type=int, default=3, help="Maximum number of concurrent workers (default: 3)")
    p_cycle.add_argument("--drain", action="store_true", help="Continuously drain ready tasks until queue is empty")
    p_cycle.add_argument("--dry-run", action="store_true", help="Run without invoking agents")
    p_cycle.add_argument("--no-merge", action="store_true", help="Do not squash-merge branches to main")
    p_cycle.add_argument("--build-docs", action="store_true", help="Compile documentation static site after cycle")
    p_cycle.add_argument("--no-review", "--skip-review", dest="no_review", action="store_true", help="Skip architectural review step")


    # rescue
    p_rescue = subparsers.add_parser("rescue", help="Inspect and recover stalled or failed autonomous worktrees")
    p_rescue.add_argument("task_id", nargs="?", help="Action ('triage', 'takeover', 'inspect', 'shell', 'prune', 'reset') or target task canonical ID (e.g. TASK-0011)")
    p_rescue.add_argument("target", nargs="?", default=None, help="Target task canonical ID when an action is specified (e.g. TASK-0011)")
    p_rescue.add_argument("--list", action="store_true", help="List all active/stalled worktrees")
    p_rescue.add_argument("--complete", action="store_true", help="Verify preflight and merge rescued worktree into main")
    p_rescue.add_argument("--discard", action="store_true", help="Discard worktree and branch")
    p_rescue.add_argument("--reset", action="store_true", help="Reset worktree and capture failure memory")
    p_rescue.add_argument("--reason", default="", help="Failure post-mortem reason description")
    p_rescue.add_argument("--demote", action="store_true", help="Demote task to proposed/ on reset")
    p_rescue.add_argument("--prune", action="store_true", help="Prune and clean up all stale/orphaned worktrees")
    p_rescue.add_argument("--dry-run", action="store_true", help="Dry-run preview of candidate worktrees and disk space")
    p_rescue.add_argument("--file", default=None, help="Target file for AST / line count diff inspection in triage")
    p_rescue.add_argument("--action", default=None, help="Direct triage action ([d]iff, [p]atch, [s]hell, [r]eset, [c]omplete, [q]uit)")
    p_rescue.add_argument("--step", default=None, help="Designated preflight step to run in isolation")
    p_rescue.add_argument("--only-failed", action="store_true", help="Re-run only previously failed preflight step")


    # worktree
    p_worktree = subparsers.add_parser("worktree", help="Human developer worktree sandboxing and lifecycle management")
    wt_subs = p_worktree.add_subparsers(dest="worktree_action", help="Worktree action")
    p_wt_start = wt_subs.add_parser("start", help="Spawn an isolated development worktree for a task")
    p_wt_start.add_argument("task_id", help="Canonical task ID (e.g. TASK-0021 or 0021)")
    p_wt_finish = wt_subs.add_parser("finish", help="Verify preflight, merge into main under MERGE_LOCK, and clean up worktree")
    p_wt_finish.add_argument("--task-id", default=None, help="Target task canonical ID (auto-detected if omitted)")


    # tui
    p_tui = subparsers.add_parser("tui", help="Launch interactive Terminal UI (TUI) dashboard")
    p_tui.add_argument("--once", action="store_true", help="Render dashboard snapshot and exit without interactive loop")
    p_tui.add_argument("--view", choices=["overview", "backlog", "tree", "health"], default="overview", help="Initial view to display (default: overview)")

    # queue
    register_queue_subparsers(subparsers)

    # backlog
    p_backlog = subparsers.add_parser("backlog", help="Backlog flow monitor, buffer telemetry, and bottleneck detection")
    p_backlog.add_argument("--once", action="store_true", help="Render dashboard snapshot without interactive loop")
    backlog_subs = p_backlog.add_subparsers(dest="backlog_action", help="Backlog action")
    p_b_flow = backlog_subs.add_parser("flow", help="Interactive terminal backlog flow monitor and JIT buffer telemetry")
    p_b_flow.add_argument("--once", action="store_true", help="Render dashboard snapshot without interactive loop")
    p_bnk = backlog_subs.add_parser("bottlenecks", help="Detect circular dependency deadlocks and choke points")
    p_bnk.add_argument("--forecast", action="store_true", help="Forecast ready buffer starvation and recommend unblockings")

    # report
    p_report = subparsers.add_parser("report", help="Executive milestone reports, burndown velocity, and presentation decks")
    report_subs = p_report.add_subparsers(dest="report_action", help="Reporting action")

    p_rep_bd = report_subs.add_parser("burndown", help="Milestone burndown velocity and presentation slide deck export")
    p_rep_bd.add_argument("--milestone", default="M1-MVP", help="Target milestone name or ID (default: M1-MVP)")
    p_rep_bd.add_argument("--format", choices=["deck", "html", "digest"], default="deck", help="Report export format (default: deck)")
    p_rep_bd.add_argument("-o", "--output", help="Output file path (default: dist/<milestone>-executive-briefing.html)")
    p_rep_bd.add_argument("--check-alignment", action="store_true", help="Audit completed tasks unanchored from ROADMAP.md")

    p_rep_ms = report_subs.add_parser("milestone", help="Milestone executive briefing digest and scope alignment")
    p_rep_ms.add_argument("--milestone", default="M1-MVP", help="Target milestone name or ID (default: M1-MVP)")
    p_rep_ms.add_argument("--format", choices=["digest", "deck", "html"], default="digest", help="Report format (default: digest)")
    p_rep_ms.add_argument("-o", "--output", help="Output file path")
    p_rep_ms.add_argument("--check-alignment", action="store_true", help="Audit completed tasks unanchored from ROADMAP.md")

    # spike
    register_spike_subparsers(subparsers)

    # security
    p_sec = subparsers.add_parser("security", help="Supply-chain security, verification, and sandboxing")
    sec_subs = p_sec.add_subparsers(dest="security_action", help="Security action")
    p_vlock = sec_subs.add_parser("verify-lock", help="Verify supply-chain lockfile cryptographic hashes and pinning")
    p_vlock.add_argument("--path", default=".", help="Directory containing uv.lock (default: current directory)")

    # review
    p_rev = subparsers.add_parser("review", help="Architectural review and dual-custody human sign-offs")
    p_rev.add_argument("task_or_action", nargs="?", default=None, help="Target task canonical ID (e.g. TASK-0015) or 'sign'")
    p_rev.add_argument("sign_task_id", nargs="?", default=None, help="Target task ID when using 'sign'")
    p_rev.add_argument("--identity", default=None, help="Authorized reviewer identity or key ID (e.g. 'Riley <riley@example.com>')")
    p_rev.add_argument("--provenance", action="store_true", help="Audit commit provenance trailers and author distinction")

    # task
    p_task = subparsers.add_parser("task", help="Ergonomic PMaC task authoring and Definition of Ready scaffolding")
    task_subs = p_task.add_subparsers(dest="task_action", help="Task action")
    p_task_create = task_subs.add_parser("create", help="Scaffold a new PMaC task with Definition of Ready scaffolding")
    p_task_create.add_argument("--title", help="Task title")
    p_task_create.add_argument("--bc", dest="target_bc", help="Target bounded context")
    p_task_create.add_argument("--prd", action="append", help="Governing PRD (repeatable or comma-separated)")
    p_task_create.add_argument("--story", action="append", help="Governing BDD user story (repeatable or comma-separated)")
    p_task_create.add_argument("--adr", action="append", help="Governing ADR (repeatable or comma-separated)")
    p_task_create.add_argument("--deps", "--dependencies", dest="dependencies", action="append", help="Task dependencies (repeatable or comma-separated)")
    p_task_create.add_argument("--stage", choices=["proposed", "refined"], default="proposed", help="Task backlog stage (default: proposed)")
    p_task_create.add_argument("--non-interactive", action="store_true", help="Do not prompt interactively")

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Audit and repair local developer workspace and tooling")
    p_doctor.add_argument("--fix", action="store_true", help="Automatically repair missing hooks and workspace configuration")
    p_doctor.add_argument("--json", action="store_true", help="Output diagnostic results as structured JSON")

    # test
    register_test_subparsers(subparsers)

    # schema
    register_schema_subparsers(subparsers)

    # verify
    p_verify = subparsers.add_parser("verify", help="Execute verification suites and invariant checks")
    p_verify.add_argument("--invariants", action="store_true", help="Execute Hypothesis generative property tests (ADR-0009)")
    p_verify.add_argument("--max-examples", type=int, default=None, help="Maximum number of Hypothesis examples per property")
    p_verify.add_argument("path", nargs="?", default=None, help="Target test file or directory")
    p_verify.add_argument("--path", dest="opt_path", default=None, help="Target test file or directory")
    p_verify.add_argument("-k", "--filter", dest="filter_expr", default=None, help="Filter property tests by name")
    p_verify.add_argument("--json", action="store_true", help="Output verification results as structured JSON")

    # invariants
    p_invariants = subparsers.add_parser("invariants", help="Enforce architectural and quality invariants")
    inv_subs = p_invariants.add_subparsers(dest="invariants_action", help="Invariants action")
    p_inv_mut = inv_subs.add_parser("verify-mutations", help="Verify mutation testing kill score quality gate per ADR-0009")
    p_inv_mut.add_argument("path", nargs="?", default=None, help="Target module or file to mutate")
    p_inv_mut.add_argument("--path", dest="opt_path", default=None, help="Target module or file to mutate")
    p_inv_mut.add_argument("--threshold", type=float, default=80.0, help="Mutation kill score threshold percentage (default: 80.0)")
    p_inv_mut.add_argument("--bc", dest="target_bc", default="core", help="Target bounded context (default: core)")
    p_inv_mut.add_argument("--json", action="store_true", help="Output mutation results as structured JSON")
    p_inv_mut.add_argument("--force-run", action="store_true", help="Force re-running Mutmut even if previous results exist")

    # watch
    p_watch = subparsers.add_parser("watch", help="Real-time in-memory graph event bus and workspace change watcher")
    p_watch.add_argument("--debounce-ms", type=float, default=250.0, help="Debounce window in milliseconds (default: 250)")
    p_watch.add_argument("--event-stream", action="store_true", help="Emit raw JSON structured event stream")
    p_watch.add_argument("--dir", default=".", help="Target repository directory (default: current directory)")
    p_watch.add_argument("--once", action="store_true", help="Run single watcher scan iteration and exit")
    p_watch.add_argument("--max-iterations", type=int, default=None, help="Maximum number of poll iterations before exit")

    return parser
