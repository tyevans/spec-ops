"""Hypothesis property-based tests for executive roadmap visualizer and exporter (ADR-0009)."""

from __future__ import annotations

import re
import string
import xml.etree.ElementTree as ET

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.exporter import (
    RoadmapMilestone,
    calculate_progress,
    render_roadmap_html,
    render_roadmap_svg,
)


@st.composite
def milestone_strategy(draw):
    mid = draw(st.text(alphabet=string.ascii_uppercase + string.digits + "-", min_size=1, max_size=10))
    title = draw(st.text(alphabet=string.ascii_letters + string.digits + " _-&<>\"'", min_size=1, max_size=30))
    status = draw(st.sampled_from(["Active", "Complete", "Planned", "In-Flight", "Draft"]))
    horizon = draw(st.text(alphabet=string.digits + "-/: ", min_size=4, max_size=20))

    task_count = draw(st.integers(min_value=0, max_value=20))
    tasks = [f"TASK-{draw(st.integers(min_value=1, max_value=9999)):04d}" for _ in range(task_count)]
    # deduplicate tasks
    tasks = list(dict.fromkeys(tasks))

    completed_count = draw(st.integers(min_value=0, max_value=len(tasks))) if tasks else 0
    completed = tasks[:completed_count]
    pct = calculate_progress(len(completed), len(tasks))

    commits = {}
    for tid in completed:
        commits[tid] = draw(st.text(alphabet="0123456789abcdef", min_size=7, max_size=7))

    return RoadmapMilestone(
        id=mid,
        display_name=f"{mid} {title}".strip(),
        title=title,
        status=status,
        horizon=horizon,
        tasks=tasks,
        completed_tasks=completed,
        progress_pct=pct,
        task_commits=commits,
    )


@settings(max_examples=40, deadline=None)
@given(milestones=st.lists(milestone_strategy(), min_size=0, max_size=8), project_name=st.text(alphabet=string.ascii_letters + " &<>\"'", min_size=1, max_size=30))
def test_property_svg_well_formed_xml(milestones: list[RoadmapMilestone], project_name: str):
    """Generative property invariant: Roadmap SVG is strictly well-formed XML under all input spaces."""
    svg_output = render_roadmap_svg(milestones, project_name=project_name)

    # Must parse without XML syntax errors
    root = ET.fromstring(svg_output)
    assert root.tag.endswith("svg")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg_output

    # Check that width and height attributes exist
    assert "width=" in root.attrib or "viewBox" in root.attrib


@settings(max_examples=40, deadline=None)
@given(
    milestones=st.lists(milestone_strategy(), min_size=0, max_size=8),
    audience=st.text(alphabet=string.ascii_letters + " &<>\"'/<script>", min_size=1, max_size=40),
    granularity=st.text(alphabet=string.ascii_letters + " &<>\"'/<script>", min_size=1, max_size=40),
)
def test_property_html_xss_safety_and_airgap(
    milestones: list[RoadmapMilestone],
    audience: str,
    granularity: str,
):
    """Generative property invariant: HTML presentation contains zero unescaped script injections and zero external dependencies."""
    html_output = render_roadmap_html(milestones, audience=audience, granularity=granularity)

    # Invariant 1: Airgap compliance - zero external network calls
    external_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']https?://', html_output, re.IGNORECASE)
    assert len(external_scripts) == 0, f"Found external scripts: {external_scripts}"

    external_links = re.findall(r'<link\b[^>]*\bhref=["\']https?://', html_output, re.IGNORECASE)
    assert len(external_links) == 0, f"Found external stylesheets: {external_links}"

    # Invariant 2: Script injection safety
    # The only <script> block must be the internal navigation script
    script_blocks = re.findall(r"<script>(.*?)</script>", html_output, re.DOTALL | re.IGNORECASE)
    assert len(script_blocks) == 1
    assert "window.addEventListener('keydown'" in script_blocks[0]

    # Invariant 3: Valid document structure and interactive progress dials
    assert html_output.startswith("<!DOCTYPE html>")
    assert "</html>" in html_output
    assert "<circle" in html_output
    assert "stroke-dashoffset" in html_output


@settings(max_examples=50, deadline=None)
@given(completed=st.integers(min_value=-10, max_value=500), total=st.integers(min_value=-10, max_value=500))
def test_property_progress_percentage_bounds(completed: int, total: int):
    """Generative property invariant: Progress calculations are strictly bounded and safe."""
    pct = calculate_progress(completed, total)
    if total <= 0:
        assert pct == 0.0
    elif completed <= 0:
        assert pct == 0.0
    elif completed >= total:
        assert pct >= 100.0
    else:
        assert 0.0 <= pct <= 100.0
