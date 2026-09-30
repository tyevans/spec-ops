"""Generative property-based tests for rescue triage taxonomy and invariants (ADR-0009)."""

from __future__ import annotations

from hypothesis import given, strategies as st

from spec_ops.rescue.triage import (
    ALL_CATEGORIES,
    CATEGORY_FILE_LENGTH,
    CATEGORY_GENERAL,
    CATEGORY_LOCKFILE,
    CATEGORY_SYNTAX_DEFECT,
    CATEGORY_TEST_SUITE,
    CATEGORY_WORKING_TREE,
    classify_log_snippet,
    parse_feedback_diagnostics,
)


@given(snippet=st.text(min_size=0, max_size=1000))
def test_classify_log_snippet_arbitrary_string_invariant(snippet: str):
    """Property: Any arbitrary text string deterministically classifies into recognized taxonomy."""
    cat = classify_log_snippet(snippet)
    assert cat in ALL_CATEGORIES
    assert isinstance(cat, str)
    assert len(cat) > 0


@given(
    file_name=st.from_regex(r"[a-z0-9_]+\.py", fullmatch=True),
    line_count=st.integers(min_value=501, max_value=2000),
    limit=st.just(500),
)
def test_classify_file_length_invariants(file_name: str, line_count: int, limit: int):
    """Property: Any string reporting file limit overruns is classified as File Length Invariant."""
    log = f"File length limit violated: {file_name} ({line_count} lines > {limit} limit)"
    cat = classify_log_snippet(log)
    assert cat == CATEGORY_FILE_LENGTH

    findings = parse_feedback_diagnostics(log)
    assert len(findings) == 1
    assert findings[0].category == CATEGORY_FILE_LENGTH
    assert findings[0].status == "FAIL"
    assert findings[0].file_path == file_name
    assert f"{line_count} lines > {limit} limit" in findings[0].details


@given(
    test_path=st.from_regex(r"tests/test_[a-z0-9_]+\.py::test_[a-z0-9_]+", fullmatch=True),
    error_kind=st.sampled_from(["AssertionError", "Failed", "ValueError"]),
)
def test_classify_test_suite_failures(test_path: str, error_kind: str):
    """Property: Any pytest failure signature is classified as Test Suite."""
    log = f"FAILED {test_path} - {error_kind}: condition failed"
    cat = classify_log_snippet(log)
    assert cat == CATEGORY_TEST_SUITE

    findings = parse_feedback_diagnostics(log)
    assert len(findings) >= 1
    assert findings[0].category == CATEGORY_TEST_SUITE
    assert findings[0].status == "FAIL"
    assert test_path in findings[0].details


@given(
    file_path=st.from_regex(r"src/[a-z0-9_]+\.py", fullmatch=True),
    lineno=st.integers(min_value=1, max_value=10000),
    err=st.sampled_from(["SyntaxError", "IndentationError"]),
)
def test_classify_syntax_defects(file_path: str, lineno: int, err: str):
    """Property: Any syntax/indentation traceback is classified as Syntax Defect with line pointer."""
    log = f'File "{file_path}", line {lineno}\n  {err}: invalid syntax'
    cat = classify_log_snippet(log)
    assert cat == CATEGORY_SYNTAX_DEFECT

    findings = parse_feedback_diagnostics(log)
    assert len(findings) >= 1
    assert findings[0].category == CATEGORY_SYNTAX_DEFECT
    assert findings[0].status == "FAIL"
    assert findings[0].line_number == lineno
    assert findings[0].file_path == file_path


@given(lines=st.integers(min_value=0, max_value=5000))
def test_headroom_invariant_boundaries(lines: int):
    """Property: Invariant Boundary Invariant (ADR-0009).

    L > 500: VIOLATION
    400 <= L <= 500: WARNING
    L < 400: COMPLIANT
    """
    headroom = 500 - lines
    status = "VIOLATION" if headroom < 0 else ("WARNING" if headroom <= 100 else "COMPLIANT")

    if lines > 500:
        assert headroom < 0
        assert status == "VIOLATION"
    elif lines >= 400:
        assert 0 <= headroom <= 100
        assert status == "WARNING"
    else:
        assert headroom > 100
        assert status == "COMPLIANT"
