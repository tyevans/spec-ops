"""Generative property-based testing for mutation gate invariants (ADR-0009)."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.mutation_gate import (
    MutationReport,
    SurvivingMutant,
    calculate_mutation_score,
    load_specops_report,
    parse_diff_details,
)


@given(
    killed=st.integers(min_value=0, max_value=5000),
    survived=st.integers(min_value=0, max_value=5000),
    timeout=st.integers(min_value=0, max_value=5000),
)
@settings(max_examples=100)
def test_mutation_score_calculation_property(killed: int, survived: int, timeout: int):
    """Hypothesis Invariant: Mutation score is bounded in [0.0, 100.0] and handles zero mutants gracefully."""
    total = killed + survived + timeout
    score = calculate_mutation_score(killed, total)

    if total == 0:
        assert score == 100.0
    else:
        assert 0.0 <= score <= 100.0
        expected = round((killed / total) * 100.0, 1)
        assert score == expected

    if total > 0 and killed == 0:
        assert score == 0.0
    if total > 0 and killed == total:
        assert score == 100.0


@given(
    total=st.integers(min_value=1, max_value=2000),
    k1=st.integers(min_value=0, max_value=2000),
    k2=st.integers(min_value=0, max_value=2000),
)
@settings(max_examples=80)
def test_mutation_score_monotonicity(total: int, k1: int, k2: int):
    """Hypothesis Invariant: For fixed total > 0, mutation score monotonically increases with killed count."""
    k_low = min(k1, k2, total)
    k_high = max(min(k1, total), min(k2, total))

    score_low = calculate_mutation_score(k_low, total)
    score_high = calculate_mutation_score(k_high, total)
    assert score_low <= score_high


@given(
    score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    threshold=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=80)
def test_threshold_pass_invariant(score: float, threshold: float):
    """Hypothesis Invariant: Quality gate passes if and only if score >= threshold."""
    report = MutationReport(
        target_module="src/spec_ops/core",
        threshold=threshold,
        killed_count=int(score),
        survived_count=100 - int(score),
        total_mutants=100,
        mutation_score=round(score, 1),
    )
    assert report.is_passed == (round(score, 1) >= threshold)


@given(
    target=st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))),
    killed=st.integers(min_value=0, max_value=500),
    survived=st.integers(min_value=0, max_value=500),
    threshold=st.floats(min_value=10.0, max_value=95.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=60)
def test_report_serialization_roundtrip(tmp_path: Path, target: str, killed: int, survived: int, threshold: float):
    """Hypothesis Invariant: Report serialization roundtrip preserves metric integrity."""
    tot = killed + survived
    mutants = [
        SurvivingMutant(
            mutant_id=f"mutant_{i}",
            file_path=f"src/{target}/file_{i}.py",
            line=i * 2 + 1,
            expression=f"x = {i}",
            diff=f"--- src/{target}/file_{i}.py\n+++ src/{target}/file_{i}.py\n@@ -{i * 2 + 1} +{i * 2 + 1} @@\n-x = 0\n+x = {i}",
        )
        for i in range(min(survived, 5))
    ]

    report = MutationReport(
        target_module=f"src/{target}",
        threshold=round(threshold, 1),
        killed_count=killed,
        survived_count=survived,
        timeout_count=0,
        total_mutants=tot,
        mutation_score=calculate_mutation_score(killed, tot),
        survived_mutants=mutants,
    )

    data = report.to_dict()
    report_file = tmp_path / "mutation_report.json"
    report_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    loaded = load_specops_report(report_file, target_module=f"src/{target}", threshold=threshold)
    assert loaded is not None
    assert loaded.target_module == report.target_module
    assert loaded.killed_count == report.killed_count
    assert loaded.survived_count == report.survived_count
    assert loaded.mutation_score == report.mutation_score
    assert len(loaded.survived_mutants) == len(mutants)


@given(
    line_no=st.integers(min_value=1, max_value=9999),
    expr=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
)
@settings(max_examples=60)
def test_diff_details_parsing_property(line_no: int, expr: str):
    """Hypothesis Invariant: Unified diff parsing deterministically extracts line number and mutated expression."""
    clean_expr = expr.strip() or "val = True"
    diff_text = (
        f"--- original.py\n"
        f"+++ mutated.py\n"
        f"@@ -{line_no},1 +{line_no},1 @@\n"
        f"-original_expr()\n"
        f"+{clean_expr}\n"
    )
    fpath, lno, parsed_expr = parse_diff_details(diff_text, fallback_file="original.py")
    assert fpath == "mutated.py"
    assert lno == line_no
    assert parsed_expr == clean_expr
