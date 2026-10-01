"""Subparser definition for spec-ops review and review radar commands."""

from __future__ import annotations

import argparse


class FlexibleReviewParser(argparse.ArgumentParser):
    """Subparser for spec-ops review supporting both subcommands (radar) and task ID positional syntax."""

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = []
        if namespace is None:
            namespace = argparse.Namespace()

        first_pos = None
        for a in args:
            if not a.startswith("-"):
                first_pos = a
                break

        if first_pos != "radar":
            sub_action = None
            for act in list(self._actions):
                if isinstance(act, argparse._SubParsersAction):
                    sub_action = act
                    self._actions.remove(act)
                    break

            t1 = self.add_argument("task_or_action", nargs="?", default=None, help="Target task canonical ID (e.g. TASK-0015) or 'sign'")
            t2 = self.add_argument("sign_task_id", nargs="?", default=None, help="Target task ID when using 'sign'")
            try:
                return super().parse_known_args(args, namespace)
            finally:
                self._actions.remove(t1)
                self._actions.remove(t2)
                if sub_action:
                    self._actions.append(sub_action)

        return super().parse_known_args(args, namespace)


def register_review_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers review commands, options, and radar subparser."""
    p_rev = subparsers.add_parser("review", help="Architectural review and dual-custody human sign-offs")
    p_rev.__class__ = FlexibleReviewParser

    p_rev.add_argument("--identity", default=None, help="Authorized reviewer identity or key ID (e.g. 'Riley <riley@example.com>')")
    p_rev.add_argument("--provenance", action="store_true", help="Audit commit provenance trailers and author distinction")

    rev_subs = p_rev.add_subparsers(dest="review_action")
    p_radar = rev_subs.add_parser("radar", help="Cross-context interface auditor and architectural review radar")
    p_radar.add_argument("--json", action="store_true", help="Output review radar results as structured JSON")
    p_radar.add_argument("--bc", help="Target bounded context to audit (default: all)")
