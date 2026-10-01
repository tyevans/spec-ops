"""Unit tests for team delivery velocity engine and cognitive churn heatmap (ADR-0003, ADR-0008)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.release.velocity_heatmap import (
    FileChurnStat,
    TaskLeadTimeStat,
    VelocityHeatmapReport,
    analyze_velocity_and_churn,
    compute_file_churn,
    compute_velocity_metrics,
    extract_completed_tasks,
    generate_velocity_heatmap,
    parse_git_history,
    render_velocity_html,
    render_velocity_json,
    render_velocity_markdown,
)


def test_compute_file_churn_basic(tmp_path: Path):
    test_file = tmp_path / "sample.py"
    test_file.write_text("\n".join(f"# line {i}" for i in range(450)), encoding="utf-8")

    records = [
        {"file_path": "sample.py", "commits": 10, "lines_added": 100, "lines_deleted": 20},
        {"file_path": "other.py", "commits": 1, "lines_added": 5, "lines_deleted": 2},
    ]

    stats = compute_file_churn(records, repo_dir=tmp_path)
    assert len(stats) == 2
    s1 = next(s for s in stats if s.file_path == "sample.py")
    assert s1.commits == 10
    assert s1.lines_added == 100
    assert s1.lines_deleted == 20
    assert s1.total_changes == 120
    assert s1.current_lines == 450
    assert s1.risk_level == "HIGH"
    assert s1.is_warning is True

    s2 = next(s for s in stats if s.file_path == "other.py")
    assert s2.risk_level == "LOW"
    assert s2.is_warning is False


def test_compute_file_churn_critical_and_moderate(tmp_path: Path):
    crit_file = tmp_path / "huge.py"
    crit_file.write_text("\n".join(f"# line {i}" for i in range(520)), encoding="utf-8")

    mod_file = tmp_path / "mod.py"
    mod_file.write_text("\n".join(f"# line {i}" for i in range(260)), encoding="utf-8")

    records = [
        {"file_path": "huge.py", "commits": 2, "lines_added": 10, "lines_deleted": 0},
        {"file_path": "mod.py", "commits": 2, "lines_added": 10, "lines_deleted": 0},
    ]
    stats = compute_file_churn(records, repo_dir=tmp_path)
    assert stats[0].risk_level == "CRITICAL"
    assert stats[0].is_warning is True
    assert stats[1].risk_level == "MODERATE"
    assert stats[1].is_warning is False


def test_compute_velocity_metrics_even_and_odd():
    # Odd lead times
    avg_l, med_l, tp, cad, span = compute_velocity_metrics(
        completed_task_count=3,
        lead_times_days=[1.0, 2.0, 3.0],
        commit_count=10,
        time_span_days=7.0,
    )
    assert avg_l == 2.0
    assert med_l == 2.0
    assert tp == 3.0
    assert cad == round(10 / 7.0, 2)
    assert span == 7.0

    # Even lead times
    avg_l2, med_l2, _, _, _ = compute_velocity_metrics(
        completed_task_count=4,
        lead_times_days=[1.0, 2.0, 4.0, 5.0],
        commit_count=0,
        time_span_days=1.0,
    )
    assert avg_l2 == 3.0
    assert med_l2 == 3.0


def test_compute_velocity_metrics_edge_cases():
    avg_l, med_l, tp, cad, span = compute_velocity_metrics(
        completed_task_count=0,
        lead_times_days=[],
        commit_count=0,
        time_span_days=0.0,
    )
    assert avg_l == 0.0
    assert med_l == 0.0
    assert tp == 0.0
    assert cad == 0.0
    assert span == 0.14


def test_parse_git_history_non_git_repo(tmp_path: Path):
    f_map, commits, dates = parse_git_history(tmp_path)
    assert f_map == {}
    assert commits == 0
    assert dates == []


def test_extract_completed_tasks_empty(tmp_path: Path):
    tasks = extract_completed_tasks(tmp_path)
    assert tasks == []


def test_extract_completed_tasks_with_frontmatter(tmp_path: Path):
    c_dir = tmp_path / "docs" / "project" / "backlog" / "complete"
    c_dir.mkdir(parents=True, exist_ok=True)
    t_file = c_dir / "0005-health-check.md"
    t_file.write_text(
        "---\n"
        "id: '0005'\n"
        "title: Codebase Health Invariants\n"
        "status: Complete\n"
        "created: 2026-09-25\n"
        "completed: 2026-09-28\n"
        "target_bc: health\n"
        "---\n\n"
        "# TASK-0005\n",
        encoding="utf-8",
    )

    tasks = extract_completed_tasks(tmp_path)
    assert len(tasks) == 1
    assert tasks[0].task_id == "0005"
    assert tasks[0].title == "Codebase Health Invariants"
    assert tasks[0].lead_time_days == 3.0
    assert tasks[0].target_bc == "health"


def test_render_velocity_markdown():
    report = VelocityHeatmapReport(
        total_completed_tasks=5,
        total_commits=15,
        throughput_tasks_per_week=10.0,
        avg_lead_time_days=2.5,
        median_lead_time_days=2.0,
        cadence_commits_per_day=3.0,
        time_window_days=5.0,
        high_churn_files=[
            FileChurnStat(
                file_path="src/main.py",
                commits=8,
                lines_added=120,
                lines_deleted=40,
                total_changes=160,
                current_lines=350,
                churn_score=24.0,
                risk_level="MODERATE",
                is_warning=False,
            )
        ],
        complexity_warnings=[
            FileChurnStat(
                file_path="src/legacy.py",
                commits=12,
                lines_added=500,
                lines_deleted=100,
                total_changes=600,
                current_lines=450,
                churn_score=54.0,
                risk_level="HIGH",
                is_warning=True,
            )
        ],
    )

    md = render_velocity_markdown(report)
    assert "# Team Delivery Velocity & Cognitive Churn Heatmap" in md
    assert "| Task Completion Rates (Delivered) | 5 tasks |" in md
    assert "`src/main.py`" in md
    assert "src/legacy.py" in md
    assert "⚠️" in md


def test_render_velocity_html():
    report = VelocityHeatmapReport(
        total_completed_tasks=2,
        total_commits=5,
        throughput_tasks_per_week=4.0,
        avg_lead_time_days=1.0,
        median_lead_time_days=1.0,
        cadence_commits_per_day=2.5,
        time_window_days=2.0,
        churn_stats=[
            FileChurnStat("src/app.py", 3, 50, 10, 60, 100, 9.0, "LOW", False),
        ],
    )
    html_out = render_velocity_html(report)
    assert "<!DOCTYPE html>" in html_out
    assert "Team Delivery Velocity &amp; Cognitive Churn Heatmap" in html_out
    assert "src/app.py" in html_out
    assert "http://" not in html_out
    assert "https://" not in html_out


def test_render_velocity_json():
    report = VelocityHeatmapReport(
        total_completed_tasks=1,
        total_commits=2,
        throughput_tasks_per_week=1.0,
        avg_lead_time_days=0.5,
        median_lead_time_days=0.5,
        cadence_commits_per_day=1.0,
        time_window_days=2.0,
    )
    data = json.loads(render_velocity_json(report))
    assert data["total_completed_tasks"] == 1
    assert data["total_commits"] == 2
    assert "task_stats" in data
    assert "churn_stats" in data


def test_generate_velocity_heatmap_to_file(tmp_path: Path):
    config = SpecOpsConfig(root_dir=tmp_path)
    out_file = tmp_path / "dist" / "velocity.html"

    dest, content = generate_velocity_heatmap(config=config, format_type="html", output_path=out_file)
    assert dest == out_file
    assert out_file.is_file()
    assert "<!DOCTYPE html>" in content
