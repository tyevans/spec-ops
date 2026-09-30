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
    p_prof = subparsers.add_parser("profiles", aliases=["profile"], help="Inspect and list architectural profiles and baseline ADRs")
    prof_subs = p_prof.add_subparsers(dest="profile_action", help="Profile action")
    prof_subs.add_parser("list", help="List all available profiles and their baseline ADRs")
    p_prof_apply = prof_subs.add_parser("apply", help="Apply architectural profile to current repository")
    p_prof_apply.add_argument("profile_name", help="Profile name (e.g. security)")
    p_prof_sync = prof_subs.add_parser("sync", help="Synchronize or restore architectural profile artifacts")
    p_prof_sync.add_argument("profile_name", help="Profile name (e.g. security)")
    p_prof_info = prof_subs.add_parser("info", help="Inspect active architectural profile rules and quality preflight commands")
    p_prof_info.add_argument("--json", action="store_true", help="Output active profiles and invariants as structured JSON")

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
    p_health.add_argument("--json", action="store_true", help="Output health inspection results as structured JSON")

    # decompose
    p_decomp = subparsers.add_parser("decompose", help="Analyze AST seams and recommend modular file decomposition")
    p_decomp.add_argument("--suggest", metavar="PATH", help="Analyze target source file AST and suggest cohesive submodule splits")
    p_decomp.add_argument("path", nargs="?", default=None, help="Target file path")

    # stats
    p_stats = subparsers.add_parser("stats", help="Inspect entity counts, graph metrics, and buffer state")
    p_stats.add_argument("--cache", action="store_true", help="Accelerate graph compilation with content-addressed cache")

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

    # prd
    p_prd = subparsers.add_parser("prd", help="PRD management commands")
    prd_subs = p_prd.add_subparsers(dest="prd_action", help="PRD action")

    p_create = prd_subs.add_parser("create", help="Scaffold a new PRD")
    p_create.add_argument("--title", required=True, help="PRD title")
    p_create.add_argument("--persona", default="", help="Target persona")
    p_create.add_argument("--component", default="", help="Owning component / bounded context")
    p_create.add_argument("--summary", default="", help="Brief summary of problem statement")
    p_create.add_argument("--stage", default="accepted", help="Stage (accepted, idea, shaped)")

    p_new = prd_subs.add_parser("new", help="Interactively guide creation of a new PRD draft in idea/")
    p_new.add_argument("--title", help="PRD title")
    p_new.add_argument("--persona", help="Target persona")
    p_new.add_argument("--component", help="Target component / bounded context")
    p_new.add_argument("--friction", help="What the person cannot do today")
    p_new.add_argument("--good", help="What good looks like (core capabilities)")
    p_new.add_argument("--anti-goals", help="What this does not do (scope boundaries)")
    p_new.add_argument("--outcomes", help="Checkable outcomes")
    p_new.add_argument("--non-interactive", action="store_true", help="Do not prompt interactively")

    p_lint = prd_subs.add_parser("lint", help="Lint PRD markdown files for mandatory sections and falsifiable outcomes")
    p_lint.add_argument("path", nargs="?", default=None, help="PRD file or directory to lint (default: all PRDs)")

    p_promote = prd_subs.add_parser("promote", help="Promote PRD through lifecycle stages")
    p_promote.add_argument("prd_id", help="PRD canonical ID (e.g. PRD-0002) or file path")
    p_promote.add_argument("--stage", required=True, choices=["idea", "shaped", "accepted", "shipped"], help="Target stage")

    p_ship = prd_subs.add_parser("ship", help="Archive accepted PRD to shipped upon backlog completion")
    p_ship.add_argument("prd_id", help="PRD canonical ID (e.g. PRD-0001)")

    prd_subs.add_parser("audit", help="Audit PRD decomposition state and buffer readiness")

    p_decompose = prd_subs.add_parser("decompose", help="Decompose a PRD into vertical slices and stories")
    p_decompose.add_argument("prd_id", help="PRD canonical identifier (e.g. PRD-0001 or 0001)")
    p_decompose.add_argument("--no-spike", action="store_true", help="Omit initial architectural spike")
    p_decompose.add_argument("--by-outcomes", action="store_true", help="Decompose each checkable outcome into a dedicated BDD user story and tasks")
    p_decompose.add_argument("--diff", action="store_true", help="Perform non-destructive delta decomposition for new or modified outcomes")

    p_studio = prd_subs.add_parser("studio", help="Run interactive Web PRD Studio and Low-Code Story Assistant")
    p_studio.add_argument("--open", action="store_true", help="Automatically open browser")
    p_studio.add_argument("--port", type=int, default=8787, help="Server port (default: 8787)")
    p_studio.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")

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
    p_worker.add_argument("action_or_task", nargs="?", default=None, help="Action ('execute', 'claim') or target task canonical ID (e.g. TASK-0009)")
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
    p_rescue.add_argument("task_id", nargs="?", help="Target task canonical ID (e.g. TASK-0011 or 0011)")
    p_rescue.add_argument("--list", action="store_true", help="List all active/stalled worktrees")
    p_rescue.add_argument("--complete", action="store_true", help="Verify preflight and merge rescued worktree into main")
    p_rescue.add_argument("--discard", action="store_true", help="Discard worktree and branch")
    p_rescue.add_argument("--prune", action="store_true", help="Prune and clean up all stale/orphaned worktrees")


    # tui
    p_tui = subparsers.add_parser("tui", help="Launch interactive Terminal UI (TUI) dashboard")
    p_tui.add_argument("--once", action="store_true", help="Render dashboard snapshot and exit without interactive loop")
    p_tui.add_argument("--view", choices=["overview", "backlog", "tree", "health"], default="overview", help="Initial view to display (default: overview)")

    # queue
    p_queue = subparsers.add_parser("queue", help="Manage backlog queue and task integration gates")
    queue_subs = p_queue.add_subparsers(dest="queue_action", help="Queue action")

    p_q_next = queue_subs.add_parser("next", help="Inspect next ready, unblocked backlog task")
    p_q_next.add_argument("--json", action="store_true", help="Output next task as structured JSON")

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

    return parser
