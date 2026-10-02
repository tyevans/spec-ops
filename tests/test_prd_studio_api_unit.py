"""Unit tests for PRD Studio HTTP API router and dispatcher contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.prd.studio_api import dispatch_studio_api_request
from spec_ops.prd.studio_state import PRDStudioStateManager
from spec_ops.scaffold.init import init_project


def test_get_session_state(tmp_path: Path):
    init_project(tmp_path, name="TestApiGet")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    code, res = dispatch_studio_api_request(mgr, "GET", "/api/studio/state")
    assert code == 200
    assert res["success"] is True
    assert "state" in res
    assert res["state"]["stage"] == "idea"


def test_get_prds_list(tmp_path: Path):
    init_project(tmp_path, name="TestApiList")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    code, res = dispatch_studio_api_request(mgr, "GET", "/api/studio/prds")
    assert code == 200
    assert res["success"] is True
    assert "prds" in res
    assert isinstance(res["prds"], list)


def test_get_unknown_endpoint(tmp_path: Path):
    init_project(tmp_path, name="TestApi404")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    code, res = dispatch_studio_api_request(mgr, "GET", "/api/studio/unknown")
    assert code == 404
    assert res["success"] is False


def test_post_new_draft(tmp_path: Path):
    init_project(tmp_path, name="TestApiNew")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    code, res = dispatch_studio_api_request(
        mgr,
        "POST",
        "/api/studio/draft/new",
        payload={
            "title": "New Studio Feature",
            "persona": "Taylor",
            "component": "prd",
            "problem_statement": "Manual YAML errors.",
            "outcomes": ["Zero syntax errors"],
        },
    )
    assert code == 200
    assert res["success"] is True
    assert res["state"]["title"] == "New Studio Feature"
    assert res["state"]["persona"] == "Taylor"
    assert res["state"]["is_valid"] is True


def test_post_update_field_valid_and_invalid(tmp_path: Path):
    init_project(tmp_path, name="TestApiUpdate")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    # Valid update
    code, res = dispatch_studio_api_request(
        mgr,
        "POST",
        "/api/studio/draft/update",
        payload={"field": "title", "value": "Updated Title"},
    )
    assert code == 200
    assert res["state"]["title"] == "Updated Title"

    # Missing field
    code, res = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/update", payload={"value": "No field"}
    )
    assert code == 400

    # Invalid field name
    code, res = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/update", payload={"field": "invalid_xyz", "value": 123}
    )
    assert code == 400


def test_post_outcomes_add_remove_reorder(tmp_path: Path):
    init_project(tmp_path, name="TestApiOutcomes")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Outcomes Demo",
        persona="Jordan",
        problem_statement="Testing outcomes API",
        outcomes=["First", "Second"],
    )

    # Add outcome
    code, res = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/outcome/add", payload={"outcome": "Third"}
    )
    assert code == 200
    assert len(res["state"]["outcomes"]) == 3

    # Reorder
    code, res = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/outcome/reorder", payload={"order": [2, 0, 1]}
    )
    assert code == 200
    assert res["state"]["outcomes"] == ["Third", "First", "Second"]

    # Invalid reorder
    code, res = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/outcome/reorder", payload={"order": [0, 0, 1]}
    )
    assert code == 400

    # Remove outcome
    code, res = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/outcome/remove", payload={"index": 1}
    )
    assert code == 200
    assert res["state"]["outcomes"] == ["Third", "Second"]

    # Invalid remove index
    code, res = dispatch_studio_api_request(
        mgr, "POST", "/api/studio/draft/outcome/remove", payload={"index": 99}
    )
    assert code == 400


def test_post_save_and_load(tmp_path: Path):
    init_project(tmp_path, name="TestApiSaveLoad")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Persisted Feature",
        persona="Alex",
        component="core",
        problem_statement="Persistence problem",
        outcomes=["Saved to idea directory"],
    )

    # Save
    code, res = dispatch_studio_api_request(mgr, "POST", "/api/studio/draft/save")
    assert code == 200
    prd_id = res.get("prd_id")
    assert prd_id is not None

    # Load in new manager via POST
    new_mgr = PRDStudioStateManager(repo_root=tmp_path)
    code, res = dispatch_studio_api_request(
        new_mgr, "POST", "/api/studio/draft/load", payload={"prd_id": prd_id}
    )
    assert code == 200
    assert res["state"]["title"] == "Persisted Feature"

    # Load via GET with query params
    code, res = dispatch_studio_api_request(
        new_mgr, "GET", "/api/studio/draft/load", query_params={"prd_id": [prd_id]}
    )
    assert code == 200

    # Load non-existent
    code, res = dispatch_studio_api_request(
        new_mgr, "POST", "/api/studio/draft/load", payload={"prd_id": "PRD-9999"}
    )
    assert code == 404


def test_method_not_allowed(tmp_path: Path):
    init_project(tmp_path, name="TestApi405")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    code, res = dispatch_studio_api_request(mgr, "PUT", "/api/studio/state")
    assert code == 405
    assert "not allowed" in res["error"]
