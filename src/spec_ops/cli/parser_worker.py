"""Worker subparser registration for SpecOps CLI."""

from __future__ import annotations

import argparse


class FlexibleWorkerParser(argparse.ArgumentParser):
    """Subparser for spec-ops worker supporting both legacy args and orchestrate subcommand."""

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = []
        if namespace is None:
            namespace = argparse.Namespace()

        if any(isinstance(a, argparse._SubParsersAction) for a in self._actions):
            first_pos = None
            for a in args:
                if not a.startswith("-"):
                    first_pos = a
                    break

            sub_commands = set()
            for act in self._actions:
                if isinstance(act, argparse._SubParsersAction):
                    sub_commands.update(act.choices.keys())

            if first_pos not in sub_commands:
                sub_action = None
                for act in list(self._actions):
                    if isinstance(act, argparse._SubParsersAction):
                        sub_action = act
                        self._actions.remove(act)
                        break

                t1 = self.add_argument("action_or_task", nargs="?", default=None)
                t2 = self.add_argument("task_pos", nargs="?", default=None)
                try:
                    return super().parse_known_args(args, namespace)
                finally:
                    self._actions.remove(t1)
                    self._actions.remove(t2)
                    if sub_action:
                        self._actions.append(sub_action)

        return super().parse_known_args(args, namespace)


def register_worker_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers worker commands, legacy arguments, and orchestrate/rebase subcommands."""
    p_worker = subparsers.add_parser("worker", help="Execute backlog task in isolated worktree")
    p_worker.__class__ = FlexibleWorkerParser

    p_worker.add_argument("--task", help="Target task canonical ID (e.g. TASK-0009)")
    p_worker.add_argument("--auto", action="store_true", help="Claim next ready unblocked task automatically in strict priority order")
    p_worker.add_argument("--drain", action="store_true", help="Continuously drain ready tasks until queue is empty")
    p_worker.add_argument("--max-concurrency", "--max-workers", "--concurrency", dest="max_concurrency", type=int, default=1, help="Maximum number of concurrent workers (default: 1)")
    p_worker.add_argument("--max-tasks", type=int, default=None, help="Maximum number of tasks to execute")
    p_worker.add_argument("--dry-run", action="store_true", help="Generate prompt without invoking agent")
    p_worker.add_argument("--no-merge", action="store_true", help="Do not merge branch to main on completion")
    p_worker.add_argument("--no-review", "--skip-review", dest="no_review", action="store_true", help="Skip architectural review step")
    p_worker.add_argument("--worker-id", "--claimant", dest="worker_id", default=None, help="Worker or claimant identifier")
    p_worker.add_argument("--telemetry", action="store_true", help="Display live autonomous worker fleet telemetry and worktree operations")
    p_worker.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    worker_subs = p_worker.add_subparsers(dest="worker_action", help="Worker subcommands")
    p_orch = worker_subs.add_parser("orchestrate", help="Multi-agent in-worktree execution with peer consultation and AST self-healing")
    p_orch.add_argument("task_pos", nargs="?", default=None, help="Target task canonical ID (e.g. TASK-0114)")
    p_orch.add_argument("--task-id", "--task", dest="task_id", default=None, help="Target task canonical ID (e.g. TASK-0114)")
    p_orch.add_argument("--max-attempts", type=int, default=3, help="Maximum self-healing attempts (default: 3)")
    p_orch.add_argument("--peer-review", "--consultation", dest="peer_review", action="store_true", default=True, help="Enable peer consultation and ADR review before staging (default: True)")
    p_orch.add_argument("--no-peer-review", dest="peer_review", action="store_false", help="Disable peer consultation and ADR review")
    p_orch.add_argument("--dry-run", action="store_true", help="Simulate orchestrator loop without executing agents")
    p_orch.add_argument("--json", action="store_true", help="Output orchestration report as JSON")

    p_rebase = worker_subs.add_parser("rebase", help="Autonomous worktree auto-rebase against main with conflict resolution")
    p_rebase.add_argument("task_pos", nargs="?", default=None, metavar="[task-id]", help="Target task canonical ID (e.g. TASK-0147)")
    p_rebase.add_argument("--abort-on-conflict", action="store_true", default=True, help="Safely abort rebase and generate HANDOVER.md on conflict (default: True)")
    p_rebase.add_argument("--dry-run", action="store_true", help="Simulate rebase without modifying working directory")
    p_rebase.add_argument("--json", action="store_true", help="Output rebase report as JSON")

    p_diag = worker_subs.add_parser("diagnose", help="AST self-healing diagnostic analysis of preflight failures and retry prompt synthesis")
    p_diag.add_argument("--log", dest="log_file", default=None, metavar="LOG", help="Path to preflight failure log file")
    p_diag.add_argument("--text", dest="trace_text", default=None, metavar="TEXT", help="Raw failure traceback or preflight output text")
    p_diag.add_argument("--json", action="store_true", help="Output diagnostic cards as JSON")

