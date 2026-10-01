"""Hypothesis property-based tests for executive milestone briefing (ADR-0009)."""

from __future__ import annotations

import re
import string
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.milestone_briefing import (
    MilestoneBriefing,
    render_briefing_html,
    render_briefing_markdown,
)


@st.composite
def milestone_briefing_strategy(draw):
    mid = draw(st.text(alphabet=string.ascii_uppercase + string.digits + "-", min_size=2, max_size=12))
    title = draw(st.text(alphabet=string.ascii_letters + " ", min_size=3, max_size=30))
    status = draw(st.sampled_from(["Active", "Complete", "Planned", "In-Flight"]))
    total = draw(st.integers(min_value=0, max_value=300))
    completed = draw(st.integers(min_value=0, max_value=total if total > 0 else 0))
    raw_pct = (completed / total * 100.0) if total > 0 else 0.0
    pct = max(0.0, min(100.0, round(raw_pct, 1)))

    unanchored = draw(st.integers(min_value=0, max_value=50))
    stability = max(0.0, min(100.0, round(100.0 - (unanchored * 3.5), 1)))
    velocity = round(draw(st.floats(min_value=0.5, max_value=40.0)), 1)
    file_violations = draw(st.integers(min_value=0, max_value=10))

    personas = {
        "Alex": {"role": "Architect", "quote": "Zero context rot.", "stories": ["US-0001: Core"]},
        "Jordan": {"role": "Engineering Lead", "quote": "Frontdoor testing always.", "stories": ["US-0023: Briefing"]},
        "Morgan": {"role": "Autonomous Agent", "quote": "Strict worktree sandboxing.", "stories": ["US-0011: Workers"]},
        "Riley": {"role": "Human Developer", "quote": "Zero-friction takeover.", "stories": []},
        "Taylor": {"role": "Product Manager", "quote": "Living PRD traceability.", "stories": ["US-0003: PRD"]},
    }

    critical_items = [f"TASK-00{i}: Deliverable {i}" for i in range(draw(st.integers(min_value=0, max_value=5)))]
    risks = [f"Risk item {i}" for i in range(draw(st.integers(min_value=0, max_value=3)))]

    return MilestoneBriefing(
        milestone_id=mid,
        title=title,
        status=status,
        target_date="2026-10-30",
        total_tasks=total,
        completed_tasks=completed,
        remaining_tasks=max(0, total - completed),
        completion_pct=pct,
        projected_date="2026-11-15",
        velocity_per_week=velocity,
        scope_stability_pct=stability,
        unanchored_count=unanchored,
        critical_path_items=critical_items,
        risk_factors=risks,
        persona_impacts=personas,
        test_count=716,
        mutation_score=84.0,
        file_violations=file_violations,
        is_healthy=file_violations == 0,
    )


@settings(max_examples=40, deadline=None)
@given(b=milestone_briefing_strategy())
def test_property_completion_percentage_bounded(b: MilestoneBriefing):
    """Generative property invariant (ADR-0009): Completion percentage is bounded in [0.0, 100.0]."""
    assert 0.0 <= b.completion_pct <= 100.0
    assert 0.0 <= b.scope_stability_pct <= 100.0
    assert b.completed_tasks <= b.total_tasks
    assert b.remaining_tasks == max(0, b.total_tasks - b.completed_tasks)


@settings(max_examples=40, deadline=None)
@given(b=milestone_briefing_strategy())
def test_property_html_briefing_zero_external_dependencies(b: MilestoneBriefing):
    """Generative property invariant: Rendered briefing HTML contains ZERO external CDN/script tags."""
    html = render_briefing_html(b)

    # 1. Complete standalone HTML document structure
    assert html.startswith("<!DOCTYPE html>")
    assert "<html" in html and "</html>" in html
    assert "<head>" in html and "</head>" in html
    assert "<body>" in html and "</body>" in html
    assert "<style>" in html and "</style>" in html

    # 2. Airgap invariant: Zero external scripts or links
    ext_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']https?://', html, re.IGNORECASE)
    assert len(ext_scripts) == 0, f"Found external scripts: {ext_scripts}"
    ext_links = re.findall(r'<link\b[^>]*\bhref=["\']https?://', html, re.IGNORECASE)
    assert len(ext_links) == 0, f"Found external stylesheets: {ext_links}"

    # 3. Visual progress ring component
    assert "<svg" in html and "circle" in html
    assert f"{b.completion_pct}%" in html

    # 4. Mandatory content sections
    assert "Critical Path Deliverables" in html
    assert "Delivery Risks & Roadblocks" in html
    assert "Quantified Customer Value Delivered by Persona" in html
    for p in ["Alex", "Jordan", "Morgan", "Riley", "Taylor"]:
        assert p in html


@settings(max_examples=30, deadline=None)
@given(b=milestone_briefing_strategy())
def test_property_markdown_briefing_invariants(b: MilestoneBriefing):
    """Generative property invariant: Markdown digest conforms to executive format."""
    md = render_briefing_markdown(b)

    assert b.title in md
    assert b.milestone_id in md
    assert f"{b.completion_pct}%" in md
    assert f"{b.completed_tasks}/{b.total_tasks}" in md
    assert b.target_date in md
    assert "| Persona | Role |" in md
    assert "Quality & Verification Invariants" in md
    assert "Critical Path & Delivery Horizon" in md
