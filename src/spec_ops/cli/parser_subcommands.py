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

