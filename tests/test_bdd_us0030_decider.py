"""BDD Step Definitions for US-0030: Pure Decider Event-Sourced Kernel and SQLite Audit Ledger.

Governed by ADR-0001, ADR-0003, ADR-0006, ADR-0010; PRD-0001, PRD-0004; US-0030.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog import (
    ProposeTask,
    TaskDecider,
    TaskProposed,
    TaskState,
    task_id_to_uuid,
)
from spec_ops.core.event_store import SQLiteEventLedger

scenarios("features/us_0030_decider.feature")


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    return {}


# Scenario 1: Pure Decider Task State Progression


@given("a TaskDecider initialized with initial empty state")
def task_decider_initial_state(bdd_context: dict[str, Any]) -> None:
    bdd_context["state"] = TaskDecider.initial_state()
    assert bdd_context["state"].status == "Uninitialized"


@when(parsers.parse('the decider receives a ProposeTask command for "{task_id}"'))
def decider_receives_propose_task(bdd_context: dict[str, Any], task_id: str) -> None:
    command = ProposeTask(
        task_id=task_id,
        title="Pure Decider Event-Sourced Kernel and SQLite Audit Ledger",
        body="Implement pure decider and SQLite ledger",
        governing_adrs=["ADR-0010"],
        governing_prds=["PRD-0001"],
        governing_stories=["US-0030"],
        target_bc="core",
    )
    bdd_context["task_id"] = task_id
    bdd_context["command"] = command
    bdd_context["events"] = TaskDecider.decide(command, bdd_context["state"])


@then("a TaskProposed event is produced")
def task_proposed_event_produced(bdd_context: dict[str, Any]) -> None:
    assert len(bdd_context["events"]) == 1
    event = bdd_context["events"][0]
    assert isinstance(event, TaskProposed)
    assert event.task_id == bdd_context["task_id"]


@then(parsers.parse('evolving the state with TaskProposed produces a task with status "{expected_status}"'))
def evolving_state_produces_status(bdd_context: dict[str, Any], expected_status: str) -> None:
    event = bdd_context["events"][0]
    evolved = TaskDecider.evolve(bdd_context["state"], event)
    bdd_context["state"] = evolved
    assert evolved.status == expected_status
    assert evolved.task_id == bdd_context["task_id"]


# Scenario 2: Embedded SQLite Audit Ledger Synchronization


@given("an initialized project repository with SpecOps configuration")
def initialized_project_repo(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    repo = tmp_path / "spec_ops_repo"
    repo.mkdir(parents=True, exist_ok=True)
    backlog_dir = repo / "docs" / "project" / "backlog"
    (backlog_dir / "proposed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "refined").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "complete").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "PRIORITY.md").write_text("# Backlog Priority Queue\n\n", encoding="utf-8")

    bdd_context["repo"] = repo
    bdd_context["backlog_dir"] = backlog_dir
    bdd_context["ledger"] = SQLiteEventLedger(project_root=repo, sync_projection=True)


@when("a task transition event is appended to the event store")
def append_task_transition_event(bdd_context: dict[str, Any]) -> None:
    task_id = "TASK-0132"
    uid = task_id_to_uuid(task_id)
    event = TaskProposed(
        aggregate_id=uid,
        task_id=task_id,
        title="Pure Decider Event-Sourced Kernel and SQLite Audit Ledger",
        body="## Task Details\nPure decider and SQLite audit ledger.\n",
        governing_adrs=["ADR-0010"],
        governing_prds=["PRD-0001", "PRD-0004"],
        governing_stories=["US-0030", "US-0081"],
        target_bc="core",
    )
    bdd_context["task_id"] = task_id
    bdd_context["emitted_event"] = event
    persisted = bdd_context["ledger"].append_events(task_id, [event])
    bdd_context["persisted_events"] = persisted


@then('the event is recorded in ".specops/events.db"')
def event_recorded_in_sqlite(bdd_context: dict[str, Any]) -> None:
    db_file = bdd_context["repo"] / ".specops" / "events.db"
    assert db_file.exists()
    assert db_file.is_file()

    stream = bdd_context["ledger"].get_stream(bdd_context["task_id"])
    assert len(stream) == 1
    assert isinstance(stream[0], TaskProposed)
    assert stream[0].task_id == bdd_context["task_id"]


@then('the corresponding markdown file in "docs/project/backlog/" is synchronized synchronously without data loss')
def markdown_file_synchronized(bdd_context: dict[str, Any]) -> None:
    proposed_dir = bdd_context["backlog_dir"] / "proposed"
    files = list(proposed_dir.glob("*.md"))
    assert len(files) == 1
    task_file = files[0]
    assert "0132" in task_file.name

    content = task_file.read_text(encoding="utf-8")
    assert "id: '0132'" in content or 'id: "0132"' in content or "id: 0132" in content
    assert "status: Proposed" in content
    assert "Pure Decider Event-Sourced Kernel" in content
    assert "ADR-0010" in content

    # Check PRIORITY.md sync
    priority_content = (bdd_context["backlog_dir"] / "PRIORITY.md").read_text(encoding="utf-8")
    assert "TASK-0132 (Proposed)" in priority_content
