"""Subparser registration helpers for SpecOps CLI."""

from __future__ import annotations

import argparse


def register_prd_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers PRD lifecycle commands."""
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

    p_audit_prd = prd_subs.add_parser("audit", help="Audit PRD decomposition state and buffer readiness")
    p_audit_prd.add_argument("prd_id", nargs="?", default=None, help="PRD canonical identifier (e.g. PRD-0001)")
    p_audit_prd.add_argument("--deep", action="store_true", help="Perform continuous deep outcome coverage audit")

    p_decompose = prd_subs.add_parser("decompose", help="Decompose a PRD into vertical slices and stories")
    p_decompose.add_argument("prd_id", help="PRD canonical identifier (e.g. PRD-0001 or 0001)")
    p_decompose.add_argument("--no-spike", action="store_true", help="Omit initial architectural spike")
    p_decompose.add_argument("--by-outcomes", action="store_true", help="Decompose each checkable outcome into a dedicated BDD user story and tasks")
    p_decompose.add_argument("--diff", action="store_true", help="Perform non-destructive delta decomposition for new or modified outcomes")

    p_studio = prd_subs.add_parser("studio", help="Run interactive Web PRD Studio and Low-Code Story Assistant")
    p_studio.add_argument("--open", action="store_true", help="Automatically open browser")
    p_studio.add_argument("--port", type=int, default=8787, help="Server port (default: 8787)")
    p_studio.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")


def register_profile_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers architectural profile commands."""
    p_prof = subparsers.add_parser("profiles", aliases=["profile"], help="Inspect and list architectural profiles and baseline ADRs")
    prof_subs = p_prof.add_subparsers(dest="profile_action", help="Profile action")
    prof_subs.add_parser("list", help="List all available profiles and their baseline ADRs")

    p_prof_apply = prof_subs.add_parser("apply", help="Apply architectural profile to current repository")
    p_prof_apply.add_argument("profile_name", help="Profile name (e.g. security)")

    p_prof_sync = prof_subs.add_parser("sync", help="Synchronize or restore architectural profile artifacts")
    p_prof_sync.add_argument("profile_name", help="Profile name (e.g. security)")

    p_prof_info = prof_subs.add_parser("info", help="Inspect active architectural profile rules and quality preflight commands")
    p_prof_info.add_argument("--json", action="store_true", help="Output active profiles and invariants as structured JSON")

    for p_name in ("package", "export"):
        p_pkg = prof_subs.add_parser(p_name, help="Package custom profile into distributable bundle (.sop / .tar.gz)")
        p_pkg.add_argument("source", help="Profile directory or name to package")
        p_pkg.add_argument("--out", "--output", dest="output", required=True, help="Destination bundle file path")

    p_prof_inst = prof_subs.add_parser("install", help="Install custom profile bundle into repository")
    p_prof_inst.add_argument("bundle", help="Path to profile bundle archive (.sop or .tar.gz)")

    p_prof_val = prof_subs.add_parser("validate", help="Validate profile manifest and resolve inheritance DAG")
    p_prof_val.add_argument("profile_target", help="Profile directory or name to validate")

    p_prof_insp = prof_subs.add_parser("inspect", help="Inspect resolved profile inheritance, merged ADRs and invariant constraints")
    p_prof_insp.add_argument("profile_target", nargs="?", default=".", help="Profile directory or name to inspect (default: current project)")

    p_prof_diff = prof_subs.add_parser("diff", help="Semantic diff of profile invariant and baseline ADR changes")
    p_prof_diff.add_argument("profile", nargs="?", default=None, help="Target profile or source profile (e.g. core@2.0.0 or specops/base@v2.0)")
    p_prof_diff.add_argument("target", nargs="?", default=None, help="Optional target profile if source profile is specified")
    p_prof_diff.add_argument("--json", action="store_true", help="Output machine-readable semantic diff in JSON format")

    p_prof_up = prof_subs.add_parser("upgrade", help="Upgrade architectural profile version and migrate baseline ADRs")
    p_prof_up.add_argument("profile", nargs="?", default=None, help="Target profile to upgrade to (default: current installed profile)")
    p_prof_up.add_argument("--force", action="store_true", help="Force upgrade and overwrite conflicting local ADR modifications")
    p_prof_up.add_argument("--action", choices=["keep-local", "accept-upstream", "custom", "diff", "abort"], default=None, help="Conflict resolution action")


