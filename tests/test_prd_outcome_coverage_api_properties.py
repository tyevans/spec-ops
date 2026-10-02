"""Hypothesis generative property tests for PRD outcome coverage API contracts."""

from __future__ import annotations

import string
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.outcome_coverage import PRDOutcomeCoverageEngine
from spec_ops.prd.outcome_coverage_api import audit_prd_outcome_coverage_api, dispatch_outcome_coverage_api_request

SAFE_CHARS = string.ascii_letters + string.digits + " _-"
safe_text = st.text(alphabet=SAFE_CHARS, min_size=3, max_size=40)
valid_personas = st.sampled_from(["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Casey", "Riley", "Devon"])


@given(
    persona=valid_personas,
    title=safe_text,
    outcome=safe_text,
)
@settings(max_examples=30, deadline=None)
def test_api_functional_always_valid(tmp_path_factory, persona: str, title: str, outcome: str):
    tmp_path = tmp_path_factory.mktemp("prop_api")
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    clean_title = title.strip() or "Feature"
    clean_outcome = outcome.strip().lstrip("-* ").strip() or "Standard check"

    (prd_dir / "prd-0001.md").write_text(
        f"""---
id: PRD-0001
title: {clean_title}
status: Accepted
target_persona: {persona}
---
# PRD-0001
## Checkable Outcomes
- {clean_outcome}
""",
        encoding="utf-8",
    )

    res = audit_prd_outcome_coverage_api("PRD-0001", repo_root=tmp_path)
    assert res["success"] is True
    assert res["total_prds"] == 1
    assert 0.0 <= res["overall_outcome_coverage_pct"] <= 100.0
    assert len(res["reports"]) == 1


@given(unknown_route=st.text(alphabet=SAFE_CHARS, min_size=1, max_size=30).map(lambda s: f"/api/unknown/{s}"))
@settings(max_examples=25, deadline=None)
def test_dispatch_unknown_route_returns_404(unknown_route: str):
    engine = PRDOutcomeCoverageEngine()
    code, res = dispatch_outcome_coverage_api_request(engine, "GET", unknown_route)
    assert code == 404
    assert res["success"] is False
