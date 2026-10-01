"""Pure Functional Decider Core for Task Lifecycle.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009, ADR-0010; PRD-0001, PRD-0004; US-0030, US-0081.
Target Bounded Context: core. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from eventsource import DomainEvent

from ..backlog.commands import (
    BacklogCommand,
    ClaimTask,
    CompleteTask,
    ProposeTask,
    RecordPreflight,
    RefineTask,
    ReleaseTask,
    task_id_to_uuid,
)
from ..backlog.decider import TaskDecider, TaskState
from ..backlog.events import (
    TaskClaimed,
    TaskCompleted,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
)


def initial_state() -> TaskState:
    """Returns the uninitialized starting state for a task decider."""
    return TaskDecider.initial_state()


def decide(command: BacklogCommand, state: TaskState) -> list[DomainEvent]:
    """Pure decision function validating invariants and emitting domain events."""
    return TaskDecider.decide(command, state)


def evolve(state: TaskState, event: DomainEvent) -> TaskState:
    """Pure state transition fold updating TaskState from a domain event."""
    return TaskDecider.evolve(state, event)


__all__ = [
    "BacklogCommand",
    "ClaimTask",
    "CompleteTask",
    "ProposeTask",
    "RecordPreflight",
    "RefineTask",
    "ReleaseTask",
    "TaskClaimed",
    "TaskCompleted",
    "TaskDecider",
    "TaskPreflightRecorded",
    "TaskProposed",
    "TaskRefined",
    "TaskReleased",
    "TaskState",
    "decide",
    "evolve",
    "initial_state",
    "task_id_to_uuid",
]
