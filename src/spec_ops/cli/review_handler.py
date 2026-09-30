"""CLI command handler for review and dual-custody operations."""

from __future__ import annotations

import argparse
import sys

from ..config.models import SpecOpsConfig
from ..security.dual_custody import sign_task_review


def handle_review_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Executes review subcommands including task sign-off."""
    if getattr(args, "review_action", None) == "sign":
        task_id = getattr(args, "task_id", "")
        identity = getattr(args, "identity", "")
        if not task_id or not identity:
            print("❌ Both task_id and --identity are required.", file=sys.stderr)
            return 1

        ok, msg = sign_task_review(task_id, identity, config)
        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            return 1
        print(f"✅ {msg}")
        return 0

    parser.parse_args(["review", "--help"])
    return 0
