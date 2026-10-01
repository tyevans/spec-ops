"""Hypothesis property-based tests for DiagnosticInjector invariants (ADR-0009)."""

from __future__ import annotations

import json
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.worker.diagnostic_injector import DiagnosticCard, DiagnosticInjector

trace_chars = st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc", "Zs", "Po"))


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(output=st.text())
def test_diagnose_failure_never_raises_on_arbitrary_string(output: str):
    """Invariant: Arbitrary text never crashes the diagnostic engine and returns deterministic cards."""
    cards = DiagnosticInjector.diagnose_failure(output)
    assert isinstance(cards, list)
    for card in cards:
        assert isinstance(card, DiagnosticCard)
        assert isinstance(card.file_path, str)
        assert card.failure_category in (
            "assertion_error",
            "file_limit_violation",
            "syntax_error",
            "runtime_error",
            "unknown",
        )
        d = card.to_dict()
        assert isinstance(d, dict)
        # Verify JSON serializability
        serialized = json.dumps(d)
        assert serialized is not None


@settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(output=st.text())
def test_diagnose_failure_determinism_property(output: str):
    """Invariant: Identical output produces identical diagnostic cards across invocations."""
    cards_1 = DiagnosticInjector.diagnose_failure(output)
    cards_2 = DiagnosticInjector.diagnose_failure(output)
    assert len(cards_1) == len(cards_2)
    for c1, c2 in zip(cards_1, cards_2):
        assert c1.file_path == c2.file_path
        assert c1.line_number == c2.line_number
        assert c1.failure_category == c2.failure_category
        assert c1.node_type == c2.node_type
        assert c1.node_name == c2.node_name


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    file_name=st.from_regex(r"[a-z0-9_]{1,10}\.py", fullmatch=True),
    line_no=st.integers(min_value=1, max_value=2000),
    err_msg=st.text(alphabet=trace_chars, min_size=0, max_size=50),
)
def test_diagnose_pytest_assertion_trace_property(file_name: str, line_no: int, err_msg: str):
    """Invariant: Formatted pytest assertion errors are deterministically extracted."""
    trace = f"src/spec_ops/{file_name}:{line_no}: AssertionError: {err_msg}"
    cards = DiagnosticInjector.diagnose_failure(trace)
    assert len(cards) >= 1
    matched = [c for c in cards if c.file_path == f"src/spec_ops/{file_name}"]
    assert len(matched) == 1
    card = matched[0]
    assert card.line_number == line_no
    assert card.failure_category == "assertion_error"
    assert card.breached_rule == "ADR-0003"


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    file_name=st.from_regex(r"[a-z0-9_]{1,10}\.py", fullmatch=True),
    line_count=st.integers(min_value=501, max_value=3000),
)
def test_diagnose_file_length_violation_property(file_name: str, line_count: int):
    """Invariant: File length violations are extracted and mapped to ADR-0002."""
    output = f"File Length Violation: src/spec_ops/{file_name} ({line_count} lines > 500 line limit)"
    cards = DiagnosticInjector.diagnose_failure(output)
    assert len(cards) >= 1
    matched = [c for c in cards if c.file_path == f"src/spec_ops/{file_name}"]
    assert len(matched) == 1
    card = matched[0]
    assert card.failure_category == "file_limit_violation"
    assert card.breached_rule == "ADR-0002"
    assert "exceeds file length limit" in card.actionable_guidance


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    cards_data=st.lists(
        st.tuples(
            st.from_regex(r"[a-z0-9_]{1,10}\.py", fullmatch=True),
            st.integers(min_value=1, max_value=500),
            st.sampled_from(["assertion_error", "file_limit_violation", "syntax_error", "unknown"]),
        ),
        min_size=0,
        max_size=5,
    )
)
def test_synthesize_retry_prompt_invariants(cards_data: list[tuple[str, int, str]]):
    """Invariant: Synthesized retry prompt contains invariant prohibitions and structured guidance."""
    cards: list[DiagnosticCard] = []
    for fpath, lno, cat in cards_data:
        rule = "ADR-0002" if cat == "file_limit_violation" else ("ADR-0003" if cat == "assertion_error" else None)
        cards.append(
            DiagnosticCard(
                file_path=fpath,
                line_number=lno,
                node_type="FunctionDef",
                node_name="test_fn",
                source_snippet="def test_fn(): pass",
                failure_category=cat,
                breached_rule=rule,
                actionable_guidance="Fix the issue.",
            )
        )

    prompt = DiagnosticInjector.synthesize_retry_prompt(cards)
    assert isinstance(prompt, str)
    if not cards:
        assert prompt == ""
    else:
        assert "## Preflight Failure Diagnostics & AST Self-Healing Guidance" in prompt
        assert "## Mandatory Invariant Prohibitions (DO NOT REPEAT)" in prompt
        assert "ADR-0002" in prompt
        assert "ADR-0003" in prompt
        assert "ADR-0005" in prompt
        assert "ADR-0020" in prompt
        for card in cards:
            assert card.file_path in prompt
