"""Hypothesis generative property tests for PRD Lint frontdoor runner."""

from __future__ import annotations

import io
import json
import string
import sys
from pathlib import Path
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.config.models import SpecOpsConfig
from spec_ops.prd.lint_runner import run_prd_lint

SAFE_CHARS = string.ascii_letters + string.digits + " _-"
valid_personas = st.sampled_from(["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Casey", "Riley", "Devon"])
safe_text = st.text(alphabet=SAFE_CHARS, min_size=3, max_size=40)


@given(
    persona=valid_personas,
    title=safe_text,
    outcome=safe_text,
)
@settings(max_examples=30, deadline=None)
def test_frontdoor_json_output_always_valid_schema(tmp_path_factory, persona: str, title: str, outcome: str):
    tmp_path = tmp_path_factory.mktemp("prop_lint")
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    clean_title = title.strip() or "Feature"
    clean_outcome = outcome.strip().lstrip("-* ").strip() or "Standard execution"

    doc = f"""---
id: PRD-0001
title: {clean_title}
status: Idea
target_persona: {persona}
component: prd
---

# PRD-0001: {clean_title}

## Problem Statement
Valid problem.

## What good looks like
Valid behavior.

## What this does not do
None.

## Checkable Outcomes
- {clean_outcome}
"""
    (prd_dir / "prd-0001.md").write_text(doc, encoding="utf-8")
    config = SpecOpsConfig(root_dir=tmp_path)

    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        code = run_prd_lint(config, json_output=True)
    finally:
        sys.stdout = old_stdout

    data = json.loads(buf.getvalue())
    assert "total_files" in data
    assert data["total_files"] == 1
    assert "reports" in data
    assert len(data["reports"]) == 1
    assert data["valid_files"] in (0, 1)
