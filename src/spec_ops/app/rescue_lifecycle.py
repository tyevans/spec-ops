"""Rescue lifecycle application service.

Coordinates worktree rescue, salvage merging, and anti-loop failure resets across
rescue, worker, and backlog bounded contexts. Governed by ADR-0020 and ADR-0021.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig


@dataclass
class RescueResult:
    """Outcome of a human rescue or worktree reset workflow."""

    task_id: str
    success: bool
    message: str
    action: str  # "salvage", "reset", "discard"
    details: dict[str, Any] | None = None


class RescueLifecycleService:
    """Application service coordinating multi-context rescue workflows."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.root_dir = config.root_dir
        self.backlog_dir = config.backlog_dir

    def complete_salvage(
        self,
        task_id: str,
        author: str | None = None,
        rescued_by: str | None = None,
    ) -> RescueResult:
        """Runs preflight verification and merges human-rescued worktree into main."""
        from ..rescue.salvage import complete_salvage

        success, msg = complete_salvage(
            self.config,
            task_id,
            author=author,
            rescued_by=rescued_by,
        )

        return RescueResult(
            task_id=task_id,
            success=success,
            message=msg,
            action="salvage",
        )

    def reset_worktree_with_anti_loop(
        self,
        task_id: str,
        reason: str,
        demote: bool = False,
        failed_invariants: list[str] | None = None,
    ) -> RescueResult:
        """Teardowns failed worktree and appends failure history to task frontmatter per ADR-0020."""
        from ..rescue.memory import reset_worktree_with_memory

        success, msg = reset_worktree_with_memory(
            config=self.config,
            task_id=task_id,
            reason=reason,
            demote=demote,
        )

        return RescueResult(
            task_id=task_id,
            success=success,
            message=msg,
            action="reset",
            details={"demoted": demote, "reason": reason},
        )
