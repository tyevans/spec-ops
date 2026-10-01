"""Hypothesis generative property tests for team delivery velocity and cognitive churn heatmap (ADR-0009)."""

from __future__ import annotations

import json
import math
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.release.velocity_heatmap import (
    FileChurnStat,
    TaskLeadTimeStat,
    VelocityHeatmapReport,
    compute_file_churn,
    compute_velocity_metrics,
    render_velocity_html,
    render_velocity_json,
    render_velocity_markdown,
)


@st.composite
def file_records_strategy(draw):
    """Generates arbitrary file modification records."""
    num_files = draw(st.integers(min_value=0, max_value=25))
    records = []
    for i in range(num_files):
        records.append(
            {
                "file_path": draw(
                    st.sampled_from(
                        [
                            f"src/module_{i}.py",
                            f"docs/explanation/doc_{i}.md",
                            f"tests/test_{i}.py",
                            f"nested/sub/file_{i}.txt",
                        ]
                    )
                ),
                "commits": draw(st.integers(min_value=-5, max_value=500)),
                "lines_added": draw(st.integers(min_value=-10, max_value=10000)),
                "lines_deleted": draw(st.integers(min_value=-10, max_value=5000)),
            }
        )
    return records


@settings(max_examples=50)
@given(
    completed_count=st.integers(min_value=-5, max_value=1000),
    lead_times=st.lists(
        st.one_of(
            st.floats(min_value=-10.0, max_value=365.0),
            st.just(float("nan")),
            st.just(float("inf")),
            st.just(float("-inf")),
        ),
        min_size=0,
        max_size=30,
    ),
    commit_count=st.integers(min_value=-5, max_value=5000),
    time_span_days=st.one_of(
        st.floats(min_value=-10.0, max_value=1000.0),
        st.just(float("nan")),
        st.just(float("inf")),
        st.just(float("-inf")),
    ),
)
def test_velocity_metrics_non_negative_and_finite(
    completed_count: int,
    lead_times: list[float],
    commit_count: int,
    time_span_days: float,
):
    """Asserts that calculated velocity metrics remain non-negative and mathematically valid."""
    avg_l, med_l, throughput, cadence, span = compute_velocity_metrics(
        completed_task_count=completed_count,
        lead_times_days=lead_times,
        commit_count=commit_count,
        time_span_days=time_span_days,
    )
    assert avg_l >= 0.0 and math.isfinite(avg_l)
    assert med_l >= 0.0 and math.isfinite(med_l)
    assert throughput >= 0.0 and math.isfinite(throughput)
    assert cadence >= 0.0 and math.isfinite(cadence)
    assert span >= 0.0 and math.isfinite(span)


@settings(max_examples=50)
@given(records=file_records_strategy())
def test_churn_scores_non_negative_and_valid(records: list[dict]):
    """Asserts that file churn scores and risk classifications are consistent and non-negative."""
    stats = compute_file_churn(records)
    for s in stats:
        assert s.churn_score >= 0.0 and math.isfinite(s.churn_score)
        assert s.total_changes == s.lines_added + s.lines_deleted
        assert s.commits >= 0
        assert s.lines_added >= 0
        assert s.lines_deleted >= 0
        assert s.risk_level in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert isinstance(s.is_warning, bool)


@settings(max_examples=30)
@given(
    records=file_records_strategy(),
    completed_count=st.integers(min_value=0, max_value=100),
    commit_count=st.integers(min_value=0, max_value=200),
)
def test_rendered_report_invariants(records: list[dict], completed_count: int, commit_count: int):
    """Asserts that renderers produce valid markdown, HTML with no CDNs, and valid JSON."""
    churn_stats = compute_file_churn(records)
    report = VelocityHeatmapReport(
        total_completed_tasks=completed_count,
        total_commits=commit_count,
        throughput_tasks_per_week=round(completed_count / 1.0, 2),
        avg_lead_time_days=1.5,
        median_lead_time_days=1.0,
        cadence_commits_per_day=round(commit_count / 1.0, 2),
        time_window_days=1.0,
        churn_stats=churn_stats,
        high_churn_files=[f for f in churn_stats[:5] if f.churn_score > 0],
        complexity_warnings=[f for f in churn_stats if f.is_warning],
    )

    # Markdown verification
    md = render_velocity_markdown(report)
    assert "# Team Delivery Velocity & Cognitive Churn Heatmap" in md
    assert "## Delivery Velocity Metrics" in md

    # HTML verification (self-contained, no external CDN dependencies)
    html_out = render_velocity_html(report)
    assert "<!DOCTYPE html>" in html_out
    assert "<html" in html_out and "</html>" in html_out
    assert "http://" not in html_out
    assert "https://" not in html_out

    # JSON verification
    json_out = render_velocity_json(report)
    parsed = json.loads(json_out)
    assert parsed["total_completed_tasks"] == completed_count
    assert parsed["total_commits"] == commit_count
    assert "churn_stats" in parsed
