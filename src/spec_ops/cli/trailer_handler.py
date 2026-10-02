"""CLI command handler for spec-ops security check-trailers command."""

from __future__ import annotations

import argparse
import json
import sys

from ..config.models import SpecOpsConfig
from ..security.trailer_sanitizer import TrailerSanitizer


def handle_check_trailers_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Dispatches 'spec-ops security check-trailers' execution."""
    rev_range = getattr(args, "rev_range", "main..HEAD") or "main..HEAD"
    strict = getattr(args, "strict", False)
    as_json = getattr(args, "json", False)

    sanitizer = TrailerSanitizer(root_dir=config.root_dir, strict=strict)
    all_valid, results = sanitizer.validate_range(rev_range)

    if as_json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return 0 if all_valid else 1

    print(f"=== Conventional Commit & RFC-822 Trailer Verification ({rev_range}) ===")
    print(f"Total Commits: {len(results)}")

    if not results:
        print("⚠️  No commits found in specified revision range.")
        return 0

    valid_count = sum(1 for r in results if r.is_valid)
    print(f"Compliant:     {valid_count}/{len(results)}")

    for r in results:
        status_icon = "✅" if r.is_valid else "❌"
        print(f"\n{status_icon} Commit {r.commit_hash}: {r.subject}")
        if r.trailers:
            trailer_str = ", ".join(f"{k}={v}" for k, v in r.trailers.items())
            print(f"   Trailers: {trailer_str}")
        if r.missing_trailers:
            print(f"   Missing:  {', '.join(r.missing_trailers)}")
        if r.errors:
            for err in r.errors:
                print(f"   Error:    {err}", file=sys.stderr)
        if r.warnings:
            for warn in r.warnings:
                print(f"   Warning:  {warn}")

    if all_valid:
        print("\n✨ All commits comply with Conventional Commits and RFC-822 trailer standards.")
        return 0

    print("\n❌ Commit trailer verification failed. Correct formatting or supply required trailers.", file=sys.stderr)
    return 1
