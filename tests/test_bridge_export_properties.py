"""Generative property-based tests for external issue tracker status and commit export sync (TASK-0107, ADR-0009)."""

from __future__ import annotations

import json
from pathlib import Path
import re

from hypothesis import HealthCheck, given, settings, strategies as st
import pytest

from spec_ops.backlog.bridge.exporter import (
    export_tracker_sync,
    extract_task_external_ticket,
    format_sync_comment,
    map_status_to_external,
    normalize_spec_ops_status,
)
from spec_ops.backlog.bridge.models import ExternalStatusMapping, TaskExportItem
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters=("\r", "\n", "\0", "\\")),
    min_size=1,
    max_size=60,
).filter(lambda s: bool(s.strip()))

known_statuses = st.sampled_from([
    "Complete", "completed", "done", "closed", "shipped", "resolved",
    "In-Progress", "in-progress", "in_progress", "active", "claimed", "started", "wip",
    "Review", "in-review", "under-review", "reviewing",
    "Blocked", "impeded", "stalled",
    "Refined", "ready", "selected", "todo", "selected-for-development",
    "Proposed", "draft", "open", "backlog", "new",
])

all_statuses = st.one_of(known_statuses, safe_text)
target_strategy = st.sampled_from(["github", "jira", "linear"])

VALID_GITHUB_STATES = {"closed", "open"}
VALID_JIRA_STATES = {"Done", "In Progress", "In Review", "Blocked", "Selected for Development", "Backlog"}
VALID_LINEAR_STATES = {"Done", "In Progress", "In Review", "Blocked", "Todo", "Backlog"}


@settings(max_examples=50)
@given(status=all_statuses)
def test_hypothesis_normalization_idempotency(status: str) -> None:
    norm1 = normalize_spec_ops_status(status)
    norm2 = normalize_spec_ops_status(norm1)
    assert norm1 == norm2
    assert norm1 in {"Complete", "In-Progress", "Review", "Blocked", "Refined", "Proposed"}


@settings(max_examples=50)
@given(status=all_statuses, target=target_strategy)
def test_hypothesis_status_mapping_idempotency_and_closure(status: str, target: str) -> None:
    mapping1 = map_status_to_external(status, target)
    assert isinstance(mapping1, ExternalStatusMapping)

    # Validate closed domain states per target platform
    if target == "github":
        assert mapping1.target_state in VALID_GITHUB_STATES
    elif target == "jira":
        assert mapping1.target_state in VALID_JIRA_STATES
    elif target == "linear":
        assert mapping1.target_state in VALID_LINEAR_STATES

    # Invariant: Re-mapping the target_state yields the exact same target_state (idempotent state transition)
    mapping2 = map_status_to_external(mapping1.target_state, target)
    assert mapping2.target_state == mapping1.target_state
    assert mapping2.target_status_name == mapping1.target_status_name


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    task_counts=st.tuples(
        st.integers(min_value=1, max_value=4),
        st.integers(min_value=0, max_value=3),
        st.integers(min_value=0, max_value=3),
    ),
    target=target_strategy,
    dry_run=st.booleans(),
)
def test_hypothesis_export_tracker_sync_invariants(
    tmp_path_factory: pytest.TempPathFactory,
    task_counts: tuple[int, int, int],
    target: str,
    dry_run: bool,
) -> None:
    n_comp, n_ref, n_prop = task_counts
    repo = tmp_path_factory.mktemp("hypo_export")
    init_project(repo, name="HypoExport")
    backlog_dir = repo / "docs" / "project" / "backlog"

    complete_dir = backlog_dir / "complete"
    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"
    complete_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)
    proposed_dir.mkdir(parents=True, exist_ok=True)

    idx = 1
    # Complete tasks
    for i in range(n_comp):
        tid = f"TASK-{str(idx).zfill(4)}"
        (complete_dir / f"{str(idx).zfill(4)}-comp.md").write_text(
            f"---\nid: '{str(idx).zfill(4)}'\ntitle: Complete Task {idx}\nstatus: Complete\nexternal_ref: https://tracker.test/issue/{idx}\n---\n",
            encoding="utf-8",
        )
        idx += 1

    # Refined tasks
    for i in range(n_ref):
        tid = f"TASK-{str(idx).zfill(4)}"
        (refined_dir / f"{str(idx).zfill(4)}-ref.md").write_text(
            f"---\nid: '{str(idx).zfill(4)}'\ntitle: Refined Task {idx}\nstatus: Refined\nexternal_ref: #{idx}\n---\n",
            encoding="utf-8",
        )
        idx += 1

    # Proposed tasks
    for i in range(n_prop):
        tid = f"TASK-{str(idx).zfill(4)}"
        (proposed_dir / f"{str(idx).zfill(4)}-prop.md").write_text(
            f"---\nid: '{str(idx).zfill(4)}'\ntitle: Proposed Task {idx}\nstatus: Proposed\n---\n",
            encoding="utf-8",
        )
        idx += 1

    total_expected = n_comp + n_ref + n_prop
    res = export_tracker_sync(
        backlog_dir=backlog_dir,
        target=target,
        sync_status=True,
        dry_run=dry_run,
    )

    # Invariant 1: Total tasks matches task queue size
    assert res.total_tasks == total_expected
    assert len(res.items) == total_expected

    # Invariant 2: When dry_run is True, zero tasks are marked synced
    if dry_run:
        assert res.synced_count == 0
        for item in res.items:
            assert item.synced is False
            assert item.sync_action == "simulated"

    # Invariant 3: JSON output is valid and round-trippable
    json_str = res.to_json()
    parsed = json.loads(json_str)
    assert parsed["target"] == target
    assert parsed["total_tasks"] == total_expected
    assert len(parsed["items"]) == total_expected

    # Invariant 4: Markdown output contains document header and table
    md_str = res.to_markdown()
    assert f"External Issue Tracker Sync Export: {target.capitalize()}" in md_str
    assert "Total Tasks Exported" in md_str
