"""Hypothesis generative property tests for PRD Lint UI renderer."""

from __future__ import annotations

import json
import string
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.lint_ui import render_lint_html

SAFE_CHARS = string.ascii_letters + string.digits + " _-"
safe_titles = st.text(alphabet=SAFE_CHARS, min_size=1, max_size=40)

diagnostic_strategy = st.fixed_dictionaries(
    {
        "rule_id": st.sampled_from(["PRD-LINT-001", "PRD-LINT-002", "PRD-LINT-003"]),
        "severity": st.sampled_from(["error", "warning"]),
        "line": st.integers(min_value=1, max_value=200),
        "message": st.text(alphabet=SAFE_CHARS, min_size=5, max_size=50),
    }
)

report_strategy = st.fixed_dictionaries(
    {
        "file_path": st.text(alphabet=SAFE_CHARS, min_size=3, max_size=30).map(lambda s: f"docs/{s}.md"),
        "is_valid": st.booleans(),
        "error_count": st.integers(min_value=0, max_value=20),
        "warning_count": st.integers(min_value=0, max_value=20),
        "falsifiable_count": st.integers(min_value=0, max_value=20),
        "unfalsifiable_count": st.integers(min_value=0, max_value=20),
        "diagnostics": st.lists(diagnostic_strategy, max_size=5),
    }
)


@given(title=safe_titles)
@settings(max_examples=30, deadline=None)
def test_render_html_preserves_title_and_envelope(title: str):
    clean_title = title.strip() or "SpecOps PRD Quality"
    html = render_lint_html(title=clean_title)
    assert "<!DOCTYPE html>" in html
    assert f"<title>{clean_title}</title>" in html
    assert html.endswith("</html>")


@given(reports=st.lists(report_strategy, max_size=5))
@settings(max_examples=30, deadline=None)
def test_render_html_embeds_all_reports(reports: list[dict]):
    html = render_lint_html(reports=reports)
    assert "<!DOCTYPE html>" in html
    for rep in reports:
        assert rep["file_path"] in html
        for diag in rep["diagnostics"]:
            assert diag["rule_id"] in html
