"""BDD step definitions for US-0119: PRD Lint Public API Contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.lint_api import dispatch_lint_api_request, lint_prd_api
from spec_ops.prd.lint_engine import PRDLintEngine

scenarios("features/us_0119_prd_lint_api.feature")


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    return {"tmp_path": tmp_path, "engine": PRDLintEngine(root_dir=tmp_path)}


@given("a repository initialized with PRD documents")
def init_repo_with_prds(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    doc = """---
id: PRD-0088
title: Test PRD
status: Idea
target_persona: Alex
component: prd
---

# PRD-0088: Test PRD

## Problem Statement
A valid problem statement.

## What good looks like
Verifiable outcomes.

## What this does not do
Does not fail silently.

## Checkable Outcomes
- Execution latency remains under 100ms
"""
    (prd_dir / "prd-0088.md").write_text(doc, encoding="utf-8")


@when(parsers.parse('an API client issues a "{method}" request to "{path}"'))
def issue_get_request(method: str, path: str, bdd_ctx: dict[str, Any]):
    engine: PRDLintEngine = bdd_ctx["engine"]
    code, res = dispatch_lint_api_request(engine, method, path)
    bdd_ctx["status_code"] = code
    bdd_ctx["response"] = res


@then(parsers.parse("the response status code is {code:d}"))
def verify_status_code(code: int, bdd_ctx: dict[str, Any]):
    assert bdd_ctx["status_code"] == code


@then("the response payload contains success status and lint reports")
def verify_get_lint_payload(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["response"]
    assert res.get("success") is True
    assert "reports" in res
    assert len(res["reports"]) >= 1


@given("an in-memory PRD document with subjective outcomes")
def in_memory_subjective_prd(bdd_ctx: dict[str, Any]):
    bdd_ctx["payload"] = {
        "content": """---
id: PRD-0089
title: Fast Interface
status: Idea
target_persona: Alex
component: prd
---

# PRD-0089: Fast Interface

## Problem Statement
System feels slow.

## What good looks like
Fast and intuitive interface.

## What this does not do
Does not bloat code.

## Checkable Outcomes
- The system is ultra fast and intuitive
"""
    }


@when(parsers.parse('an API client issues a "{method}" request to "{path}" with the content payload'))
def issue_post_request(method: str, path: str, bdd_ctx: dict[str, Any]):
    engine: PRDLintEngine = bdd_ctx["engine"]
    payload = bdd_ctx.get("payload", {})
    code, res = dispatch_lint_api_request(engine, method, path, payload=payload)
    bdd_ctx["status_code"] = code
    bdd_ctx["response"] = res


@then("the lint report detects unfalsifiable outcomes with line-level suggestions")
def verify_detected_unfalsifiable(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["response"]
    assert res.get("success") is True
    report = res.get("report", {})
    assert report.get("unfalsifiable_count", 0) >= 1
    diagnostics = report.get("diagnostics", [])
    matching = [d for d in diagnostics if d.get("rule_id") == "PRD-LINT-002"]
    assert len(matching) >= 1
    assert matching[0].get("suggestion") is not None


@given("an in-memory PRD document needing line-level remediation")
def in_memory_prd_remediation(bdd_ctx: dict[str, Any]):
    bdd_ctx["payload"] = {
        "content": """---
id: PRD-0090
title: Intuitive UI
status: Idea
target_persona: Alex
component: prd
---

# PRD-0090: Intuitive UI

## Problem Statement
Need improvement.

## What good looks like
Better UX.

## What this does not do
No regressions.

## Checkable Outcomes
- The page is fast and clean
"""
    }


@when(parsers.parse('an API client issues a "{method}" request to "{path}"'))
def issue_post_remediate(method: str, path: str, bdd_ctx: dict[str, Any]):
    engine: PRDLintEngine = bdd_ctx["engine"]
    payload = bdd_ctx.get("payload", {})
    code, res = dispatch_lint_api_request(engine, method, path, payload=payload)
    bdd_ctx["status_code"] = code
    bdd_ctx["response"] = res


@then("the response provides remediated content with positive applied count")
def verify_remediation_content(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["response"]
    assert res.get("success") is True
    assert res.get("applied_count", 0) >= 1
    remediated = res.get("remediated_content", "")
    assert "fast" not in remediated.lower()


@then("the new lint report shows improved outcome falsifiability")
def verify_new_lint_report(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["response"]
    new_report = res.get("new_report", {})
    assert new_report.get("unfalsifiable_count", 0) == 0
