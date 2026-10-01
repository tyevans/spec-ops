"""Architectural spike: Anti-loop worktree failure memory schema and negative prompt synthesis (US-0089).

Re-exports core failure memory primitives from spec_ops.rescue.memory for backwards compatibility.
"""

from __future__ import annotations

from .memory import (
    DEFAULT_MANDATE,
    INVARIANT_MANDATES,
    FailureHistoryEntry,
    append_failure_record,
    benchmark_frontmatter_update,
    demote_task_to_proposed,
    extract_failed_invariants,
    format_failure_memory_prompt,
    parse_task_memory,
    reset_worktree_with_memory,
    serialize_task_with_memory,
    synthesize_negative_constraints,
)

__all__ = [
    "DEFAULT_MANDATE",
    "INVARIANT_MANDATES",
    "FailureHistoryEntry",
    "append_failure_record",
    "benchmark_frontmatter_update",
    "demote_task_to_proposed",
    "extract_failed_invariants",
    "format_failure_memory_prompt",
    "parse_task_memory",
    "reset_worktree_with_memory",
    "serialize_task_with_memory",
    "synthesize_negative_constraints",
]
