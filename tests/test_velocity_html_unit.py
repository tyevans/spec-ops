"""Unit tests for standalone HTML velocity dashboard and SVG chart generation."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from spec_ops.backlog.velocity_dashboard import (
    calculate_bar_width,
    calculate_polyline_points,
    export_velocity_dashboard,
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
)
from spec_ops.cli.main import main


@pytest.fixture
def sample_velocity_report() -> VelocityReport:
    agent = ContributorVelocity(
        contributor_class="Agent Workers",
        tasks_delivered=18,
        merged_commits=24,
        tasks_per_week=9.0,
        avg_cycle_time_minutes=4.2,
        avg_cycle_time_formatted="4.2 minutes",
        preflight_pass_rate=85.0,
        self_healing_rate=25.0,
        rescue_escalation_rate=12.5,
    )
    human = ContributorVelocity(
        contributor_class="Human Developers",
        tasks_delivered=6,
        merged_commits=8,
        tasks_per_week=3.0,
        avg_cycle_time_minutes=228.0,
        avg_cycle_time_formatted="3.8 hours",
        preflight_pass_rate=92.0,
    )
    hybrid = ContributorVelocity(
        contributor_class="Hybrid Total",
        tasks_delivered=24,
        merged_commits=32,
        tasks_per_week=12.0,
        avg_cycle_time_minutes=42.1,
        avg_cycle_time_formatted="42.1 minutes",
        preflight_pass_rate=87.5,
        self_healing_rate=25.0,
        rescue_escalation_rate=12.5,
    )
    rescues = RescueAnalytics(
        total_rescues=2,
        rescue_burden_ratio=0.125,
        mean_time_to_unblock_minutes=15.0,
        failure_clusters=[
            FailureCluster(
                cluster="Preflight Test Failures",
                incidents=2,
                percentage=100.0,
                top_invariants=["ADR-0004"],
                sample_reason="Assertion failed in preflight",
            )
        ],
    )
    return VelocityReport(
        window="14d",
        window_days=14,
        generated_at="2026-09-30T12:00:00Z",
        agent_metrics=agent,
        human_metrics=human,
        hybrid_total=hybrid,
        rescues=rescues,
    )


def test_calculate_bar_width():
    assert calculate_bar_width(0, 100, 300) == 0.0
    assert calculate_bar_width(-10, 100, 300) == 0.0
    assert calculate_bar_width(50, 0, 300) == 0.0
    assert calculate_bar_width(50, -5, 300) == 0.0
    assert calculate_bar_width(50, 100, 300) == 150.0
    assert calculate_bar_width(100, 100, 300) == 300.0
    assert calculate_bar_width(150, 100, 300) == 300.0


def test_calculate_polyline_points():
    assert calculate_polyline_points([], 100) == ""
    assert calculate_polyline_points([10.0], 100, pad_x=70, pad_y=25, height=120) == "70,145"

    pts = calculate_polyline_points([0.0, 50.0, 100.0], 100.0, width=200.0, height=100.0, pad_x=50.0, pad_y=20.0)
    # x: 50.0, 150.0, 250.0; y: 120.0, 70.0, 20.0
    assert "50.0,120.0" in pts
    assert "150.0,70.0" in pts
    assert "250.0,20.0" in pts


def test_render_trends_svg():
    svg = render_trends_svg(9.0, 3.0, 12.0)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "polyline" in svg
    assert "#a855f7" in svg
    assert "#38bdf8" in svg
    assert "#10b981" in svg


def test_render_throughput_svg():
    svg = render_throughput_svg(18, 6, 24)
    assert "<svg" in svg
    assert "18 tasks" in svg
    assert "6 tasks" in svg
    assert "24 tasks" in svg


def test_render_rescue_clusters_svg_with_rescues():
    clusters = [
        FailureCluster(
            cluster="Preflight Test Failures",
            incidents=3,
            percentage=75.0,
            top_invariants=["ADR-0004"],
            sample_reason="Assertion error",
        ),
        FailureCluster(
            cluster="File Length Violations",
            incidents=1,
            percentage=25.0,
            top_invariants=["ADR-0002"],
            sample_reason="File over 500 lines",
        ),
    ]
    svg = render_rescue_clusters_svg(clusters, 4)
    assert "Preflight Test Failures" in svg
    assert "File Length Violations" in svg
    assert "ADR-0004" in svg
    assert "ADR-0002" in svg


def test_render_rescue_clusters_svg_zero_rescues():
    svg = render_rescue_clusters_svg([], 0)
    assert "Zero Human Rescues Required" in svg
    assert "100% Autonomous Worker Preflight" in svg


def test_render_forecast_svg():
    svg = render_forecast_svg(12.0, remaining_tasks=24)
    assert "Projected Delivery:" in svg
    assert "Target (24 tasks)" in svg


def test_render_velocity_html(sample_velocity_report):
    html = render_velocity_html(sample_velocity_report, remaining_tasks=24)
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "Hybrid Delivery Velocity" in html
    assert "12.0" in html
    assert "4.2 minutes" in html
    assert "3.8 hours" in html
    assert "Preflight Test Failures" in html
    # Standalone zero-dependency checks
    assert "<script" not in html
    assert "http://" not in html
    assert "https://" not in html
    assert "<link rel=\"stylesheet\"" not in html


def test_export_velocity_dashboard(tmp_path: Path, sample_velocity_report):
    out_file = tmp_path / "reports" / "custom-velocity.html"
    dest = export_velocity_dashboard(sample_velocity_report, output_path=out_file)
    assert dest == out_file
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Hybrid Delivery Velocity" in content


def test_export_velocity_dashboard_default_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_velocity_report):
    monkeypatch.chdir(tmp_path)
    dest = export_velocity_dashboard(sample_velocity_report, repo_root=tmp_path)
    expected = tmp_path / "dist" / "velocity-report.html"
    assert dest == expected
    assert expected.exists()


def test_cli_report_velocity_export_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "specops.toml").write_text("[project]\nname = 'Test'\n", encoding="utf-8")

    out_file = tmp_path / "dist" / "my-velocity.html"
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            main(["report", "velocity", "--export", "html", "--out", str(out_file)])
        except SystemExit as exc:
            assert exc.code == 0

    assert out_file.exists()
    assert "Exported velocity report" in buf.getvalue()
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
