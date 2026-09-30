"""CLI argument parser definition for SpecOps."""

from __future__ import annotations

import argparse

from .parser_subcommands import register_prd_subparsers, register_profile_subparsers


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

    # audit
    p_audit_cmd = subparsers.add_parser("audit", help="Audit project dependencies, compliance manifests, and security policies")
    audit_subs = p_audit_cmd.add_subparsers(dest="audit_action", help="Audit action")
    p_audit_deps = audit_subs.add_parser("dependencies", help="Scan dependencies for CVEs and license allowlist compliance")
    p_audit_deps.add_argument("--path", default=".", help="Directory containing dependencies (default: current directory)")
    p_audit_deps.add_argument("--offline", action="store_true", help="Run in air-gapped/offline mode with local cache")

    p_audit_export = audit_subs.add_parser("export", help="Compile and export tamper-evident Merkle compliance audit manifest")
    p_audit_export.add_argument("--standard", default="soc2", help="Compliance standard profile (e.g. soc2, iso27001, hipaa)")
    p_audit_export.add_argument("--output", default="dist/compliance/", help="Output directory for compliance manifest and root hash")

    p_audit_verify = audit_subs.add_parser("verify", help="Verify cryptographic compliance manifest integrity and SDLC traceability")
    p_audit_verify.add_argument("--manifest", default="dist/compliance/soc2-audit-manifest.json", help="Path to compliance manifest JSON")
    p_audit_verify.add_argument("--repo", default=".", help="Path to repository root (default: current directory)")

    # profiles
    register_profile_subparsers(subparsers)

    # scaffold
    p_scaffold = subparsers.add_parser("scaffold", help="Scaffold or regenerate project components")
    scaffold_subs = p_scaffold.add_subparsers(dest="scaffold_action", help="Scaffolding action")
    scaffold_subs.add_parser("agents", help="Regenerate AGENTS.md constitution from installed profiles")

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
    p_graph = subparsers.add_parser("graph", help="Relational graph operations and compilation")
    graph_subs = p_graph.add_subparsers(dest="graph_action", help="Graph action")
    p_g_comp = graph_subs.add_parser("compile", help="Compile repository relational knowledge graph")
    p_g_comp.add_argument("--incremental", action="store_true", help="Perform incremental compilation backed by content-addressed cache")
    p_g_comp.add_argument("--json", action="store_true", help="Output compilation result and graph statistics as JSON")
    p_g_comp.add_argument("--force-cold", action="store_true", help="Force a cold compilation rebuild regardless of cache state")

    p_g_cyc = graph_subs.add_parser("cycles", help="Deterministic cycle detection via Tarjan SCC")
    p_g_cyc.add_argument("--format", choices=["text", "json"], default="text", help="Output format (default: text)")
    p_g_cyc.add_argument("--json", action="store_true", help="Output cycles as JSON")

    p_g_sort = graph_subs.add_parser("sort", help="Deterministic topological backlog execution sorting")
    p_g_sort.add_argument("--type", default="task", help="Entity type filter (default: task)")

    p_g_ord = graph_subs.add_parser("order", help="Deterministic topological backlog execution ordering")
    p_g_ord.add_argument("--type", default="task", help="Entity type filter (default: task)")

    p_g_path = graph_subs.add_parser("path", help="Reachability pathfinding and lineage tracing")
    p_g_path.add_argument("--from", dest="from_node", required=True, help="Origin entity ID (e.g. persona:taylor)")
    p_g_path.add_argument("--to", dest="to_node", required=True, help="Destination entity ID (e.g. commit:a1b2c3d)")

    p_g_blast = graph_subs.add_parser("blast-radius", help="Calculate downstream blast radius of entity")
    p_g_blast.add_argument("entity", help="Target entity ID (e.g. ADR-0003)")

    p_g_insp = graph_subs.add_parser("inspect", help="Inspect entity metadata, lineage card, and neighborhood")
    p_g_insp.add_argument("entity", help="Target entity ID (e.g. TASK-0042)")

    graph_subs.add_parser("audit", help="Full bidirectional graph traceability and orphan work item audit")

    # trace
    p_trace = subparsers.add_parser("trace", help="Audit end-to-end bidirectional graph linkages and traceability")
    p_trace.add_argument("--verify", action="store_true", default=True, help="Verify bidirectional graph connectivity and orphan work items")


    # prd
    register_prd_subparsers(subparsers)

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
    p_rescue.add_argument("task_id", nargs="?", help="Target task canonical ID (e.g. TASK-0011, prune, or 0011)")
    p_rescue.add_argument("--list", action="store_true", help="List all active/stalled worktrees")
    p_rescue.add_argument("--complete", action="store_true", help="Verify preflight and merge rescued worktree into main")
    p_rescue.add_argument("--discard", action="store_true", help="Discard worktree and branch")
    p_rescue.add_argument("--prune", action="store_true", help="Prune and clean up all stale/orphaned worktrees")
    p_rescue.add_argument("--dry-run", action="store_true", help="Dry-run preview of candidate worktrees and disk space")

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
    p_queue = subparsers.add_parser("queue", help="Manage backlog queue and task integration gates")
    queue_subs = p_queue.add_subparsers(dest="queue_action", help="Queue action")

    p_q_next = queue_subs.add_parser("next", help="Inspect next ready, unblocked backlog task")
    p_q_next.add_argument("--json", action="store_true", help="Output next task as structured JSON")

    p_q_refine = queue_subs.add_parser("refine", help="Validate Definition of Ready and promote task to refined")
    p_q_refine.add_argument("task_id", help="Canonical task ID (e.g. TASK-0025 or 0025)")

    p_q_comp = queue_subs.add_parser("complete", help="Gate and complete task integration under merge lock")
    p_q_comp.add_argument("task_id", help="Canonical task ID (e.g. TASK-0028 or 0028)")
    p_q_comp.add_argument("--base", default="main", help="Base branch for diff comparison (default: main)")

    p_q_tree = queue_subs.add_parser("tree", help="Display task dependency tree, execution waves, and blockers")
    p_q_tree.add_argument("--task", default=None, help="Focus tree on a specific task canonical ID (e.g. TASK-0054)")
    p_q_tree.add_argument("--direction", choices=["blocks", "blocked-by"], default="blocks", help="Tree orientation: 'blocks' (forward execution flow) or 'blocked-by' (prerequisites)")
    p_q_tree.add_argument("--reverse", action="store_true", help="Alias for --direction blocked-by")
    p_q_tree.add_argument("--waves", action="store_true", help="Display execution horizons / delivery waves breakdown")
    p_q_tree.add_argument("--all", action="store_true", help="Include completed tasks in dependency tree output")
    p_q_tree.add_argument("--json", action="store_true", help="Output dependency DAG and waves as structured JSON")

    p_q_block = queue_subs.add_parser("block", help="Mark a task as blocked by an unknown question or impediment")
    p_q_block.add_argument("task_id", help="Canonical task ID (e.g. TASK-0052 or 0052)")
    p_q_block.add_argument("--question", required=True, help="The unanswered question or unknown needing resolution")
    p_q_block.add_argument("--type", default="unknown", choices=["unknown", "spike_needed", "external", "dependency"], help="Type of blocker (default: unknown)")
    p_q_block.add_argument("--spike", action="store_true", help="Automatically scaffold an isolated architectural spike and test harness")
    p_q_block.add_argument("--timebox", default="2h", help="Timebox for the created spike (default: 2h)")
    p_q_block.add_argument("--raised-by", default="", help="Identifier of person or agent raising the blocker")

    p_q_unblock = queue_subs.add_parser("unblock", help="Resolve an unknown/blocker and restore ready/proposed state")
    p_q_unblock.add_argument("task_id", help="Canonical task ID (e.g. TASK-0052 or 0052)")
    p_q_unblock.add_argument("--resolution", required=True, help="Explanation or findings that resolved the blocker")
    p_q_unblock.add_argument("--adr", default=None, help="Governing ADR canonical ID if resolved via ADR (e.g. ADR-0017)")

    p_q_blockers = queue_subs.add_parser("blockers", help="List all currently blocked tasks, open questions, and linked spikes")
    p_q_blockers.add_argument("--json", action="store_true", help="Output blockers summary as JSON")

    p_q_mon = queue_subs.add_parser("monitor", help="Interactive terminal backlog flow monitor and JIT buffer telemetry")
    p_q_mon.add_argument("--once", action="store_true", help="Render dashboard snapshot without interactive loop")

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
    p_spike = subparsers.add_parser("spike", help="Governed architectural spike lifecycle, sandboxing, and empirical ADR synthesis")
    spike_subs = p_spike.add_subparsers(dest="spike_action", help="Spike action")

    # spike create
    p_spk_create = spike_subs.add_parser("create", help="Author a new architectural spike task and isolated test harness")
    p_spk_create.add_argument("--name", required=True, help="Spike descriptive name / topic")
    p_spk_create.add_argument("--question", required=True, help="Unanswered question or hypothesis statement to validate")
    p_spk_create.add_argument("--timebox", default="2h", help="Timebox duration (default: 2h)")
    p_spk_create.add_argument("--task", default=None, help="Governing task canonical ID (e.g. TASK-0052)")
    p_spk_create.add_argument("--prd", default=None, help="Governing PRD canonical ID (e.g. PRD-0002)")

    # spike start
    p_spk_start = spike_subs.add_parser("start", help="Instantiate disposable sandboxed spike worktree")
    p_spk_start.add_argument("spike_id", help="Spike canonical identifier (e.g. SPIKE-0002 or 0002)")
    p_spk_start.add_argument("--hypothesis", default=None, help="Hypothesis statement for empirical validation")
    p_spk_start.add_argument("--timebox", default=None, help="Spike timebox duration (e.g. 2h, 4h)")

    # spike check
    p_spk_check = spike_subs.add_parser("check", help="Check spike timebox and write isolation")
    p_spk_check.add_argument("spike_id", nargs="?", default=None, help="Spike identifier (optional if run inside worktree)")
    p_spk_check.add_argument("--elapsed", type=float, default=None, help="Simulated elapsed seconds for testing")

    # spike preflight
    p_spk_preflight = spike_subs.add_parser("preflight", help="Enforce in-worktree write isolation preflight hook")
    p_spk_preflight.add_argument("spike_id", nargs="?", default=None, help="Spike identifier")

    # spike graduate
    p_spk_grad = spike_subs.add_parser("graduate", help="Graduate empirical spike findings into an Architectural Decision Record")
    p_spk_grad.add_argument("spike_id", help="Spike canonical identifier (e.g. SPIKE-0002 or 0002)")
    p_spk_grad.add_argument("--result", required=True, choices=["proven", "disproven"], help="Empirical hypothesis validation result")
    p_spk_grad.add_argument("--title", default=None, help="ADR Title")
    p_spk_grad.add_argument("--notes", default=None, help="Empirical observations or rationale")
    p_spk_grad.add_argument("--findings", default=None, help="Recorded benchmark output / findings")
    p_spk_grad.add_argument("--status", default=None, help="ADR status (e.g. Accepted, Proposed)")

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

    return parser
