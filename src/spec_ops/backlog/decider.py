"""Pure functional decider aggregate for Task and Backlog lifecycle."""

from __future__ import annotations

from typing import Any
from eventsource import DeciderAggregate, DomainEvent
from pydantic import BaseModel, Field

from .commands import (
    BacklogCommand,
    ClaimTask,
    CompleteTask,
    ProposeTask,
    RecordPreflight,
    RefineTask,
    ReleaseTask,
)
from .events import (
    TaskClaimed,
    TaskCompleted,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
)


class TaskState(BaseModel):
    """Immutable state representation of a Task."""
    task_id: str = ""
    title: str = ""
    body: str = ""
    status: str = "Uninitialized"  # Uninitialized, Proposed, Refined, Claimed, Complete
    dependencies: list[str] = Field(default_factory=list)
    governing_adrs: list[str] = Field(default_factory=list)
    governing_prds: list[str] = Field(default_factory=list)
    governing_stories: list[str] = Field(default_factory=list)
    target_bc: str = "core"
    claimed_by: str = ""
    branch: str = ""
    last_preflight_success: bool | None = None
    commit_hash: str = ""
    pr_url: str = ""


class TaskDecider(DeciderAggregate[TaskState, BacklogCommand]):
    """Pure functional decider governing the task lifecycle in the Backlog context."""
    aggregate_type = "Task"

    @staticmethod
    def initial_state() -> TaskState:
        return TaskState()

    @staticmethod
    def decide(command: BacklogCommand, state: TaskState) -> list[DomainEvent]:
        match command:
            case ProposeTask():
                if state.status != "Uninitialized":
                    raise ValueError(f"Task '{command.task_id}' is already proposed (current status: {state.status})")
                if not command.title.strip():
                    raise ValueError("Task title cannot be empty")
                return [
                    TaskProposed(
                        aggregate_id=command.aggregate_id,
                        task_id=command.task_id,
                        title=command.title.strip(),
                        body=command.body,
                        dependencies=command.dependencies,
                        governing_adrs=command.governing_adrs,
                        governing_prds=command.governing_prds,
                        governing_stories=command.governing_stories,
                        target_bc=command.target_bc,
                    )
                ]

            case RefineTask():
                if state.status == "Uninitialized":
                    raise ValueError(f"Cannot refine non-existent task '{command.task_id}'")
                if state.status == "Complete":
                    raise ValueError(f"Cannot refine already completed task '{command.task_id}'")
                if state.status == "Refined":
                    return []
                return [TaskRefined(aggregate_id=command.aggregate_id, task_id=command.task_id)]

            case ClaimTask():
                if state.status == "Uninitialized":
                    raise ValueError(f"Cannot claim non-existent task '{command.task_id}'")
                if state.status == "Complete":
                    raise ValueError(f"Cannot claim already completed task '{command.task_id}'")
                if state.claimed_by and state.claimed_by != command.claimed_by:
                    raise ValueError(f"Task '{state.task_id}' is already claimed by '{state.claimed_by}'")
                if not command.claimed_by.strip():
                    raise ValueError("claimed_by must be specified")
                return [
                    TaskClaimed(
                        aggregate_id=command.aggregate_id,
                        task_id=command.task_id,
                        claimed_by=command.claimed_by,
                        branch=command.branch,
                    )
                ]

            case ReleaseTask():
                if not state.claimed_by:
                    raise ValueError(f"Task '{state.task_id}' is not claimed")
                return [
                    TaskReleased(
                        aggregate_id=command.aggregate_id,
                        task_id=command.task_id,
                        reason=command.reason,
                    )
                ]

            case RecordPreflight():
                if state.status == "Uninitialized":
                    raise ValueError(f"Cannot record preflight on non-existent task '{command.task_id}'")
                return [
                    TaskPreflightRecorded(
                        aggregate_id=command.aggregate_id,
                        task_id=command.task_id,
                        success=command.success,
                        logs=command.logs,
                    )
                ]

            case CompleteTask():
                if state.status == "Uninitialized":
                    raise ValueError(f"Cannot complete non-existent task '{command.task_id}'")
                if state.status == "Complete":
                    raise ValueError(f"Task '{command.task_id}' is already completed")
                if state.last_preflight_success is False:
                    raise ValueError(f"Cannot complete task '{command.task_id}': preflight checks failed")
                return [
                    TaskCompleted(
                        aggregate_id=command.aggregate_id,
                        task_id=command.task_id,
                        commit_hash=command.commit_hash,
                        pr_url=command.pr_url,
                    )
                ]

            case _:
                raise NotImplementedError(f"Unhandled command type: {type(command).__name__}")

    @staticmethod
    def evolve(state: TaskState, event: DomainEvent) -> TaskState:
        match event:
            case TaskProposed():
                return state.model_copy(
                    update={
                        "task_id": event.task_id,
                        "title": event.title,
                        "body": event.body,
                        "dependencies": event.dependencies,
                        "governing_adrs": event.governing_adrs,
                        "governing_prds": event.governing_prds,
                        "governing_stories": event.governing_stories,
                        "target_bc": event.target_bc,
                        "status": "Proposed",
                    }
                )

            case TaskRefined():
                return state.model_copy(update={"status": "Refined"})

            case TaskClaimed():
                return state.model_copy(
                    update={
                        "status": "Claimed",
                        "claimed_by": event.claimed_by,
                        "branch": event.branch,
                    }
                )

            case TaskReleased():
                return state.model_copy(
                    update={
                        "status": "Refined",
                        "claimed_by": "",
                        "branch": "",
                    }
                )

            case TaskPreflightRecorded():
                return state.model_copy(
                    update={"last_preflight_success": event.success}
                )

            case TaskCompleted():
                return state.model_copy(
                    update={
                        "status": "Complete",
                        "claimed_by": "",
                        "branch": "",
                        "commit_hash": event.commit_hash,
                        "pr_url": event.pr_url,
                    }
                )

            case _:
                return state
