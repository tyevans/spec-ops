"""CLI command handler for 'spec-ops audit sink'."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.audit_sink import AuditFilter, AuditSinkExporter


def handle_audit_sink_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Executes 'spec-ops audit sink' to export and compress structured audit archives."""
    fmt = getattr(args, "format", "jsonl") or "jsonl"
    default_filename = f"audit-sink.{'sqlite' if fmt == 'sqlite' else 'jsonl'}"
    if getattr(args, "compress", False) and fmt != "sqlite":
        default_filename += ".gz"

    out_arg = getattr(args, "output", None)
    if out_arg:
        output_path = Path(out_arg)
        if not output_path.is_absolute():
            output_path = config.root_dir / output_path
    else:
        output_path = config.root_dir / "dist" / "audit" / default_filename

    db_arg = getattr(args, "db", None)
    if db_arg:
        db_path = Path(db_arg)
        if not db_path.is_absolute():
            db_path = config.root_dir / db_path
    else:
        db_path = config.root_dir / ".specops" / "events.db"

    filter_spec = AuditFilter(
        since=getattr(args, "since", None),
        until=getattr(args, "until", None),
        category=getattr(args, "category", None),
        aggregate_type=getattr(args, "aggregate_type", None),
    )

    compress = getattr(args, "compress", False)
    exporter = AuditSinkExporter(db_path=db_path)

    try:
        count, size_bytes, last_hash = exporter.export(
            output_path=output_path,
            format_type=fmt,
            filter_spec=filter_spec,
            compress=compress,
        )
    except Exception as exc:
        print(f"❌ Failed exporting audit sink: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        summary = {
            "status": "success",
            "format": fmt,
            "exported_records": count,
            "file_size_bytes": size_bytes,
            "output_path": str(output_path),
            "chained_hash": last_hash,
        }
        print(json.dumps(summary, indent=2))
        return 0

    rel_out = output_path.relative_to(config.root_dir) if output_path.is_relative_to(config.root_dir) else output_path
    print(f"✨ Exported {count} structured audit events to {rel_out} ({size_bytes:,} bytes)")
    print(f"   Format:       {fmt.upper()}")
    print(f"   Chained Hash: {last_hash}")
    print("   Status:       OK")
    return 0
