"""CLI argument parser for architecture commands."""

from __future__ import annotations

import argparse


def register_architecture_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers 'spec-ops architecture' CLI subcommands."""
    p_arch = subparsers.add_parser(
        "architecture",
        aliases=["arch"],
        help="Audit bounded context seams, layering rules, and cross-context coupling heatmap",
    )
    arch_subs = p_arch.add_subparsers(dest="architecture_action", help="Architecture subcommands")

    p_seams = arch_subs.add_parser("seams", help="Audit bounded context seams and cross-context coupling heatmap")
    p_seams.add_argument("--strict", action="store_true", help="Exit with code 1 if unauthorized cross-context imports exist")
    p_seams.add_argument("--json", action="store_true", help="Output seam audit and coupling matrix as structured JSON")
    p_seams.add_argument(
        "--export-heatmap",
        dest="export_heatmap",
        default=None,
        help="Export cross-context coupling heatmap report to destination path",
    )
