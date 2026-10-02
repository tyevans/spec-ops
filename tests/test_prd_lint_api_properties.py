"""Hypothesis generative property tests for PRD Lint API contracts."""

from __future__ import annotations

import string
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.lint_api import dispatch_lint_api_request, lint_prd_api
from spec_ops.prd.lint_engine import PRDLintEngine

SAFE_CHARS = string.ascii_letters + string.digits + " _-"

valid_personas = st.sampled_from(["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Casey", "Riley", "Devon"])
safe_text = st.text(alphabet=SAFE_CHARS, min_size=3, max_size=40)


@given(
    persona=valid_personas,
    title=safe_text,
    outcome=safe_text,
)
@settings(max_examples=35, deadline=None)
def test_dispatch_post_lint_always_returns_valid_response(persona: str, title: str, outcome: str):
    clean_title = title.strip() or "Feature"
    clean_outcome = outcome.strip().lstrip("-* ").strip() or "Standard execution"
    content = f"""---
id: PRD-0001
title: {clean_title}
status: Idea
target_persona: {persona}
component: prd
---

# PRD-0001: {clean_title}

## Problem Statement
A valid problem statement.

## What good looks like
Well-defined behavior.

## What this does not do
Does not introduce unverified claims.

## Checkable Outcomes
- {clean_outcome}
"""
    engine = PRDLintEngine()
    code, res = dispatch_lint_api_request(
        engine,
        "POST",
        "/api/prd/lint",
        payload={"content": content},
    )
    assert code == 200
    assert res.get("success") is True
    report = res.get("report")
    assert report is not None
    assert isinstance(report["diagnostics"], list)
    assert report["error_count"] >= 0
    assert report["warning_count"] >= 0


@given(
    persona=valid_personas,
    title=safe_text,
    subjective_word=st.sampled_from(["fast", "intuitive", "simple", "scalable", "modern"]),
)
@settings(max_examples=35, deadline=None)
def test_dispatch_remediate_improves_or_maintains_quality(persona: str, title: str, subjective_word: str):
    clean_title = title.strip() or "Feature"
    content = f"""---
id: PRD-0002
title: {clean_title}
status: Idea
target_persona: {persona}
component: prd
---

# PRD-0002: {clean_title}

## Problem Statement
Valid statement.

## What good looks like
Valid behavior.

## What this does not do
None.

## Checkable Outcomes
- Execution is {subjective_word} and responsive
"""
    engine = PRDLintEngine()
    code, res = dispatch_lint_api_request(
        engine,
        "POST",
        "/api/prd/lint/remediate",
        payload={"content": content},
    )
    assert code == 200
    assert res.get("success") is True
    assert res.get("applied_count", 0) >= 1
    new_report = res.get("new_report")
    assert new_report is not None
    assert new_report["unfalsifiable_count"] == 0
