"""BDD step definitions for US-0120: PRD Outcome to BDD Scenario Coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.outcome_coverage import PRDOutcomeCoverageEngine, PRDTestCoverageReport

scenarios("features/us_0120_prd_outcome_coverage.feature")


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    return {"tmp_path": tmp_path, "engine": PRDOutcomeCoverageEngine(repo_root=tmp_path)}


@given(parsers.parse('a repository with PRD "{prd_id}" containing checkable outcomes'))
def repo_with_prd(prd_id: str, bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    content = f"""---
id: {prd_id}
title: Test Discovery PRD
status: Accepted
target_persona: Taylor
component: prd
---

# {prd_id}: Test Discovery PRD

## Problem Statement
Need living outcome verification.

## What good looks like
All outcomes verified.

## What this does not do
Does not guess coverage.

## Checkable Outcomes
- Running spec-ops prd studio --open launches UI
- Running spec-ops prd lint flags unfalsifiable outcomes
- Running spec-ops prd audit computes outcome coverage
"""
    (prd_dir / f"{prd_id.lower()}.md").write_text(content, encoding="utf-8")
    bdd_ctx["prd_id"] = prd_id


@given("user stories linked to each checkable outcome with BDD acceptance scenarios")
def create_linked_stories(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    for outcome_idx in (1, 2, 3):
        story_content = f"""---
id: '011{7 + outcome_idx}'
title: Outcome {outcome_idx} Story
status: Accepted
governing_prd: PRD-0003
outcome_id: {outcome_idx}
target_bc: prd
---

# US-011{7 + outcome_idx}: Outcome {outcome_idx} Story

## Acceptance Criteria
Scenario: Verify Outcome {outcome_idx} execution
  Given the system is ready
  When action occurs
  Then outcome is verified
"""
        (stories_dir / f"us-011{7 + outcome_idx}.md").write_text(story_content, encoding="utf-8")


@given("automated test step bindings covering those scenarios")
def create_test_bindings(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    for outcome_idx in (1, 2, 3):
        test_content = f"""# Test binding for US-011{7 + outcome_idx}
def test_bdd_us011{7 + outcome_idx}_step():
    pass
"""
        (tests_dir / f"test_bdd_us011{7 + outcome_idx}_sample.py").write_text(test_content, encoding="utf-8")


@when(parsers.parse('the outcome coverage engine audits "{prd_id}"'))
def audit_target_prd(prd_id: str, bdd_ctx: dict[str, Any]):
    engine: PRDOutcomeCoverageEngine = bdd_ctx["engine"]
    report = engine.audit_prd(prd_id)
    bdd_ctx["report"] = report


@then("the test coverage report indicates 100 percent outcome coverage")
def verify_full_coverage(bdd_ctx: dict[str, Any]):
    report: PRDTestCoverageReport = bdd_ctx["report"]
    assert report.total_outcomes == 3
    assert report.covered_outcomes == 3
    assert report.outcome_coverage_pct == 100.0
    assert report.is_fully_covered is True


@then("all checkable outcomes are marked as tested and covered")
def verify_all_outcomes_tested(bdd_ctx: dict[str, Any]):
    report: PRDTestCoverageReport = bdd_ctx["report"]
    for item in report.outcome_items:
        assert item.is_covered is True
        assert len(item.test_bindings) > 0


@given("a PRD containing checkable outcomes without any linked BDD scenarios")
def prd_unlinked_outcomes(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    content = """---
id: PRD-0044
title: Untested PRD
status: Idea
target_persona: Alex
---

# PRD-0044: Untested PRD

## Problem Statement
No tests yet.

## What good looks like
Tests to come.

## What this does not do
None.

## Checkable Outcomes
- An outcome without any story
- Another outcome without tests
"""
    (prd_dir / "prd-0044.md").write_text(content, encoding="utf-8")
    bdd_ctx["untested_prd_id"] = "PRD-0044"


@when("the outcome coverage engine audits the PRD")
def audit_untested_prd(bdd_ctx: dict[str, Any]):
    engine: PRDOutcomeCoverageEngine = bdd_ctx["engine"]
    report = engine.audit_prd(bdd_ctx["untested_prd_id"])
    bdd_ctx["untested_report"] = report


@then("the test coverage report identifies the orphaned and untested outcomes")
def verify_untested_outcomes(bdd_ctx: dict[str, Any]):
    report: PRDTestCoverageReport = bdd_ctx["untested_report"]
    assert report.total_outcomes == 2
    assert report.covered_outcomes == 0
    assert report.is_fully_covered is False
    for item in report.outcome_items:
        assert item.is_covered is False


@then("the outcome coverage percentage reflects the missing test bindings")
def verify_zero_pct(bdd_ctx: dict[str, Any]):
    report: PRDTestCoverageReport = bdd_ctx["untested_report"]
    assert report.outcome_coverage_pct == 0.0
