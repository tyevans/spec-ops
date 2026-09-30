"""CLI command handler for review and dual-custody operations."""

from __future__ import annotations

import argparse
import sys

from ..config.models import SpecOpsConfig
from ..security.dual_custody import sign_task_review
from ..worker.review import generate_review_brief, render_review_brief


def handle_review_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Executes review subcommands including task sign-off and architectural review briefs."""
    action = getattr(args, "task_or_action", None) or getattr(args, "review_action", None)
    if action == "sign":
        task_id = getattr(args, "sign_task_id", None) or getattr(args, "task_id", "")
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

    target_task = action or getattr(args, "task_id", "")
    if not target_task:
        parser.parse_args(["review", "--help"])
        return 0

    provenance = getattr(args, "provenance", False)
    brief = generate_review_brief(target_task, config, provenance=provenance)
    print(render_review_brief(brief, provenance=provenance))
    return 0
