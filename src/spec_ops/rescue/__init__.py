"""Rescue bounded context: worktree lifecycle, human sandboxing, and zero-pollution pruning."""

from .doctor import DeveloperEnvironmentDoctor
from .lifecycle import (
    cleanup_worktree,
    create_worktree,
    get_worktree_branch,
    init_worktree_environment,
    is_worktree_dirty,
    prune_git_worktrees,
)
from .prune import (
    PruneCandidate,
    calculate_directory_size,
    format_bytes,
    is_prune_candidate,
    prune_worktrees,
    scan_worktree_candidates,
)
from .memory import (
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
from .sandbox import finish_human_worktree, start_human_worktree

__all__ = [
    "DeveloperEnvironmentDoctor",
    "cleanup_worktree",
    "create_worktree",
    "get_worktree_branch",
    "init_worktree_environment",
    "is_worktree_dirty",
    "prune_git_worktrees",
    "PruneCandidate",
    "calculate_directory_size",
    "format_bytes",
    "is_prune_candidate",
    "prune_worktrees",
    "scan_worktree_candidates",
    "start_human_worktree",
    "finish_human_worktree",
    "FailureHistoryEntry",
    "extract_failed_invariants",
    "parse_task_memory",
    "serialize_task_with_memory",
    "append_failure_record",
    "demote_task_to_proposed",
    "synthesize_negative_constraints",
    "format_failure_memory_prompt",
    "reset_worktree_with_memory",
    "benchmark_frontmatter_update",
    "TriageFinding",
    "FileDiffMetric",
    "classify_log_snippet",
    "parse_feedback_diagnostics",
    "analyze_worktree",
    "format_triage_table",
    "get_targeted_recommendation",
    "calculate_file_diff",
    "takeover_task",
    "StepRecord",
    "StepCacheData",
    "run_incremental_rescue_test",
    "clear_step_cache",
    "load_step_cache",
    "save_step_cache",
    "is_step_cache_valid",
    "invalidate_dirty_step_caches",
    "AttemptSummary",
    "HandoverBrief",
    "generate_handover_brief",
    "render_quickstart_cheatsheet",
    "purge_ephemeral_handover_artifacts",
    "assert_handover_excluded_from_staging",
    "assert_handover_excluded_from_git",
    "sanitize_credentials",
    "extract_reproduction_command",
]

from .handover import (
    AttemptSummary,
    HandoverBrief,
    assert_handover_excluded_from_git,
    assert_handover_excluded_from_staging,
    extract_reproduction_command,
    generate_handover_brief,
    purge_ephemeral_handover_artifacts,
    render_quickstart_cheatsheet,
    sanitize_credentials,
)
from .incremental_runner import (
    StepCacheData,
    StepRecord,
    clear_step_cache,
    invalidate_dirty_step_caches,
    is_step_cache_valid,
    load_step_cache,
    run_incremental_rescue_test,
    save_step_cache,
)
from .fast_check import (
    DiagnosticViolation,
    FastCheckResult,
    handle_fast_check_command,
    run_fast_check,
)
from .triage import (
    FileDiffMetric,
    TriageFinding,
    analyze_worktree,
    calculate_file_diff,
    classify_log_snippet,
    format_triage_table,
    get_targeted_recommendation,
    parse_feedback_diagnostics,
    takeover_task,
)

__all__.extend([
    "DiagnosticViolation",
    "FastCheckResult",
    "handle_fast_check_command",
    "run_fast_check",
])

from .salvage import (
    complete_salvage,
    ensure_rescue_branch,
    format_salvage_commit_message,
    get_rescue_branch_name,
    get_staged_files,
    get_untracked_files,
    patch_files,
    patch_task,
    run_curated_preflight,
    salvage_files,
    salvage_task,
)

__all__.extend([
    "complete_salvage",
    "ensure_rescue_branch",
    "format_salvage_commit_message",
    "get_rescue_branch_name",
    "get_staged_files",
    "get_untracked_files",
    "patch_files",
    "patch_task",
    "run_curated_preflight",
    "salvage_files",
    "salvage_task",
])

