"""Scaffold CLI subparser registration."""

from __future__ import annotations

import argparse


def register_scaffold_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers scaffold commands (agents, docs, ci, hooks)."""
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

    p_scaffold_skill = scaffold_subs.add_parser(
        "skill",
        help="Package and scaffold universal multi-platform skill bundles across agent platforms",
    )
    p_scaffold_skill.add_argument(
        "--target",
        choices=["antigravity", "claude", "cursor", "all"],
        default="all",
        help="Target agent platform (antigravity, claude, cursor, all; default: all)",
    )
    p_scaffold_skill.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Destination directory for scaffolded skill bundles (default: repository root)",
    )
    p_scaffold_skill.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate skill packaging without writing files to disk",
    )
    p_scaffold_skill.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing skill definitions and rule files",
    )

