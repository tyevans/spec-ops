"""Subparser registration helpers for backlog queue commands."""

from __future__ import annotations

import argparse


def register_queue_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers backlog queue management commands."""
    p_queue = subparsers.add_parser("queue", help="Manage backlog queue and task integration gates")
    queue_subs = p_queue.add_subparsers(dest="queue_action", help="Queue action")

    p_q_next = queue_subs.add_parser("next", help="Inspect next ready, unblocked backlog task")
    p_q_next.add_argument("--json", action="store_true", help="Output next task as structured JSON")

    p_q_claim = queue_subs.add_parser("claim", help="Claim next ready unblocked task or specific task under queue lock")
    p_q_claim.add_argument("task_id", nargs="?", default=None, help="Target task canonical ID (auto-detected if omitted)")
    p_q_claim.add_argument("--auto", action="store_true", help="Claim next ready unblocked task automatically in strict priority order")
    p_q_claim.add_argument("--worker-id", "--claimant", dest="worker_id", default=None, help="Identifier of claiming worker")
    p_q_claim.add_argument("--json", action="store_true", help="Output claimed task metadata as JSON")

    p_q_refine = queue_subs.add_parser("refine", help="Validate Definition of Ready and promote task to refined")
    p_q_refine.add_argument("task_id", help="Canonical task ID (e.g. TASK-0025 or 0025)")

    p_q_comp = queue_subs.add_parser("complete", help="Gate and complete task integration under merge lock")
    p_q_comp.add_argument("task_id", help="Canonical task ID (e.g. TASK-0028 or 0028)")
    p_q_comp.add_argument("--base", default="main", help="Base branch for diff comparison (default: main)")

    p_q_tree = queue_subs.add_parser("tree", help="Display task dependency tree, execution waves, and blockers")
    p_q_tree.add_argument("--task", default=None, help="Focus tree on a specific task canonical ID (e.g. TASK-0054)")
    p_q_tree.add_argument("--direction", choices=["blocks", "blocked-by"], default="blocks", help="Tree orientation: 'blocks' (forward execution flow) or 'blocked-by' (prerequisites)")
    p_q_tree.add_argument("--reverse", action="store_true", help="Alias for --direction blocked-by")
    p_q_tree.add_argument("--waves", action="store_true", help="Display execution horizons / delivery waves breakdown")
    p_q_tree.add_argument("--all", action="store_true", help="Include completed tasks in dependency tree output")
    p_q_tree.add_argument("--json", action="store_true", help="Output dependency DAG and waves as structured JSON")

    p_q_block = queue_subs.add_parser("block", help="Mark a task as blocked by an unknown question or impediment")
    p_q_block.add_argument("task_id", help="Canonical task ID (e.g. TASK-0052 or 0052)")
    p_q_block.add_argument("--question", required=True, help="The unanswered question or unknown needing resolution")
    p_q_block.add_argument("--type", default="unknown", choices=["unknown", "spike_needed", "external", "dependency"], help="Type of blocker (default: unknown)")
    p_q_block.add_argument("--spike", action="store_true", help="Automatically scaffold an isolated architectural spike and test harness")
    p_q_block.add_argument("--timebox", default="2h", help="Timebox for the created spike (default: 2h)")
    p_q_block.add_argument("--raised-by", default="", help="Identifier of person or agent raising the blocker")

    p_q_unblock = queue_subs.add_parser("unblock", help="Resolve an unknown/blocker and restore ready/proposed state")
    p_q_unblock.add_argument("task_id", help="Canonical task ID (e.g. TASK-0052 or 0052)")
    p_q_unblock.add_argument("--resolution", required=True, help="Explanation or findings that resolved the blocker")
    p_q_unblock.add_argument("--adr", default=None, help="Governing ADR canonical ID if resolved via ADR (e.g. ADR-0017)")

    p_q_blockers = queue_subs.add_parser("blockers", help="List all currently blocked tasks, open questions, and linked spikes")
    p_q_blockers.add_argument("--json", action="store_true", help="Output blockers summary as JSON")

    p_q_mon = queue_subs.add_parser("monitor", help="Interactive terminal backlog flow monitor and JIT buffer telemetry")
    p_q_mon.add_argument("--once", action="store_true", help="Render dashboard snapshot without interactive loop")

    p_q_doc = queue_subs.add_parser(
        "doctor",
        help="Audit backlog health, dangling dependencies, and index drift with self-healing repair",
    )
    p_q_doc.add_argument("--fix", action="store_true", help="Automatically repair broken dependencies and PRIORITY.md drift")
    p_q_doc.add_argument("--repair", action="store_true", help="Alias for --fix")
    p_q_doc.add_argument("--json", action="store_true", help="Output diagnostic report as structured JSON")
    p_q_doc.add_argument("--dir", default=None, help="Backlog directory path (defaults to docs/project/backlog)")

    p_q_digest = queue_subs.add_parser(
        "digest",
        help="Generate automated daily standup curation digest",
    )
    p_q_digest.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Standup digest serialization format (default: markdown)",
    )
    p_q_digest.add_argument(
        "--window",
        default="24h",
        help="Time window for completed throughput analysis (default: 24h)",
    )

    p_q_reorder = queue_subs.add_parser(
        "reorder",
        help="Deterministic topological backlog re-ordering and multi-criteria priority scoring",
    )
    p_q_reorder.add_argument("--dry-run", action="store_true", help="Preview re-ordering without modifying PRIORITY.md")
    p_q_reorder.add_argument("--topological", action="store_true", help="Enforce strict topological ordering to eliminate priority inversions")
    p_q_reorder.add_argument("--by-weights", action="store_true", help="Apply multi-criteria weighted scoring (milestone, blockers, risk)")
    p_q_reorder.add_argument("--json", action="store_true", help="Output re-ranking results as structured JSON")

    p_q_rec = queue_subs.add_parser(
        "reclaim-stalled",
        help="Automated detection and reclamation of abandoned task claims and stale worker leases",
    )
    p_q_rec.add_argument("--timeout-hours", type=float, default=4.0, help="Inactivity timeout threshold in hours before lease is revoked (default: 4.0)")
    p_q_rec.add_argument("--dry-run", action="store_true", help="Preview reclaimable tasks without modifying disk")
    p_q_rec.add_argument("--json", action="store_true", help="Output reclamation results as structured JSON")
