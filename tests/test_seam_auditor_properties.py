"""Hypothesis generative property tests for Bounded Context Seam Auditor coupling metrics."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.seam_auditor import calculate_instability


@given(
    ca=st.integers(min_value=0, max_value=10000),
    ce=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=100)
def test_instability_bounded_property(ca: int, ce: int) -> None:
    """Property: Instability index I = Ce / (Ca + Ce) is strictly bounded in [0.0, 1.0] for any inputs."""
    instability = calculate_instability(ca, ce)
    assert 0.0 <= instability <= 1.0

    if ca == 0 and ce == 0:
        assert instability == 0.0
    elif ca > 0 and ce == 0:
        assert instability == 0.0
    elif ca == 0 and ce > 0:
        assert instability == 1.0


@given(
    ca=st.integers(min_value=-100, max_value=-1),
    ce=st.integers(min_value=-100, max_value=-1),
)
@settings(max_examples=25)
def test_negative_coupling_protection_property(ca: int, ce: int) -> None:
    """Property: Negative coupling values are gracefully sanitized to 0.0."""
    assert calculate_instability(ca, ce) == 0.0
