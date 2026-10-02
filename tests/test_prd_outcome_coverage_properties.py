"""Hypothesis generative property tests for PRD outcome test coverage."""

from __future__ import annotations

import string
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.outcome_coverage import OutcomeScenarioItem, PRDTestCoverageReport

SAFE_CHARS = string.ascii_letters + string.digits + " _-"


@given(
    total=st.integers(min_value=0, max_value=50),
    covered=st.integers(min_value=0, max_value=50),
    total_scenarios=st.integers(min_value=0, max_value=50),
    covered_scenarios=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=40, deadline=None)
def test_report_invariants(total: int, covered: int, total_scenarios: int, covered_scenarios: int):
    actual_covered = min(total, covered)
    actual_covered_scenarios = min(total_scenarios, covered_scenarios)

    outcome_pct = round((actual_covered / total) * 100.0, 1) if total > 0 else 100.0
    scenario_pct = round((actual_covered_scenarios / total_scenarios) * 100.0, 1) if total_scenarios > 0 else 100.0

    rep = PRDTestCoverageReport(
        prd_id="PRD-0001",
        prd_title="Invariants",
        stage="accepted",
        total_outcomes=total,
        covered_outcomes=actual_covered,
        outcome_coverage_pct=outcome_pct,
        total_bdd_scenarios=total_scenarios,
        covered_bdd_scenarios=actual_covered_scenarios,
        scenario_coverage_pct=scenario_pct,
    )

    assert 0.0 <= rep.outcome_coverage_pct <= 100.0
    assert 0.0 <= rep.scenario_coverage_pct <= 100.0
    assert rep.covered_outcomes <= rep.total_outcomes
    assert rep.covered_bdd_scenarios <= rep.total_bdd_scenarios
    if total > 0 and actual_covered == total:
        assert rep.is_fully_covered is True
    else:
        assert rep.is_fully_covered is False
