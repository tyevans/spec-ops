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

    p_disc = prd_subs.add_parser("discover", help="Discover and scaffold a new PRD idea draft")
    p_disc.add_argument("--title", help="PRD title")
    p_disc.add_argument("--persona", help="Target persona")
    p_disc.add_argument("--bc", help="Target bounded context / component")
    p_disc.add_argument("--summary", help="Summary of problem statement / customer friction")
    p_disc.add_argument("--non-interactive", action="store_true", help="Do not prompt interactively")

    p_shape = prd_subs.add_parser("shape", help="Shape PRD idea into falsifiable specifications and advance lifecycle stage")
    p_shape.add_argument("pos_id", nargs="?", default=None, help="PRD canonical ID or path")
    p_shape.add_argument("--id", dest="prd_id", default=None, help="PRD canonical ID or path")
    p_shape.add_argument("--outcomes", help="Checkable outcomes (comma-separated, newline-separated, or file path)")
    p_shape.add_argument("--anti-goals", help="Scope boundaries and non-goals")
    p_shape.add_argument("--stage", choices=["shaped", "accepted"], default=None, help="Target lifecycle stage (default: shaped or accepted)")
    p_shape.add_argument("--accept", action="store_true", help="Promote PRD directly to accepted stage")

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

    p_uat = prd_subs.add_parser("uat", help="Customer UAT verification, PM sign-off, and receipt management")
    uat_subs = p_uat.add_subparsers(dest="uat_action", help="UAT action")

    p_status = uat_subs.add_parser("status", help="Display customer UAT readiness matrix and overall delivery percentage")
    p_status.add_argument("--json", action="store_true", help="Output customer UAT readiness matrix as JSON")

    p_sign = uat_subs.add_parser("sign", help="Record PM business acceptance sign-off into docs/project/product/uat-signoff.json")
    p_sign.add_argument("--prd", required=True, help="Target PRD canonical ID (e.g. PRD-0003)")
    p_sign.add_argument("--outcome", required=True, help="PRD checkable outcome ID (e.g. 1)")
    p_sign.add_argument("--reviewer", required=True, help="Reviewer identity (e.g. Taylor <taylor@example.com>)")
    p_sign.add_argument("--notes", default="", help="Business acceptance review notes")
    p_sign.add_argument("--status", choices=["Approved", "Rejected", "Pending"], default="Approved", help="Sign-off status (default: Approved)")

    p_receipt = uat_subs.add_parser("receipt", help="Generate or verify tamper-evident cryptographic Customer UAT receipt")
    p_receipt.add_argument("--prd", default=None, help="Target PRD canonical ID (e.g. PRD-0003)")
    p_receipt.add_argument("--out", default=None, help="Output receipt file path")
    p_receipt.add_argument("--verify", action="store_true", help="Verify cryptographic Customer UAT receipt integrity and git tree digest")


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
    p_g_cyc.add_argument("--resolve", action="store_true", help="Resolve cycles with minimal feedback edge detection")
    p_g_cyc.add_argument("--prune-chokepoints", action="store_true", help="Calculate bottleneck nodes and decoupling seams")

    p_g_sort = graph_subs.add_parser("sort", help="Deterministic topological backlog execution sorting")
    p_g_sort.add_argument("--type", default="task", help="Entity type filter (default: task)")

    p_g_ord = graph_subs.add_parser("order", help="Deterministic topological backlog execution ordering")
    p_g_ord.add_argument("--type", default="task", help="Entity type filter (default: task)")

    p_g_path = graph_subs.add_parser("path", help="Reachability pathfinding and lineage tracing")
    p_g_path.add_argument("--from", dest="from_node", required=True, help="Origin entity ID (e.g. persona:taylor)")
    p_g_path.add_argument("--to", dest="to_node", required=True, help="Destination entity ID (e.g. commit:a1b2c3d)")

    p_g_reach = graph_subs.add_parser("reach", help="Verify reachability between graph entities")
    p_g_reach.add_argument("--source", required=True, help="Source entity ID (e.g. persona:Alex or TASK-0001)")
    p_g_reach.add_argument("--target", required=True, help="Target entity ID (e.g. PRD-0001 or ADR-0010)")
    p_g_reach.add_argument("--json", action="store_true", help="Output reachability result as JSON")

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


