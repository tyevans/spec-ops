"""BDD step definitions for US-0120: PRD Outcome Coverage Public API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.outcome_coverage import PRDOutcomeCoverageEngine
from spec_ops.prd.outcome_coverage_api import dispatch_outcome_coverage_api_request

scenarios("features/us_0120_prd_outcome_coverage_api.feature")


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    return {"tmp_path": tmp_path, "engine": PRDOutcomeCoverageEngine(repo_root=tmp_path)}


@given(parsers.parse('a repository initialized with PRD "{prd_id}" and BDD test suites'))
def repo_with_prd_and_tests(prd_id: str, bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    content = f"""---
id: {prd_id}
title: Discovery Suite
status: Accepted
target_persona: Taylor
---
# {prd_id}
## Checkable Outcomes
- Live PRD Studio
- Quality Linter
- Living UAT Coverage
"""
    (prd_dir / f"{prd_id.lower()}.md").write_text(content, encoding="utf-8")

    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0120.md").write_text(
        f"""---
id: '0120'
title: Coverage Story
governing_prd: {prd_id}
outcome_id: 3
---
Scenario: Living coverage execution
  Given step
""",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_bdd_us0120.py").write_text(
        "# binding for us-0120\ndef test(): pass\n",
        encoding="utf-8",
    )


@when(parsers.parse('an API client queries "{method}" at "{path}" with "{prd_id}"'))
def query_get_endpoint(method: str, path: str, prd_id: str, bdd_ctx: dict[str, Any]):
    engine: PRDOutcomeCoverageEngine = bdd_ctx["engine"]
    code, res = dispatch_outcome_coverage_api_request(
        engine,
        method,
        path,
        query_params={"prd": [prd_id]},
    )
    bdd_ctx["status_code"] = code
    bdd_ctx["response"] = res


@when(parsers.parse('an API client issues a "{method}" to "{path}" with payload for "{prd_id}"'))
def query_post_endpoint(method: str, path: str, prd_id: str, bdd_ctx: dict[str, Any]):
    engine: PRDOutcomeCoverageEngine = bdd_ctx["engine"]
    code, res = dispatch_outcome_coverage_api_request(
        engine,
        method,
        path,
        payload={"prd_id": prd_id},
    )
    bdd_ctx["status_code"] = code
    bdd_ctx["response"] = res


@then(parsers.parse("the response status code is {code:d}"))
def verify_status_code(code: int, bdd_ctx: dict[str, Any]):
    assert bdd_ctx["status_code"] == code


@then("the response payload confirms successful coverage computation with valid metrics")
def verify_get_payload(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["response"]
    assert res.get("success") is True
    assert res.get("total_prds") == 1
    assert "reports" in res
    rep = res["reports"][0]
    assert rep["total_outcomes"] == 3
    assert rep["covered_outcomes"] == 1


@then("the returned report includes checkable outcome breakdown and BDD scenario counts")
def verify_post_payload(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["response"]
    assert res.get("success") is True
    rep = res["reports"][0]
    assert "outcome_items" in rep
    assert len(rep["outcome_items"]) == 3
    assert rep["total_bdd_scenarios"] == 1
