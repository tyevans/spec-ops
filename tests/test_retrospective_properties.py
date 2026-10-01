"""Hypothesis generative property tests for orchestration retrospective engine (ADR-0009, US-0117)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.worker.retrospective import (
    GENERIC_FALLBACK,
    INVARIANT_PATTERNS,
    FailurePattern,
    classify_failure,
)

KNOWN_INVARIANT_IDS = set(INVARIANT_PATTERNS.keys()) | {GENERIC_FALLBACK["invariant_id"]}


@settings(max_examples=100)
@given(log_text=st.text())
def test_property_arbitrary_error_log_parses_without_exception(log_text: str):
    """Assert that any arbitrary string parses deterministically without exceptions into valid patterns."""
    patterns = classify_failure(log_text)

    # Invariant: Always returns at least one pattern
    assert len(patterns) >= 1
    assert all(isinstance(p, FailurePattern) for p in patterns)

    # Invariant: Every pattern maps to a known invariant category or fallback
    for p in patterns:
        assert p.invariant_id in KNOWN_INVARIANT_IDS
        assert len(p.category) > 0
        assert len(p.mandate) > 0
        assert len(p.governing_adrs) >= 1
        assert len(p.governing_prds) >= 1

    # Invariant: Deterministic execution (idempotency)
    second_run = classify_failure(log_text)
    assert len(patterns) == len(second_run)
    assert [p.invariant_id for p in patterns] == [p.invariant_id for p in second_run]


@settings(max_examples=50)
@given(
    prefix=st.text(max_size=50),
    suffix=st.text(max_size=50),
    inv_id=st.sampled_from(list(INVARIANT_PATTERNS.keys())),
)
def test_property_explicit_invariant_always_detected(prefix: str, suffix: str, inv_id: str):
    """Assert that when an explicit ADR token is present, that invariant is guaranteed to be detected."""
    synthetic_log = f"{prefix}\nError occurred violating {inv_id} in preflight\n{suffix}"
    patterns = classify_failure(synthetic_log)
    detected_ids = {p.invariant_id for p in patterns}
    assert inv_id in detected_ids


@settings(max_examples=50)
@given(
    noise=st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")), max_size=100),
    keyword=st.sampled_from(["mock backdoor", "lines > limit 500", "high-entropy secret", "lockfile mutation", "dependency cycle"]),
)
def test_property_keyword_in_noise_detected(noise: str, keyword: str):
    """Assert that domain failure keywords embedded in noise trigger the appropriate invariant."""
    text = f"{noise} {keyword} {noise}"
    patterns = classify_failure(text)
    detected_ids = {p.invariant_id for p in patterns}
    # Should not be solely fallback if one of the distinct domain keywords is present
    assert any(inv != "ADR-0020" for inv in detected_ids)
