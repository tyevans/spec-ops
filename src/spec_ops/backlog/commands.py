"""Domain commands for the Backlog Bounded Context."""

from __future__ import annotations

import uuid
from uuid import UUID
from eventsource import DomainCommand
from pydantic import Field


def task_id_to_uuid(task_id: str) -> UUID:
    """Deterministically maps a canonical task ID (e.g. TASK-0001) to a UUID."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, task_id.strip().upper())


class BacklogCommand(DomainCommand):
    """Base command targeting a specific task aggregate."""
    task_id: str
    aggregate_id: UUID = Field(default=uuid.UUID(int=0))

    def model_post_init(self, __context: object) -> None:
        super().model_post_init(__context)
        if self.aggregate_id == uuid.UUID(int=0) and self.task_id:
            object.__setattr__(self, "aggregate_id", task_id_to_uuid(self.task_id))


class ProposeTask(BacklogCommand):
    title: str
    body: str = ""
    dependencies: list[str] = Field(default_factory=list)
    governing_adrs: list[str] = Field(default_factory=list)
    governing_prds: list[str] = Field(default_factory=list)
    governing_stories: list[str] = Field(default_factory=list)
    target_bc: str = "core"


class RefineTask(BacklogCommand):
    pass


class ClaimTask(BacklogCommand):
    claimed_by: str
    branch: str = ""


class ReleaseTask(BacklogCommand):
    reason: str = ""


class RecordPreflight(BacklogCommand):
    success: bool
    logs: str = ""


class CompleteTask(BacklogCommand):
    commit_hash: str = ""
    pr_url: str = ""
