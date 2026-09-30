"""CLI command handler for schema validation and migration."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.migration import migrate_specifications
from ..core.schema_validator import SCHEMA_VERSION, validate_specifications


def handle_schema_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Dispatches schema validation and migration CLI commands."""
    action = getattr(args, "schema_action", None)
    if not action:
        print("Usage: spec-ops schema {check,validate,migrate} [options]")
        return 0

    raw_path = getattr(args, "opt_path", None) or getattr(args, "path", None)
    target = Path(raw_path).resolve() if raw_path else None

    if action in ("check", "validate"):
        is_valid, errors, _ = validate_specifications(config.root_dir, target_path=target)
        if is_valid:
            print(f"Schema Check Passed: All specification documents conform to schema {SCHEMA_VERSION}")
            return 0

        print(f"❌ Schema Validation Failed: {len(errors)} error(s) detected in specification documents:\n")
        for err in errors:
            print(err.format_error())
            print()
        return 1

    if action == "migrate":
        in_place = getattr(args, "in_place", False)
        mod_count, diff_text, mod_files = migrate_specifications(
            config.root_dir, target_path=target, in_place=in_place
        )

        if mod_count == 0:
            print(f"✨ All specification documents conform to schema {SCHEMA_VERSION}. No migrations required.")
            return 0

        if in_place:
            print(f"✨ Successfully migrated {mod_count} specification document(s) in-place to schema {SCHEMA_VERSION}:")
            for f in mod_files:
                try:
                    rel = f.relative_to(config.root_dir)
                except ValueError:
                    rel = f
                print(f"   ✓ {rel}")
            return 0

        # Dry-run migration
        if diff_text:
            print(diff_text, end="")
        return 0

    return 0