from .parser_queue import register_queue_subparsers


class FlexibleRescueParser(argparse.ArgumentParser):
    """Subparser for spec-ops rescue that supports both subcommand and positional task syntax."""

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = []
        if namespace is None:
            namespace = argparse.Namespace()

        if any(isinstance(a, argparse._SubParsersAction) for a in self._actions):
            first_pos = None
            for a in args:
                if not a.startswith("-"):
                    first_pos = a
                    break

            if first_pos != "reset":
                sub_action = None
                for act in list(self._actions):
                    if isinstance(act, argparse._SubParsersAction):
                        sub_action = act
                        self._actions.remove(act)
                        break

                t1 = self.add_argument("task_id", nargs="?", default=None)
                t2 = self.add_argument("target", nargs="?", default=None)
                try:
                    return super().parse_known_args(args, namespace)
                finally:
                    self._actions.remove(t1)
                    self._actions.remove(t2)
                    if sub_action:
                        self._actions.append(sub_action)

        return super().parse_known_args(args, namespace)


def register_rescue_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers rescue commands, subcommands, and options (US-0089)."""
    p_rescue = subparsers.add_parser("rescue", help="Inspect and recover stalled or failed autonomous worktrees")
    p_rescue.__class__ = FlexibleRescueParser

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

    rescue_subs = p_rescue.add_subparsers(dest="rescue_action", help="Rescue action")
    p_reset = rescue_subs.add_parser("reset", help="Safe worktree discard with anti-loop failure memory and task reset")
    p_reset.add_argument("task_id", help="Target task canonical ID (e.g. TASK-0024)")
    p_reset.add_argument("--reason", default="", help="Failure post-mortem reason description")
    p_reset.add_argument("--demote", action="store_true", help="Demote task to proposed/ on reset")


from .parser_spike import register_spike_subparsers


from .parser_audit import register_audit_subparsers


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
def register_security_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers supply-chain security, verification, and sentinel commands."""
    p_sec = subparsers.add_parser("security", help="Supply-chain security, verification, and sandboxing")
    sec_subs = p_sec.add_subparsers(dest="security_action", help="Security action")
    p_vlock = sec_subs.add_parser("verify-lock", help="Verify supply-chain lockfile cryptographic hashes and pinning")
    p_vlock.add_argument("--path", default=".", help="Directory containing uv.lock (default: current directory)")

    p_sentinel = sec_subs.add_parser("sentinel", help="Inspect and enforce supply-chain lockfile mutation immutability")
    p_sentinel.add_argument("--path", default=".", help="Directory to inspect for lockfile mutations (default: current directory)")
    p_sentinel.add_argument("--fix", action="store_true", help="Automatically revert unauthorized lockfile modifications")
    p_sentinel.add_argument("--json", action="store_true", help="Output sentinel evaluation as structured JSON")

    p_scan = sec_subs.add_parser(
        "scan-secrets",
        help="Scan worktree diffs and source files for high-entropy secrets and credential leaks",
    )
    p_scan.add_argument(
        "--path",
        default=".",
        help="Directory or file path to scan (default: current directory)",
    )
    p_scan.add_argument(
        "--staged",
        action="store_true",
        help="Scan only git staged changes",
    )
    p_scan.add_argument(
        "--threshold",
        type=float,
        default=3.7,
        help="Shannon entropy threshold (default: 3.7)",
    )
    p_scan.add_argument(
        "--json",
        action="store_true",
        help="Output results as structured JSON",
    )


from .parser_scaffold import register_scaffold_subparsers
from .parser_report import register_report_subparsers


def register_check_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers real-time IDE fast check command (US-0091, TASK-0055)."""
    p_check = subparsers.add_parser("check", help="Sub-second IDE invariant diagnostics and real-time editor feedback")
    p_check.add_argument("--fast", action="store_true", default=False, help="Fast single-file invariant diagnostic check")
    p_check.add_argument("--file", dest="file", default=None, help="Target source file to evaluate")
    p_check.add_argument("positional_file", nargs="?", default=None, help="Target source file to evaluate (positional)")
    p_check.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Diagnostic output format (text, json, sarif; default: text)")

from .parser_milestone import register_milestone_subparsers
from .parser_story import register_story_subparsers
from .parser_worker import register_worker_subparsers

