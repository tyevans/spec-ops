"""CLI command handler for architecture commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.seam_auditor import handle_seam_audit


def handle_architecture_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Dispatches 'spec-ops architecture' subcommands."""
    action = getattr(args, "architecture_action", None)
    if action == "seams":
        return handle_seam_audit(
            config,
            strict=getattr(args, "strict", False),
            json_output=getattr(args, "json", False),
            export_heatmap=getattr(args, "export_heatmap", None),
        )

    parser.parse_args(["architecture", "--help"])
    return 0
