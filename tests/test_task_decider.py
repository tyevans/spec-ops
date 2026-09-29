"""Tests for TaskDecider using eventsource.testing.DeciderScenario."""

from __future__ import annotations

import pytest
from eventsource import DomainCommand, DomainEvent
from eventsource.testing import DeciderScenario
from hypothesis import given, strategies as st

from spec_ops.backlog.commands import (
    BacklogCommand,
    ClaimTask,
    CompleteTask,
    ProposeTask,
    RecordPreflight,
    RefineTask,
    ReleaseTask,
    task_id_to_uuid,
)
from spec_ops.backlog.decider import TaskDecider, TaskState
from spec_ops.backlog.events import (
    TaskClaimed,
    TaskCompleted,
    TaskPreflightRecorded,
    TaskProposed,
    TaskRefined,
    TaskReleased,
)


class UnknownCommand(BacklogCommand):
    pass


class UnknownEvent(DomainEvent):
    aggregate_type: str = "Task"


def test_propose_task_success() -> None:
    task_id = "TASK-0100"
    scenario = (
        DeciderScenario(TaskDecider)
        .when(
            ProposeTask(
                task_id=task_id,
                title="Implement Event Sourced Core",
                body="Task details",
                dependencies=["TASK-0099"],
                governing_adrs=["ADR-0010"],
                governing_prds=["PRD-0001"],
                governing_stories=["US-0001"],
                target_bc="backlog",
            )
        )
        .then_events(TaskProposed)
    )
    event = scenario.events[0]
    assert isinstance(event, TaskProposed)
    assert event.task_id == task_id
    assert event.title == "Implement Event Sourced Core"
    assert event.body == "Task details"
    assert event.dependencies == ["TASK-0099"]
    assert event.governing_adrs == ["ADR-0010"]
    assert event.governing_prds == ["PRD-0001"]
    assert event.governing_stories == ["US-0001"]
    assert event.target_bc == "backlog"


def test_propose_task_rejection_empty_title() -> None:
    task_id = "TASK-0100"
    (
        DeciderScenario(TaskDecider)
        .when(ProposeTask(task_id=task_id, title="   "))
        .then_rejected(ValueError, match="^Task title cannot be empty$")
    )


def test_propose_task_rejection_already_exists() -> None:
    task_id = "TASK-0100"
    uid = task_id_to_uuid(task_id)

    (
        DeciderScenario(TaskDecider)
        .given(TaskProposed(aggregate_id=uid, task_id=task_id, title="Initial"))
        .when(ProposeTask(task_id=task_id, title="Duplicate"))
        .then_rejected(ValueError, match="already proposed")
    )


def test_refine_task_lifecycle() -> None:
    task_id = "TASK-0101"
    uid = task_id_to_uuid(task_id)

    # From proposed -> refined
    (
        DeciderScenario(TaskDecider)
        .given(TaskProposed(aggregate_id=uid, task_id=task_id, title="Feature"))
        .when(RefineTask(task_id=task_id))
        .then_events(TaskRefined)
    )

    # Idempotent refine
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Feature"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
        )
        .when(RefineTask(task_id=task_id))
        .then_events()  # No new events emitted
    )

    # Rejection on uninitialized task
    (
        DeciderScenario(TaskDecider)
        .when(RefineTask(task_id=task_id))
        .then_rejected(ValueError, match="Cannot refine non-existent task")
    )

    # Rejection on completed task
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Feature"),
            TaskCompleted(aggregate_id=uid, task_id=task_id),
        )
        .when(RefineTask(task_id=task_id))
        .then_rejected(ValueError, match="Cannot refine already completed task")
    )


def test_claim_and_release_lifecycle() -> None:
    task_id = "TASK-0102"
    uid = task_id_to_uuid(task_id)

    # Claim refined task
    scenario = (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Worker Task"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
        )
        .when(ClaimTask(task_id=task_id, claimed_by="agent-alpha", branch="feat/0102"))
        .then_events(TaskClaimed)
    )
    event = scenario.events[0]
    assert isinstance(event, TaskClaimed)
    assert event.claimed_by == "agent-alpha"
    assert event.branch == "feat/0102"

    # Conflict when already claimed by another agent
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Worker Task"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
            TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="agent-alpha"),
        )
        .when(ClaimTask(task_id=task_id, claimed_by="agent-beta"))
        .then_rejected(ValueError, match="already claimed by 'agent-alpha'")
    )

    # Rejection when claimed_by is empty
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Worker Task"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
        )
        .when(ClaimTask(task_id=task_id, claimed_by="  "))
        .then_rejected(ValueError, match="claimed_by must be specified")
    )

    # Rejection on uninitialized task
    (
        DeciderScenario(TaskDecider)
        .when(ClaimTask(task_id=task_id, claimed_by="agent-alpha"))
        .then_rejected(ValueError, match="Cannot claim non-existent task")
    )

    # Rejection on complete task
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Worker Task"),
            TaskCompleted(aggregate_id=uid, task_id=task_id),
        )
        .when(ClaimTask(task_id=task_id, claimed_by="agent-alpha"))
        .then_rejected(ValueError, match="Cannot claim already completed task")
    )

    # Release task back to ready
    scenario = (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Worker Task"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
            TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="agent-alpha"),
        )
        .when(ReleaseTask(task_id=task_id, reason="Worktree preflight error"))
        .then_events(TaskReleased)
    )
    rel_event = scenario.events[0]
    assert isinstance(rel_event, TaskReleased)
    assert rel_event.reason == "Worktree preflight error"

    # Rejection on releasing unclaimed task
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Worker Task"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
        )
        .when(ReleaseTask(task_id=task_id))
        .then_rejected(ValueError, match="not claimed")
    )


