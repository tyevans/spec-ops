"""BDD step definitions for US-0118: PRD Studio Public API Dispatch Contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.studio_api import dispatch_studio_api_request
from spec_ops.prd.studio_state import PRDStudioStateManager
from spec_ops.scaffold.init import init_project

scenarios("features/us_0118_prd_studio_api.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


@given("an active PRD studio session connected to an initialized project")
def studio_session_ready(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="StudioApiProject")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    bdd_ctx["manager"] = mgr
    bdd_ctx["tmp_path"] = tmp_path


@when(parsers.parse('an HTTP GET request is dispatched to "{path}"'))
def dispatch_get_step(path: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    code, res = dispatch_studio_api_request(mgr, "GET", path)
    bdd_ctx["last_code"] = code
    bdd_ctx["last_res"] = res


@then("the response status is 200 and returns the active session state")
def verify_get_state_200(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["last_code"] == 200
    res = bdd_ctx["last_res"]
    assert res.get("success") is True
    assert "state" in res
    assert "session_id" in res["state"]


@then("the response status is 200 and lists available PRDs.")
def verify_get_prds_200(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["last_code"] == 200
    res = bdd_ctx["last_res"]
    assert res.get("success") is True
    assert "prds" in res
    assert isinstance(res["prds"], list)


@when(
    parsers.parse(
        'an HTTP POST request is dispatched to "{path}" with field "{field}" and value "{val}"'
    )
)
def dispatch_post_update_field(path: str, field: str, val: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    code, res = dispatch_studio_api_request(mgr, "POST", path, payload={"field": field, "value": val})
    bdd_ctx["last_code"] = code
    bdd_ctx["last_res"] = res


@when(
    parsers.parse(
        'an HTTP POST request is dispatched to "{path}" with outcome "{outcome}"'
    )
)
def dispatch_post_outcome_add(path: str, outcome: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    # Provide problem_statement as well to ensure validation passes
    mgr.update_field("problem_statement", "Valid problem statement.")
    code, res = dispatch_studio_api_request(mgr, "POST", path, payload={"outcome": outcome})
    bdd_ctx["last_code"] = code
    bdd_ctx["last_res"] = res


@then("the response status is 200 and the draft is marked valid")
def verify_draft_valid(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["last_code"] == 200
    res = bdd_ctx["last_res"]
    assert res.get("is_valid") is True
    assert res["state"]["is_valid"] is True


@when(parsers.parse('an HTTP POST request is dispatched to "{path}"'))
def dispatch_post_plain(path: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    code, res = dispatch_studio_api_request(mgr, "POST", path, payload={})
    bdd_ctx["last_code"] = code
    bdd_ctx["last_res"] = res


@then("the response status is 200 and the draft file path is returned.")
def verify_save_success(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["last_code"] == 200
    res = bdd_ctx["last_res"]
    assert res.get("success") is True
    assert "file_path" in res


@given("a PRD draft populated with 3 checkable outcomes")
def draft_with_three_outcomes(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="OutcomesApiProject")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Sample PRD",
        persona="Jordan",
        problem_statement="Problem statement",
        outcomes=["Outcome One", "Outcome Two", "Outcome Three"],
    )
    bdd_ctx["manager"] = mgr


@when(
    parsers.parse(
        'an HTTP POST request is dispatched to "{path}" with order {order}'
    )
)
def dispatch_post_reorder(path: str, order: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    order_list = json.loads(order)
    code, res = dispatch_studio_api_request(mgr, "POST", path, payload={"order": order_list})
    bdd_ctx["last_code"] = code
    bdd_ctx["last_res"] = res


@then("the response status is 200 and the outcomes are reversed")
def verify_reordered_outcomes(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["last_code"] == 200
    res = bdd_ctx["last_res"]
    assert res["state"]["outcomes"] == ["Outcome Three", "Outcome Two", "Outcome One"]


@when(
    parsers.parse(
        'an HTTP POST request is dispatched to "{path}" with index {index:d}'
    )
)
def dispatch_post_remove(path: str, index: int, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    code, res = dispatch_studio_api_request(mgr, "POST", path, payload={"index": index})
    bdd_ctx["last_code"] = code
    bdd_ctx["last_res"] = res


@then("the response status is 200 and 2 outcomes remain.")
def verify_outcomes_count_reduced(bdd_ctx: dict[str, Any]):
    assert bdd_ctx["last_code"] == 200
    res = bdd_ctx["last_res"]
    assert len(res["state"]["outcomes"]) == 2
