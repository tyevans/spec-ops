"""Unit tests for PRDStudioSessionState, PRDSummary, and PRDStudioStateManager."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spec_ops.prd.studio_state import (
    PRDStudioSessionState,
    PRDStudioStateManager,
    PRDSummary,
)
from spec_ops.scaffold.init import init_project


def test_session_state_defaults():
    state = PRDStudioSessionState()
    assert state.session_id.startswith("studio-")
    assert state.stage == "idea"
    assert state.is_dirty is False
    assert state.is_valid is False
    assert state.host == "127.0.0.1"
    assert state.port == 8080


def test_state_manager_init(tmp_path: Path):
    init_project(tmp_path, name="TestInit")
    mgr = PRDStudioStateManager(repo_root=tmp_path, open_browser=True, port=9090)
    assert mgr.state.open_browser is True
    assert mgr.state.port == 9090
    assert mgr.state.is_valid is False
    assert len(mgr.state.validation_errors) > 0


def test_state_manager_new_draft(tmp_path: Path):
    init_project(tmp_path, name="TestNewDraft")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    state = mgr.new_draft(
        title="Web Visualizer Engine",
        persona="Alex",
        component="prd",
        problem_statement="Complex DAGs cannot be visually audited.",
        outcomes=["Running spec-ops visualizer launches dashboard"],
    )
    assert state.title == "Web Visualizer Engine"
    assert state.persona == "Alex"
    assert state.component == "prd"
    assert state.is_dirty is True
    assert state.is_valid is True
    assert len(state.validation_errors) == 0


def test_state_manager_update_fields(tmp_path: Path):
    init_project(tmp_path, name="TestUpdate")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.update_field("title", "New Title")
    assert mgr.state.title == "New Title"

    mgr.update_field("persona", "Jordan")
    assert mgr.state.persona == "Jordan"

    mgr.update_field("component", "core")
    assert mgr.state.component == "core"

    mgr.update_field("problem_statement", "Some problem")
    assert mgr.state.problem_statement == "Some problem"

    mgr.update_field("outcomes", ["Outcome 1", "Outcome 2"])
    assert len(mgr.state.outcomes) == 2

    mgr.update_field("outcomes", "- Outcome 3\n- Outcome 4")
    assert mgr.state.outcomes == ["Outcome 3", "Outcome 4"]

    mgr.update_field("stage", "shaped")
    assert mgr.state.stage == "shaped"

    with pytest.raises(KeyError):
        mgr.update_field("unknown_field", "value")


def test_outcomes_manipulation(tmp_path: Path):
    init_project(tmp_path, name="TestOutcomes")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.add_outcome("Outcome A")
    mgr.add_outcome("Outcome B")
    mgr.add_outcome("Outcome C")
    assert mgr.state.outcomes == ["Outcome A", "Outcome B", "Outcome C"]

    # Reorder
    assert mgr.reorder_outcomes([1, 2, 0]) is True
    assert mgr.state.outcomes == ["Outcome B", "Outcome C", "Outcome A"]

    # Invalid reorder
    assert mgr.reorder_outcomes([0, 0, 1]) is False

    # Remove outcome
    assert mgr.remove_outcome(1) is True
    assert mgr.state.outcomes == ["Outcome B", "Outcome A"]

    # Out-of-bounds remove
    assert mgr.remove_outcome(99) is False


def test_save_and_load_draft(tmp_path: Path):
    init_project(tmp_path, name="TestSaveLoad")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Live Metrics Streamer",
        persona="Taylor",
        component="prd",
        problem_statement="Lack of real-time pipeline telemetry.",
        outcomes=["Streams task lifecycle events over SSE"],
    )
    save_res = mgr.save_draft()
    assert save_res.get("success") is True
    assert mgr.state.active_prd_id is not None
    assert mgr.state.active_file_path is not None
    assert mgr.state.is_dirty is False
    assert mgr.state.last_saved_at is not None

    # Load in a fresh manager
    fresh_mgr = PRDStudioStateManager(repo_root=tmp_path)
    assert fresh_mgr.load_prd(mgr.state.active_prd_id) is True
    assert fresh_mgr.state.title == "Live Metrics Streamer"
    assert fresh_mgr.state.persona == "Taylor"
    assert len(fresh_mgr.state.outcomes) == 1


def test_list_prds_and_stage_promotion(tmp_path: Path):
    init_project(tmp_path, name="TestListPromotion")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="PRD Promotion Candidate",
        persona="Morgan",
        component="core",
        problem_statement="Test promotion.",
        outcomes=["Passes test criteria"],
    )
    mgr.save_draft()

    summaries = mgr.list_prds()
    assert len(summaries) >= 1
    found = [s for s in summaries if s.title == "PRD Promotion Candidate"]
    assert len(found) == 1
    assert found[0].stage == "idea"

    # Promote to shaped
    prom_res = mgr.promote_stage("shaped")
    assert prom_res.get("success") is True
    assert mgr.state.stage == "shaped"
    assert "shaped" in (mgr.state.active_file_path or "")


def test_commit_changes(tmp_path: Path):
    init_project(tmp_path, name="TestCommit")
    # Initialize a git repo in tmp_path
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)

    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Committed Specification",
        persona="Sasha",
        component="prd",
        problem_statement="Problem statement test.",
        outcomes=["Observable verified outcome"],
    )
    commit_res = mgr.commit_changes(commit_message="spec(prd): initial test commit")
    assert commit_res.get("success") is True
    assert mgr.state.last_commit_hash is not None
    assert len(mgr.state.last_commit_hash) > 0


def test_to_dict_serialization(tmp_path: Path):
    init_project(tmp_path, name="TestSerialization")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    data = mgr.to_dict()
    assert isinstance(data, dict)
    assert "session_id" in data
    assert "is_dirty" in data
    assert "validation_errors" in data
