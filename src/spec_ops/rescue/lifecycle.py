"""Git worktree lifecycle management and collision recovery.

Governed by ADR-0007, ADR-0021. Re-exports primitives from core downward.
"""

from __future__ import annotations

from ..core.git_worktree import (
    cleanup_worktree,
    create_worktree,
    get_worktree_branch,
    init_worktree_environment,
    is_worktree_dirty,
    prune_git_worktrees,
    register_default_hook_propagator,
)

try:
    from ..scaffold.native_hooks import propagate_hooks_to_worktree

    register_default_hook_propagator(propagate_hooks_to_worktree)
except Exception:
    pass

__all__ = [
    "cleanup_worktree",
    "create_worktree",
    "get_worktree_branch",
    "init_worktree_environment",
    "is_worktree_dirty",
    "prune_git_worktrees",
]
