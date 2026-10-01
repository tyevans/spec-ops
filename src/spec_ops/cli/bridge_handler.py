"""CLI command handler for issue tracker bridge and backlog import / export."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ..backlog.bridge.exporter import export_backlog_snapshot
from ..backlog.bridge.importer import IssueImporter
from ..config.models import SpecOpsConfig


def handle_bridge_command(
    args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser
) -> int:
    """Dispatches bridge and backlog import/export actions."""
    action = getattr(args, "bridge_action", None) or getattr(args, "backlog_action", None)
    if not action:
        parser.parse_args(["bridge", "--help"])
        return 0

    backlog_dir = config.backlog_dir

    if action == "import":
        source = getattr(args, "source", "auto") or "auto"
        file_arg = getattr(args, "file", None)
        repo_arg = getattr(args, "repo", None)
        label_arg = getattr(args, "label", None)
        target_bc = getattr(args, "target_bc", "core") or "core"

        file_path = Path(file_arg).resolve() if file_arg else None

        importer = IssueImporter(backlog_dir=backlog_dir, config=config)
        try:
            result = importer.import_from_source(
                source=source,
                file_path=file_path,
                repo=repo_arg,
                label=label_arg,
                default_bc=target_bc,
            )
        except Exception as e:
            print(f"❌ Ingestion failed: {e}", file=sys.stderr)
            return 1

        print(f"✅ {result.summary_message}")
        for tid, p in zip(result.task_ids, result.files):
            print(f"   • {tid}: {p.name}")
        return 0

    if action == "export":
        fmt = getattr(args, "format", "markdown") or "markdown"
        out_arg = getattr(args, "output", None) or getattr(args, "out", None)
        out_path = Path(out_arg).resolve() if out_arg else None

        output_str = export_backlog_snapshot(
            backlog_dir=backlog_dir,
            config=config,
            format=fmt,
            output_path=out_path,
        )
        if out_path:
            print(f"✅ Exported backlog snapshot to {out_path}")
        else:
            print(output_str)
        return 0

    return 0
