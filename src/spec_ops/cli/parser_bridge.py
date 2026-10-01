"""CLI argument parser definitions for bridge and backlog ingestion / export commands."""

from __future__ import annotations

import argparse


def register_bridge_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers 'spec-ops bridge' CLI subcommands."""
    p_bridge = subparsers.add_parser("bridge", help="External issue tracker ingestion bridge and export")
    bridge_subs = p_bridge.add_subparsers(dest="bridge_action", help="Bridge action")

    _add_import_arguments(bridge_subs.add_parser("import", help="Ingest issues from external issue tracker into backlog/proposed/"))
    _add_export_arguments(bridge_subs.add_parser("export", help="Export backlog status snapshot for executive roadmap reviews"))


def register_backlog_bridge_subparsers(backlog_subs: argparse._SubParsersAction) -> None:
    """Registers 'import' and 'export' subcommands under 'spec-ops backlog'."""
    _add_import_arguments(backlog_subs.add_parser("import", help="Ingest issues from external issue tracker into backlog/proposed/"))
    _add_export_arguments(backlog_subs.add_parser("export", help="Export backlog status snapshot for executive roadmap reviews"))


def _add_import_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=["github", "jira", "linear", "auto"],
        default="auto",
        help="External issue tracker provider (github, jira, linear, or auto-detected)",
    )
    parser.add_argument("--file", "-f", default=None, help="Path to exported JSON or CSV issue file")
    parser.add_argument("--repo", "-r", default=None, help="Remote GitHub repository in 'owner/repo' format")
    parser.add_argument("--label", "-l", default=None, help="Filter issues by label (GitHub)")
    parser.add_argument("--bc", "--target-bc", dest="target_bc", default="core", help="Default target bounded context (default: core)")


def _add_export_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Export serialization format (default: markdown)")
    parser.add_argument("-o", "--out", "--output", dest="output", default=None, help="Output destination file path")
