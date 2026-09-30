"""Worker bounded context for multi-worker execution, claiming, and merge locking."""

from .claimer import (
    TaskClaimer,
    hydrate_task_prompt,
    initialize_worktree,
    validate_definition_of_ready,
)
from .guardrails import (
    detect_backlog_modifications,
    prepare_guardrailed_commit,
    sanitize_backlog_modifications,
    stage_legitimate_files,
)
from .integration import rebase_with_inference_healing, squash_merge_and_commit
from .merge_lock import MergeLockManager
from .orchestrator import BatchCycleOrchestrator, BatchCycleReport
from .preflight import run_worktree_preflight
from .worktree import cleanup_worktree, create_worktree

__all__ = [
    "BatchCycleOrchestrator",
    "BatchCycleReport",
    "MergeLockManager",
    "TaskClaimer",
    "cleanup_worktree",
    "create_worktree",
    "detect_backlog_modifications",
    "hydrate_task_prompt",
    "initialize_worktree",
    "prepare_guardrailed_commit",
    "rebase_with_inference_healing",
    "run_worktree_preflight",
    "sanitize_backlog_modifications",
    "squash_merge_and_commit",
    "stage_legitimate_files",
    "validate_definition_of_ready",
]
