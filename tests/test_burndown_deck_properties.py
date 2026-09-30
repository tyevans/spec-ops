"""Hypothesis property-based tests for milestone burndown deck exporter (ADR-0009)."""

from __future__ import annotations

import re
import string
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.visualizer.burndown_deck import MilestoneBurndown, render_presentation_deck


@st.composite
def milestone_burndown_strategy(draw):
    mid = draw(st.text(alphabet=string.ascii_uppercase + string.digits + "-", min_size=2, max_size=15))
    title = draw(st.text(alphabet=string.ascii_letters + " ", min_size=3, max_size=40))
    status = draw(st.sampled_from(["Active", "Complete", "Planned", "In-Flight"]))
    total = draw(st.integers(min_value=1, max_value=200))
    completed = draw(st.integers(min_value=0, max_value=total))
    pct = round(completed / total * 100.0, 1)
    velocity = round(draw(st.floats(min_value=0.5, max_value=50.0)), 1)
    stability = round(draw(st.floats(min_value=0.0, max_value=100.0)), 1)
    unanchored = draw(st.integers(min_value=0, max_value=30))
    test_count = draw(st.integers(min_value=10, max_value=2000))
    mutation_score = round(draw(st.floats(min_value=50.0, max_value=100.0)), 1)
    file_violations = draw(st.integers(min_value=0, max_value=10))

    personas = {
        "Alex": {"role": "Architect", "quote": "SpecOps invariant", "stories": ["US-0001: Core"]},
        "Jordan": {"role": "Lead", "quote": "Frontdoor verification", "stories": ["US-0002: BDD"]},
        "Morgan": {"role": "Agent", "quote": "Worktree isolation", "stories": ["US-0003: Runner"]},
        "Riley": {"role": "Developer", "quote": "Ergonomics", "stories": ["US-0004: TUI"]},
        "Taylor": {"role": "PM", "quote": "Living reporting", "stories": ["US-0005: Decks"]},
    }

    return MilestoneBurndown(
        milestone_id=mid,
        title=title,
        status=status,
        horizon="2026-10-30",
        total_tasks=total,
        completed_tasks=completed,
        remaining_tasks=total - completed,
        completion_pct=pct,
        velocity_per_week=velocity,
        projected_delivery_horizon="2026-11-15",
        scope_stability_pct=stability,
        unanchored_tasks_count=unanchored,
        persona_value=personas,
        test_count=test_count,
        mutation_score=mutation_score,
        file_violations=file_violations,
        is_healthy=file_violations == 0,
        blocked_dependencies=[],
    )


@settings(max_examples=30, deadline=None)
@given(b=milestone_burndown_strategy())
def test_property_presentation_deck_zero_external_dependencies(b: MilestoneBurndown):
    """Generative property invariant (ADR-0009): Rendered deck contains ZERO external script or style tags."""
    html = render_presentation_deck(b)

    # Invariant 1: Airgap integrity - Zero external network calls
    external_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']https?://', html, re.IGNORECASE)
    assert len(external_scripts) == 0, f"Found external scripts: {external_scripts}"

    external_links = re.findall(r'<link\b[^>]*\bhref=["\']https?://', html, re.IGNORECASE)
    assert len(external_links) == 0, f"Found external stylesheets: {external_links}"

    # Invariant 2: Complete HTML structure
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<style>" in html
    assert "<script>" in html

    # Invariant 3: All 4 executive slides are present
    assert 'data-slide="1"' in html
    assert 'data-slide="2"' in html
    assert 'data-slide="3"' in html
    assert 'data-slide="4"' in html

    # Invariant 4: Interactive radial progress meters & SVG visualization
    assert "<svg" in html and "circle" in html
    assert f"{b.completion_pct}%" in html

    # Invariant 5: Keyboard navigation event listener
    assert "ArrowRight" in html or "ArrowLeft" in html or "keydown" in html