def register_adr_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers Architectural Decision Record (ADR) lifecycle commands."""
    p_adr = subparsers.add_parser("adr", help="Architectural Decision Record (ADR) lifecycle and supersession")
    adr_subs = p_adr.add_subparsers(dest="adr_action", help="ADR action")

    p_sup = adr_subs.add_parser("supersede", help="Supersede an existing ADR with a new decision")
    p_sup.add_argument("old_id", help="Canonical ID or path of superseded ADR (e.g. ADR-0003)")
    p_sup.add_argument("new_id_pos", nargs="?", default=None, help="Superseding ADR identifier or path")
    p_sup.add_argument("--by", "--with", dest="by", default=None, help="Superseding ADR identifier or path (e.g. ADR-0015)")


def register_graph_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers graph compilation, cycles, pathfinding, and inspection commands."""
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
    p_g_watch = graph_subs.add_parser("watch", help="Real-time in-memory graph event bus and workspace change watcher")
    p_g_watch.add_argument("--debounce-ms", type=float, default=250.0, help="Debounce window in milliseconds (default: 250)")
    p_g_watch.add_argument("--event-stream", action="store_true", help="Emit raw JSON structured event stream")
    p_g_watch.add_argument("--dir", default=".", help="Target repository directory (default: current directory)")
    p_g_watch.add_argument("--once", action="store_true", help="Run single watcher scan iteration and exit")
    p_g_watch.add_argument("--max-iterations", type=int, default=None, help="Maximum number of poll iterations before exit")


def register_queue_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers backlog queue management commands."""
    p_queue = subparsers.add_parser("queue", help="Manage backlog queue and task integration gates")
    queue_subs = p_queue.add_subparsers(dest="queue_action", help="Queue action")

    p_q_next = queue_subs.add_parser("next", help="Inspect next ready, unblocked backlog task")
    p_q_next.add_argument("--json", action="store_true", help="Output next task as structured JSON")

    p_q_claim = queue_subs.add_parser("claim", help="Claim next ready unblocked task or specific task under queue lock")
    p_q_claim.add_argument("task_id", nargs="?", default=None, help="Target task canonical ID (auto-detected if omitted)")
    p_q_claim.add_argument("--auto", action="store_true", help="Claim next ready unblocked task automatically in strict priority order")
    p_q_claim.add_argument("--worker-id", "--claimant", dest="worker_id", default=None, help="Identifier of claiming worker")
    p_q_claim.add_argument("--json", action="store_true", help="Output claimed task metadata as JSON")

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

    p_q_doc = queue_subs.add_parser(
        "doctor",
        help="Audit backlog health, dangling dependencies, and index drift with self-healing repair",
    )
    p_q_doc.add_argument("--fix", action="store_true", help="Automatically repair broken dependencies and PRIORITY.md drift")
    p_q_doc.add_argument("--repair", action="store_true", help="Alias for --fix")
    p_q_doc.add_argument("--json", action="store_true", help="Output diagnostic report as structured JSON")
    p_q_doc.add_argument("--dir", default=None, help="Backlog directory path (defaults to docs/project/backlog)")


def register_spike_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers architectural spike lifecycle commands."""
    p_spike = subparsers.add_parser("spike", help="Governed architectural spike lifecycle, sandboxing, and empirical ADR synthesis")
    spike_subs = p_spike.add_subparsers(dest="spike_action", help="Spike action")

    p_spk_create = spike_subs.add_parser("create", help="Author a new architectural spike task and isolated test harness")
    p_spk_create.add_argument("--name", required=True, help="Spike descriptive name / topic")
    p_spk_create.add_argument("--question", required=True, help="Unanswered question or hypothesis statement to validate")
    p_spk_create.add_argument("--timebox", default="2h", help="Timebox duration (default: 2h)")
    p_spk_create.add_argument("--task", default=None, help="Governing task canonical ID (e.g. TASK-0052)")
    p_spk_create.add_argument("--prd", default=None, help="Governing PRD canonical ID (e.g. PRD-0002)")

    p_spk_start = spike_subs.add_parser("start", help="Instantiate disposable sandboxed spike worktree")
    p_spk_start.add_argument("spike_id", help="Spike canonical identifier (e.g. SPIKE-0002 or 0002)")
    p_spk_start.add_argument("--hypothesis", default=None, help="Hypothesis statement for empirical validation")
    p_spk_start.add_argument("--timebox", default=None, help="Spike timebox duration (e.g. 2h, 4h)")

    p_spk_check = spike_subs.add_parser("check", help="Check spike timebox and write isolation")
    p_spk_check.add_argument("spike_id", nargs="?", default=None, help="Spike identifier (optional if run inside worktree)")
    p_spk_check.add_argument("--elapsed", type=float, default=None, help="Simulated elapsed seconds for testing")

    p_spk_preflight = spike_subs.add_parser("preflight", help="Enforce in-worktree write isolation preflight hook")
    p_spk_preflight.add_argument("spike_id", nargs="?", default=None, help="Spike identifier")

    p_spk_grad = spike_subs.add_parser("graduate", help="Graduate empirical spike findings into an Architectural Decision Record")
    p_spk_grad.add_argument("spike_id", help="Spike canonical identifier (e.g. SPIKE-0002 or 0002)")
    p_spk_grad.add_argument("--result", required=True, choices=["proven", "disproven"], help="Empirical hypothesis validation result")
    p_spk_grad.add_argument("--title", default=None, help="ADR Title")
    p_spk_grad.add_argument("--notes", default=None, help="Empirical observations or rationale")
    p_spk_grad.add_argument("--findings", default=None, help="Recorded benchmark output / findings")
    p_spk_grad.add_argument("--status", default=None, help="ADR status (e.g. Accepted, Proposed)")


