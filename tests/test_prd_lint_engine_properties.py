"""Generative Hypothesis property tests for PRD lint engine and line-level remediation."""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.lint_engine import (
    RULE_UNFALSIFIABLE_OUTCOME,
    PRDLintEngine,
)
from spec_ops.prd.linter import SUBJECTIVE_WORDS
from spec_ops.prd.studio import KNOWN_PERSONAS

SAFE_CHARS = string.ascii_letters + string.digits + " _-"
valid_text = st.text(alphabet=SAFE_CHARS, min_size=3, max_size=30).map(str.strip).filter(lambda s: len(s) >= 3)
valid_personas = st.sampled_from(sorted(KNOWN_PERSONAS))
subjective_sample = st.sampled_from(SUBJECTIVE_WORDS)


@settings(max_examples=40, deadline=None)
@given(word=subjective_sample, prefix=valid_text, suffix=valid_text)
def test_subjective_remediation_invariants(word: str, prefix: str, suffix: str):
    engine = PRDLintEngine()
    orig = f"{prefix} {word} {suffix}"
    sug = engine.synthesize_remediation(RULE_UNFALSIFIABLE_OUTCOME, line=10, text=orig, detail=word)
    # The suggested text must replace the subjective word
    assert word.lower() not in sug.suggested_text.lower().split()
    assert len(sug.suggested_text) > 0
    assert len(sug.remediation_hint) > 0


@settings(max_examples=40, deadline=None)
@given(persona=valid_personas, title=valid_text, outcome=valid_text)
def test_valid_document_lint_invariants(persona: str, title: str, outcome: str):
    engine = PRDLintEngine()
    # Strip any possible subjective word accidental match in randomized text
    clean_outcome = outcome
    for w in SUBJECTIVE_WORDS:
        clean_outcome = clean_outcome.replace(w, "tested")

    doc = f"""---
id: PRD-0999
title: {title}
status: Idea
target_persona: {persona}
component: core
---
## Problem Statement
Valid problem statement description.
## What good looks like
Observable outcome capabilities.
## What this does not do
Scope boundary non-goals.
## Checkable Outcomes
- Observable assertion: {clean_outcome}
"""
    report = engine.lint_content(doc)
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.falsifiable_count == 1
    assert report.unfalsifiable_count == 0
