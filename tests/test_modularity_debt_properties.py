"""Hypothesis generative property tests for modularity debt scoring invariants (ADR-0009)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.core.modularity_debt import ModularityDebtAnalyzer


@given(
    line_counts=st.lists(st.integers(min_value=-500, max_value=5000), min_size=1, max_size=50),
    imports_count=st.integers(min_value=-50, max_value=200),
)
def test_modularity_debt_monotonicity_and_bounds(line_counts: list[int], imports_count: int):
    """Asserts that for any arbitrary list of file line counts, calculated modularity risk scores:

    1. Scale monotonically with file length.
    2. Remain strictly bounded between 0.0 and 100.0 without unhandled exceptions.
    """
    sorted_lines = sorted(line_counts)
    scores = [ModularityDebtAnalyzer.calculate_file_score(l, imports_count) for l in sorted_lines]

    for score in scores:
        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0

    for i in range(len(scores) - 1):
        assert scores[i] <= scores[i + 1], (
            f"Monotonicity violation at lines {sorted_lines[i]} -> {sorted_lines[i + 1]}: "
            f"score {scores[i]} > {scores[i + 1]}"
        )


@given(
    l1=st.integers(min_value=0, max_value=2000),
    l2=st.integers(min_value=0, max_value=2000),
)
def test_modularity_debt_pairwise_monotonicity(l1: int, l2: int):
    """Pairwise monotonic invariant: l1 <= l2 implies score(l1) <= score(l2)."""
    score1 = ModularityDebtAnalyzer.calculate_file_score(l1)
    score2 = ModularityDebtAnalyzer.calculate_file_score(l2)

    assert 0.0 <= score1 <= 100.0
    assert 0.0 <= score2 <= 100.0

    if l1 <= l2:
        assert score1 <= score2
    else:
        assert score1 >= score2