def register_audit_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers audit commands (dependencies, export, verify, provenance)."""
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

    p_audit_prov = audit_subs.add_parser(
        "provenance",
        aliases=["traceability"],
        help="Audit unbroken commit trailers, SDLC traceability lineage, and contributor provenance",
    )
    p_audit_prov.add_argument("--strict", action="store_true", help="Fail with exit code 1 if any unanchored commits, orphaned tasks, or missing tasks exist")
    p_audit_prov.add_argument("--contributions", action="store_true", help="Break down delivered tasks and merged commits by contributor provenance")
    p_audit_prov.add_argument("--repo", default=".", help="Repository root path (default: current directory)")


def register_test_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers test quality gates, anti-mock audit, and frontdoor verification commands."""
    p_test = subparsers.add_parser("test", help="Test quality gates, anti-mock audit, and frontdoor verification")
    test_subs = p_test.add_subparsers(dest="test_action", help="Test action")

    for name in ("audit-anti-mock", "verify-frontdoors"):
        p_sub = test_subs.add_parser(name, help="Audit test ASTs for prohibited mock backdoors and verify ADR-0003 frontdoor compliance")
        p_sub.add_argument("path", nargs="?", default=None, help="Target test file or directory to scan (default: tests/)")
        p_sub.add_argument("--path", dest="opt_path", default=None, help="Target test file or directory to scan")
        p_sub.add_argument("--strict-mutation", action="store_true", help="Enforce >=80%% Mutmut mutation score invariant")
        p_sub.add_argument("--threshold", type=float, default=80.0, help="Mutation kill score threshold percentage (default: 80.0)")
        p_sub.add_argument("--json", action="store_true", help="Output audit results as structured JSON")

    p_prop = test_subs.add_parser(
        "properties",
        aliases=["invariants"],
        help="Execute Hypothesis generative property invariant verification tests (ADR-0009)",
    )
    p_prop.add_argument("path", nargs="?", default=None, help="Target test file or directory to execute (default: tests/test_hypothesis_properties.py)")
    p_prop.add_argument("--path", dest="opt_path", default=None, help="Target test file or directory to execute")
    p_prop.add_argument("--max-examples", type=int, default=None, help="Maximum number of Hypothesis examples per property")
    p_prop.add_argument("-k", "--filter", dest="filter_expr", default=None, help="Filter property tests by name")
    p_prop.add_argument("--json", action="store_true", help="Output property verification results as structured JSON")

    p_mut = test_subs.add_parser("mutation", help="Run Mutmut mutation testing quality gate on domain modules per ADR-0009")
    p_mut.add_argument("path", nargs="?", default=None, help="Target module or file to mutate")
    p_mut.add_argument("--path", dest="opt_path", default=None, help="Target module or file to mutate")
    p_mut.add_argument("--threshold", type=float, default=80.0, help="Mutation kill score threshold percentage (default: 80.0)")
    p_mut.add_argument("--bc", dest="target_bc", default="core", help="Target bounded context (default: core)")
    p_mut.add_argument("--json", action="store_true", help="Output mutation results as structured JSON")
    p_mut.add_argument("--force-run", action="store_true", help="Force re-running Mutmut even if previous results exist")


