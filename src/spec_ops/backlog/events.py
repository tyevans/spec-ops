"""Domain events for the Backlog Bounded Context."""

from __future__ import annotations

from uuid import UUID
from eventsource import DomainEvent, register_event


@register_event
class TaskProposed(DomainEvent):
    """Emitted when a new task is drafted/proposed."""
    aggregate_type: str = "Task"
    task_id: str
    title: str
    body: str = ""
    dependencies: list[str] = []
    governing_adrs: list[str] = []
    governing_prds: list[str] = []
    governing_stories: list[str] = []
    target_bc: str = "core"


@register_event
class TaskRefined(DomainEvent):
    """Emitted when a task is refined and meets the Definition of Ready."""
    aggregate_type: str = "Task"
    task_id: str


@register_event
class TaskClaimed(DomainEvent):
    """Emitted when an autonomous worker claims a task in a dedicated worktree."""
    aggregate_type: str = "Task"
    task_id: str
    claimed_by: str
    branch: str = ""


@register_event
class TaskReleased(DomainEvent):
    """Emitted when an autonomous worker unclaims or releases a task back to ready."""
    aggregate_type: str = "Task"
    task_id: str
    reason: str = ""


@register_event
class TaskPreflightRecorded(DomainEvent):
    """Emitted when preflight verification checks run on a task."""
    aggregate_type: str = "Task"
    task_id: str
    success: bool
    logs: str = ""


@register_event
class TaskCompleted(DomainEvent):
    """Emitted when a task passes preflight and is integrated/completed."""
    aggregate_type: str = "Task"
    task_id: str
    commit_hash: str = ""
    pr_url: str = ""
