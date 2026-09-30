"""CLI export handler for executive roadmap and stakeholder presentation assets."""

from __future__ import annotations

import argparse

from ..config.models import SpecOpsConfig
from ..prd.exporter import export_roadmap


def handle_export_command(args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser) -> int:
    """Dispatches export subcommands."""
    action = getattr(args, "export_action", None)
    if action == "roadmap" or action is None:
        fmt = getattr(args, "format", "svg") or "svg"
        out_path = getattr(args, "output", None)
        audience = getattr(args, "audience", "Leadership / Non-Technical") or "Leadership / Non-Technical"
        granularity = getattr(args, "granularity", "Milestones & PRD Outcomes") or "Milestones & PRD Outcomes"

        dest = export_roadmap(config, format=fmt, output_path=out_path, audience=audience, granularity=granularity)
        print(f"✅ Exported executive roadmap to {dest}")
        return 0

    parser.parse_args(["export", "--help"])
    return 0