def test_preflight_and_completion_invariants() -> None:
    task_id = "TASK-0103"
    uid = task_id_to_uuid(task_id)

    # Record preflight rejection on uninitialized
    (
        DeciderScenario(TaskDecider)
        .when(RecordPreflight(task_id=task_id, success=True))
        .then_rejected(ValueError, match="Cannot record preflight on non-existent task")
    )

    # Successful preflight allows completion
    scenario = (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Complete Me"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
            TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="agent-alpha"),
            TaskPreflightRecorded(aggregate_id=uid, task_id=task_id, success=True, logs="All pass"),
        )
        .when(CompleteTask(task_id=task_id, commit_hash="abcdef123456", pr_url="https://github.com/pr/1"))
        .then_events(TaskCompleted)
    )
    comp_event = scenario.events[0]
    assert isinstance(comp_event, TaskCompleted)
    assert comp_event.commit_hash == "abcdef123456"
    assert comp_event.pr_url == "https://github.com/pr/1"

    # Failed preflight blocks completion
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Complete Me"),
            TaskRefined(aggregate_id=uid, task_id=task_id),
            TaskClaimed(aggregate_id=uid, task_id=task_id, claimed_by="agent-alpha"),
            TaskPreflightRecorded(aggregate_id=uid, task_id=task_id, success=False, logs="Test failed"),
        )
        .when(CompleteTask(task_id=task_id, commit_hash="abcdef123456"))
        .then_rejected(ValueError, match="preflight checks failed")
    )

    # Completion on uninitialized task fails
    (
        DeciderScenario(TaskDecider)
        .when(CompleteTask(task_id=task_id))
        .then_rejected(ValueError, match="Cannot complete non-existent task")
    )

    # Completion on already completed task fails
    (
        DeciderScenario(TaskDecider)
        .given(
            TaskProposed(aggregate_id=uid, task_id=task_id, title="Complete Me"),
            TaskCompleted(aggregate_id=uid, task_id=task_id),
        )
        .when(CompleteTask(task_id=task_id))
        .then_rejected(ValueError, match="already completed")
    )


def test_unhandled_command_raises_not_implemented() -> None:
    task_id = "TASK-0104"
    uid = task_id_to_uuid(task_id)
    (
        DeciderScenario(TaskDecider)
        .when(UnknownCommand(task_id=task_id))
        .then_rejected(NotImplementedError, match="Unhandled command type")
    )


def test_evolve_unknown_event_leaves_state_intact() -> None:
    state = TaskState(task_id="TASK-0105", title="Test", status="Proposed")
    new_state = TaskDecider.evolve(state, UnknownEvent(aggregate_id=task_id_to_uuid("TASK-0105")))
    assert new_state == state


@given(
    task_num=st.integers(min_value=1, max_value=9999),
    title=st.text(min_size=1, max_size=50).filter(lambda s: bool(s.strip())),
)
def test_hypothesis_task_lifecycle_property(task_num: int, title: str) -> None:
    task_id = f"TASK-{task_num:04d}"
    uid = task_id_to_uuid(task_id)

    state = TaskDecider.initial_state()
    assert state.status == "Uninitialized"

    # Step 1: Propose
    events = TaskDecider.decide(ProposeTask(task_id=task_id, title=title, body="Detail"), state)
    for e in events:
        state = TaskDecider.evolve(state, e)
    assert state.status == "Proposed"
    assert state.task_id == task_id
    assert state.title == title.strip()
    assert state.body == "Detail"

    # Step 2: Refine
    events = TaskDecider.decide(RefineTask(task_id=task_id), state)
    for e in events:
        state = TaskDecider.evolve(state, e)
    assert state.status == "Refined"

    # Step 3: Claim
    events = TaskDecider.decide(ClaimTask(task_id=task_id, claimed_by="worker-1", branch="b1"), state)
    for e in events:
        state = TaskDecider.evolve(state, e)
    assert state.status == "Claimed"
    assert state.claimed_by == "worker-1"
    assert state.branch == "b1"

    # Step 4: Preflight pass and complete
    events = TaskDecider.decide(RecordPreflight(task_id=task_id, success=True, logs="Pass"), state)
    for e in events:
        state = TaskDecider.evolve(state, e)
    assert state.last_preflight_success is True

    events = TaskDecider.decide(CompleteTask(task_id=task_id, commit_hash="c0ffee", pr_url="pr1"), state)
    for e in events:
        state = TaskDecider.evolve(state, e)
    assert state.status == "Complete"
    assert state.claimed_by == ""
    assert state.branch == ""
    assert state.commit_hash == "c0ffee"
    assert state.pr_url == "pr1"
