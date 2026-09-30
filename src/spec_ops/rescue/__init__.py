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
]