def register_schema_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers specification schema validation and migration commands."""
    p_schema = subparsers.add_parser("schema", help="Specification frontmatter schema validation and automated in-place migration")
    schema_subs = p_schema.add_subparsers(dest="schema_action", help="Schema action")

    for name in ("check", "validate"):
        p_chk = schema_subs.add_parser(name, help="Audit specification frontmatter against active Pydantic models")
        p_chk.add_argument("path", nargs="?", default=None, help="Target file or directory to audit (default: docs/project/)")
        p_chk.add_argument("--path", dest="opt_path", default=None, help="Target file or directory to audit")

    p_mig = schema_subs.add_parser("migrate", help="Safely migrate specification frontmatter to current schema")
    p_mig.add_argument("path", nargs="?", default=None, help="Target file or directory to migrate (default: docs/project/)")
    p_mig.add_argument("--path", dest="opt_path", default=None, help="Target file or directory to migrate")
    p_mig.add_argument("--dry-run", action="store_true", default=False, help="Display unified diff of projected transformations without modifying disk")
    p_mig.add_argument("--in-place", action="store_true", default=False, help="Rewrite outdated frontmatter in-place preserving Markdown body byte-for-byte")


def register_export_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers export commands for executive roadmaps and stakeholder presentations."""
    p_exp = subparsers.add_parser("export", help="Export executive roadmaps and stakeholder presentations")
    exp_subs = p_exp.add_subparsers(dest="export_action", help="Export action")

    p_rd = exp_subs.add_parser("roadmap", help="Export executive roadmap vector visual or interactive presentation")
    p_rd.add_argument("--format", choices=["svg", "html"], default="svg", help="Export format (svg, html, default: svg)")
    p_rd.add_argument("-o", "--out", "--output", dest="output", default=None, help="Output file path (default: dist/roadmap.<format>)")
    p_rd.add_argument("--audience", default="Leadership / Non-Technical", help="Target audience (default: Leadership / Non-Technical)")
    p_rd.add_argument("--granularity", default="Milestones & PRD Outcomes", help="Delivery granularity (default: Milestones & PRD Outcomes)")


def register_release_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers release notes and customer-facing changelog commands."""
    p_rel = subparsers.add_parser("release", help="Customer-facing release notes and changelog generation")
    rel_subs = p_rel.add_subparsers(dest="release_action", help="Release action")
    p_notes = rel_subs.add_parser("notes", help="Generate customer-facing release notes")
    p_notes.add_argument("--milestone", required=True, help="Target milestone identifier (e.g. M1, Milestone 1)")
    p_notes.add_argument("--format", choices=["markdown", "html"], default="markdown", help="Output format (markdown, html)")
    p_notes.add_argument("--branded", action="store_true", default=False, help="Include branded styling and visualizer links")
    p_notes.add_argument("-o", "--output", default=None, help="Output file path")


def register_scaffold_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers scaffold commands (agents, docs, ci)."""
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

    p_scaffold_ci = scaffold_subs.add_parser(
        "ci",
        help="Scaffold multi-platform CI/CD quality gate workflows (GitHub Actions, GitLab CI)",
    )
    p_scaffold_ci.add_argument(
        "--platform",
        choices=["github", "gitlab", "all"],
        default="all",
        help="Target CI platform (github, gitlab, all)",
    )
    p_scaffold_ci.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing CI workflow files and update toolchains while preserving custom configurations",
    )
    p_scaffold_ci.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Alias for --force to update existing CI workflow files",
    )
    p_scaffold_ci.add_argument(
        "--matrix",
        help="Comma-separated Python versions for matrix testing (e.g. 3.12,3.13)",
    )

    p_scaffold_hooks = scaffold_subs.add_parser("hooks", help="Scaffold native, zero-dependency git hooks")
    p_scaffold_hooks.add_argument("--force", action="store_true", help="Overwrite existing hooks")
    p_scaffold_hooks.add_argument("--native", action="store_true", default=True, help="Scaffold native POSIX shell git hooks")


