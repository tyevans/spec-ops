"""Generative property-based invariant tests for customer release notes generator (ADR-0009, US-0049)."""

from __future__ import annotations

import json
from hypothesis import given, strategies as st

from spec_ops.release.customer_notes import (
    CustomerReleaseNotesData,
    PersonaImpact,
    UATOutcome,
    render_html_customer_notes,
    render_json_customer_notes,
    render_markdown_customer_notes,
    sanitize_customer_text,
)

safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=100,
).map(lambda s: s.strip() or "Sample")

persona_strategy = st.builds(
    PersonaImpact,
    name=st.sampled_from(["Taylor", "Alex", "Jordan", "Riley", "Morgan", "Sasha"]),
    role=st.text(min_size=0, max_size=50),
    benefits=st.lists(safe_text, min_size=0, max_size=5),
)

outcome_strategy = st.builds(
    UATOutcome,
    outcome=safe_text,
    verified=st.booleans(),
)

data_strategy = st.builds(
    CustomerReleaseNotesData,
    prd_id=st.integers(min_value=1, max_value=9999).map(lambda n: f"PRD-{str(n).zfill(4)}"),
    title=safe_text,
    status=st.sampled_from(["Shipped", "Accepted", "Verified"]),
    summary=st.text(max_size=200),
    target_persona=st.sampled_from(["Taylor", "Alex", "Jordan", "Riley"]),
    personas=st.lists(persona_strategy, min_size=1, max_size=4),
    uat_outcomes=st.lists(outcome_strategy, min_size=0, max_size=10),
    capabilities=st.lists(st.tuples(safe_text, safe_text), min_size=0, max_size=5),
    stories=st.lists(st.tuples(safe_text, safe_text, safe_text), min_size=0, max_size=5),
)


@given(data=data_strategy)
def test_markdown_rendering_invariant(data: CustomerReleaseNotesData) -> None:
    """Asserts markdown rendering always produces non-empty text with header."""
    md = render_markdown_customer_notes(data)
    assert isinstance(md, str)
    assert len(md) > 0
    assert f"# Release Notes: {data.title}" in md
    assert "## Target Persona Benefits" in md


@given(data=data_strategy, branded=st.booleans())
def test_html_rendering_invariant(data: CustomerReleaseNotesData, branded: bool) -> None:
    """Asserts HTML rendering produces valid standalone HTML with verified checkmarks and no raw unescaped script tags."""
    html_out = render_html_customer_notes(data, branded=branded)
    assert isinstance(html_out, str)
    assert "<!DOCTYPE html>" in html_out
    assert "</html>" in html_out
    assert "Verifiable Customer UAT Checkmarks" in html_out
    # XSS safety: if unescaped <script> appears in title/summary/outcomes, it must be escaped
    assert "<script>" not in html_out


@given(data=data_strategy)
def test_json_rendering_invariant(data: CustomerReleaseNotesData) -> None:
    """Asserts JSON rendering always produces valid deserializable JSON."""
    json_str = render_json_customer_notes(data)
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["prd_id"] == data.prd_id
    assert parsed["title"] == data.title
    assert isinstance(parsed["personas"], list)
    assert isinstance(parsed["uat_outcomes"], list)


@given(text=st.text())
def test_sanitize_text_invariant(text: str) -> None:
    """Asserts sanitizing arbitrary text never raises and produces clean output."""
    clean = sanitize_customer_text(text)
    assert isinstance(clean, str)
    assert not clean.startswith(" ")
    assert not clean.endswith(" ")
