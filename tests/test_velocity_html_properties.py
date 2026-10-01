"""Hypothesis generative property invariant tests for HTML velocity dashboard (ADR-0009)."""

from __future__ import annotations

import html
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.velocity_dashboard import (
    calculate_bar_width,
    calculate_polyline_points,
    render_forecast_svg,
    render_rescue_clusters_svg,
    render_throughput_svg,
    render_trends_svg,
    render_velocity_html,
)
from spec_ops.backlog.velocity_models import (
    ContributorVelocity,
    FailureCluster,
    RescueAnalytics,
    VelocityReport,
    format_cycle_time,
)


@st.composite
def velocity_report_strategy(draw):
    """Generates synthetic VelocityReport instances with potentially hostile strings."""
    # Strings including potential XSS / script injection attacks
    hostile_text = draw(
        st.sampled_from(
            [
                "14d",
                "<script>alert('xss')</script>",
                "30d <script src='bad.js'>",
                "normal_window",
                "<div>test</div>",
                "quotes \" and ' and &",
            ]
        )
    )

    agent_delivered = draw(st.integers(min_value=0, max_value=500))
    agent_commits = draw(st.integers(min_value=0, max_value=1000))
    agent_vel = round(draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)), 1)
    agent_cycle = round(draw(st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False)), 1)
    agent_pass = round(draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)), 1)

    human_delivered = draw(st.integers(min_value=0, max_value=500))
    human_commits = draw(st.integers(min_value=0, max_value=1000))
    human_vel = round(draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)), 1)
    human_cycle = round(draw(st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False)), 1)
    human_pass = round(draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)), 1)

    hybrid_delivered = agent_delivered + human_delivered
    hybrid_commits = agent_commits + human_commits
    hybrid_vel = round(agent_vel + human_vel, 1)
    hybrid_cycle = round((agent_cycle + human_cycle) / 2.0, 1)
    hybrid_pass = round((agent_pass + human_pass) / 2.0, 1)

    agent_m = ContributorVelocity(
        contributor_class="Agent Workers",
        tasks_delivered=agent_delivered,
        merged_commits=agent_commits,
        tasks_per_week=agent_vel,
        avg_cycle_time_minutes=agent_cycle,
        avg_cycle_time_formatted=format_cycle_time(agent_cycle),
        preflight_pass_rate=agent_pass,
        self_healing_rate=25.0,
        rescue_escalation_rate=12.5,
    )
    human_m = ContributorVelocity(
        contributor_class="Human Developers",
        tasks_delivered=human_delivered,
        merged_commits=human_commits,
        tasks_per_week=human_vel,
        avg_cycle_time_minutes=human_cycle,
        avg_cycle_time_formatted=format_cycle_time(human_cycle),
        preflight_pass_rate=human_pass,
    )
    hybrid_m = ContributorVelocity(
        contributor_class="Hybrid Total",
        tasks_delivered=hybrid_delivered,
        merged_commits=hybrid_commits,
        tasks_per_week=hybrid_vel,
        avg_cycle_time_minutes=hybrid_cycle,
        avg_cycle_time_formatted=format_cycle_time(hybrid_cycle),
        preflight_pass_rate=hybrid_pass,
        self_healing_rate=25.0,
        rescue_escalation_rate=12.5,
    )

    num_clusters = draw(st.integers(min_value=0, max_value=4))
    clusters = []
    for c_i in range(num_clusters):
        c_name = draw(
            st.sampled_from(
                [
                    "Preflight Test Failures",
                    "File Length Violations",
                    "<script>danger</script>",
                    "Mock Rejections",
                ]
            )
        )
        incidents = draw(st.integers(min_value=1, max_value=50))
        clusters.append(
            FailureCluster(
                cluster=c_name,
                incidents=incidents,
                percentage=round(100.0 / max(1, num_clusters), 1),
                top_invariants=["ADR-0004", "<script>inv</script>"],
                sample_reason="Hostile <script>reason</script>",
            )
        )

    rescues = RescueAnalytics(
        total_rescues=sum(c.incidents for c in clusters),
        rescue_burden_ratio=0.15 if clusters else 0.0,
        mean_time_to_unblock_minutes=12.0,
        failure_clusters=clusters,
    )

    return VelocityReport(
        window=hostile_text,
        window_days=14,
        generated_at="2026-09-30T12:00:00Z",
        agent_metrics=agent_m,
        human_metrics=human_m,
        hybrid_total=hybrid_m,
        rescues=rescues,
    )


@given(report=velocity_report_strategy(), remaining_tasks=st.integers(min_value=1, max_value=100))
@settings(max_examples=50)
def test_property_rendered_html_security_and_numeric_integrity(report: VelocityReport, remaining_tasks: int):
    """Asserts generated HTML contains zero raw script tags and embeds numbers accurately."""
    html_out = render_velocity_html(report, remaining_tasks=remaining_tasks)

    # 1. Zero raw script tag injection invariant
    assert "<script" not in html_out.lower(), "Raw script tag detected in rendered HTML"
    assert "onerror=" not in html_out.lower(), "Event handler injection detected"
    assert "onload=" not in html_out.lower(), "Event handler injection detected"

    # 2. Valid document structure
    assert html_out.startswith("<!DOCTYPE html>")
    assert "</html>" in html_out
    assert "<head>" in html_out
    assert "</head>" in html_out
    assert "<body>" in html_out
    assert "</body>" in html_out

    # 3. All SVG elements are well-formed
    svg_opens = len(re.findall(r"<svg\b", html_out))
    svg_closes = len(re.findall(r"</svg>", html_out))
    assert svg_opens == 4
    assert svg_closes == 4

    # 4. Correct numeric embedding
    assert str(report.hybrid_total.tasks_delivered) in html_out
    assert str(report.agent_metrics.tasks_delivered) in html_out
    assert str(report.human_metrics.tasks_delivered) in html_out
    assert str(report.hybrid_total.tasks_per_week) in html_out


@given(
    val=st.floats(min_value=-1000.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
    max_val=st.floats(min_value=-1000.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
    max_w=st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_calculate_bar_width(val: float, max_val: float, max_w: float):
    """Asserts bar width calculation is strictly bounded between 0.0 and max_w."""
    w = calculate_bar_width(val, max_val, max_w)
    assert 0.0 <= w <= max_w
    if val <= 0.0 or max_val <= 0.0:
        assert w == 0.0
