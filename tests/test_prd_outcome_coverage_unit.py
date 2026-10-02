"""Unit tests for PRD outcome to BDD scenario coverage engine and models."""

from __future__ import annotations

from pathlib import Path
import pytest

from spec_ops.prd.outcome_coverage import (
    OutcomeScenarioItem,
    PRDOutcomeCoverageEngine,
    PRDTestCoverageReport,
    _clean_prd_id,
    _clean_story_id,
)


@pytest.fixture
def repo_env(tmp_path: Path):
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0003.md").write_text(
        """---
id: PRD-0003
title: Product Discovery
status: Accepted
target_persona: Taylor
component: prd
---

# PRD-0003: Product Discovery

## Problem Statement
Living UAT.

## What good looks like
Verification.

## What this does not do
None.

## Checkable Outcomes
- First outcome text
- Second outcome text
""",
        encoding="utf-8",
    )

    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0118.md").write_text(
        """---
id: '0118'
title: First outcome story
governing_prd: PRD-0003
outcome_id: 1
---
Scenario: First outcome scenario
  Given step
""",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_bdd_us0118.py").write_text(
        "# binding for us-0118\ndef test(): pass\n",
        encoding="utf-8",
    )
    return tmp_path


def test_clean_id_helpers():
    assert _clean_prd_id("3") == "PRD-0003"
    assert _clean_prd_id("prd-0003") == "PRD-0003"
    assert _clean_story_id("118") == "US-0118"
    assert _clean_story_id("us-0118") == "US-0118"


def test_outcome_scenario_item_serialization():
    item = OutcomeScenarioItem(
        outcome_id=1,
        outcome_text="Deploy feature",
        linked_stories=["US-0001"],
        linked_scenarios=["Scenario 1"],
        test_bindings=["test_bdd_us0001.py"],
        is_covered=True,
    )
    d = item.to_dict()
    assert d["outcome_id"] == 1
    assert d["is_covered"] is True
    assert len(d["linked_stories"]) == 1


def test_prd_test_coverage_report_summary():
    rep = PRDTestCoverageReport(
        prd_id="PRD-0003",
        prd_title="Discovery",
        stage="accepted",
        total_outcomes=2,
        covered_outcomes=1,
        outcome_coverage_pct=50.0,
        total_bdd_scenarios=2,
        covered_bdd_scenarios=1,
        scenario_coverage_pct=50.0,
        outcome_items=[
            OutcomeScenarioItem(outcome_id=1, outcome_text="Outcome 1", is_covered=True),
            OutcomeScenarioItem(outcome_id=2, outcome_text="Outcome 2", is_covered=False),
        ],
    )
    assert rep.is_fully_covered is False
    summary_text = rep.summary()
    assert "PRD-0003" in summary_text
    assert "50.0%" in summary_text
    assert "[✅] Outcome 1" in summary_text
    assert "[❌] Outcome 2" in summary_text


def test_audit_prd_partial_coverage(repo_env: Path):
    engine = PRDOutcomeCoverageEngine(repo_root=repo_env)
    rep = engine.audit_prd("PRD-0003")
    assert rep.total_outcomes == 2
    assert rep.covered_outcomes == 1
    assert rep.outcome_coverage_pct == 50.0
    assert rep.total_bdd_scenarios == 1
    assert rep.covered_bdd_scenarios == 1
    assert len(rep.outcome_items) == 2
    assert rep.outcome_items[0].is_covered is True
    assert rep.outcome_items[1].is_covered is False


def test_audit_prd_not_found(repo_env: Path):
    engine = PRDOutcomeCoverageEngine(repo_root=repo_env)
    rep = engine.audit_prd("PRD-9999")
    assert rep.prd_title == "Not Found"
    assert rep.total_outcomes == 0
    assert rep.outcome_coverage_pct == 0.0


def test_audit_all(repo_env: Path):
    engine = PRDOutcomeCoverageEngine(repo_root=repo_env)
    reports = engine.audit_all()
    assert len(reports) >= 1
    assert reports[0].prd_id == "PRD-0003"
