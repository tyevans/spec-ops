"""Unit tests for Customer Journey Map and Pain Point Matrix visualizer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.persona_models import PersonaProfile
from spec_ops.prd.journey_map import (
    CustomerJourneyReport,
    JourneyMapEngine,
    PainPointRecord,
    PersonaJourneyMap,
    handle_journey_command,
)


@pytest.fixture
def sample_personas() -> list[PersonaProfile]:
    return [
        PersonaProfile(
            name="Taylor",
            role="The Product Manager",
            pain_points=[
                "High friction and terminal-command intimidation when collaborating on git-based specifications.",
                "Disconnect between green CI test runs and actual customer-ready business value.",
                "Double-entry overhead translating between git repositories and executive roadmaps.",
            ],
            index=1,
        ),
        PersonaProfile(
            name="Alex",
            role="The Agentic Systems Architect",
            pain_points=[
                "Context rot when specifications stored in external SaaS tools drift from git code.",
                "Frustrating merge conflicts when multiple autonomous agents edit backlog files in parallel.",
            ],
            index=2,
        ),
    ]


@pytest.fixture
def sample_stories() -> list[dict[str, any]]:
    return [
        {
            "id": "US-0043",
            "title": "Interactive Web-Based PRD Studio",
            "persona": "Taylor (The Product Manager)",
            "status": "Accepted",
            "governing_prd": "PRD-0003",
            "pain_point": 1,
            "pain_points": [],
            "content": "Eliminates terminal-command intimidation.",
        },
        {
            "id": "US-0046",
            "title": "Customer-Ready UAT Verification Matrix",
            "persona": "Taylor",
            "status": "Accepted",
            "governing_prd": "PRD-0003",
            "pain_point": None,
            "pain_points": ["Disconnect between green CI test runs and actual customer-ready business value."],
            "content": "Verifies customer acceptance.",
        },
        {
            "id": "US-0081",
            "title": "Concurrent Multi-Worker Execution with Worktree Auto-Rebase",
            "persona": "Alex",
            "status": "Accepted",
            "governing_prd": "PRD-0004",
            "pain_point": None,
            "pain_points": [],
            "content": "Resolves frustrating merge conflicts when multiple autonomous agents edit backlog in parallel.",
        },
        {
            "id": "US-0099",
            "title": "Unapproved Feature Draft",
            "persona": "Taylor",
            "status": "Proposed",  # Proposed status should not count as addressed
            "governing_prd": "PRD-0003",
            "pain_point": 3,
            "pain_points": [],
            "content": "Draft feature.",
        },
    ]


def test_correlate_computes_exact_metrics(sample_personas: list[PersonaProfile], sample_stories: list[dict[str, any]]) -> None:
    engine = JourneyMapEngine()
    report = engine.correlate(personas_list=sample_personas, stories_list=sample_stories, prds_list=[])

    assert report.total_personas == 2
    assert report.total_pain_points == 5
    assert report.addressed_pain_points == 3  # Taylor points 1 & 2, Alex point 2
    assert report.unaddressed_pain_points == 2
    assert report.overall_coverage_percentage == 60.0

    taylor_map = next(p for p in report.personas if p.persona_name == "Taylor")
    assert taylor_map.total_pain_points == 3
    assert taylor_map.addressed_pain_points == 2
    assert taylor_map.unaddressed_pain_points == 1
    assert taylor_map.coverage_percentage == pytest.approx(66.7, rel=1e-2)

    alex_map = next(p for p in report.personas if p.persona_name == "Alex")
    assert alex_map.total_pain_points == 2
    assert alex_map.addressed_pain_points == 1
    assert alex_map.unaddressed_pain_points == 1
    assert alex_map.coverage_percentage == 50.0


def test_persona_filter_exact_and_partial(sample_personas: list[PersonaProfile], sample_stories: list[dict[str, any]]) -> None:
    engine = JourneyMapEngine()

    # Exact filter
    report_taylor = engine.correlate(persona_filter="Taylor", personas_list=sample_personas, stories_list=sample_stories)
    assert report_taylor.total_personas == 1
    assert report_taylor.personas[0].persona_name == "Taylor"
    assert report_taylor.overall_coverage_percentage == pytest.approx(66.7, rel=1e-2)

    # Lowercase ID filter
    report_alex = engine.correlate(persona_filter="alex", personas_list=sample_personas, stories_list=sample_stories)
    assert report_alex.total_personas == 1
    assert report_alex.personas[0].persona_name == "Alex"
    assert report_alex.overall_coverage_percentage == 50.0

    # Non-existent filter
    report_none = engine.correlate(persona_filter="NonExistent", personas_list=sample_personas, stories_list=sample_stories)
    assert report_none.total_personas == 0
    assert report_none.total_pain_points == 0
    assert report_none.overall_coverage_percentage == 100.0


def test_proposed_or_draft_stories_do_not_address_pain_points(sample_personas: list[PersonaProfile]) -> None:
    engine = JourneyMapEngine()
    stories = [
        {
            "id": "US-0099",
            "title": "Draft Story",
            "persona": "Taylor",
            "status": "Proposed",
            "governing_prd": "PRD-0003",
            "pain_point": 1,
            "pain_points": [],
            "content": "WIP",
        }
    ]
    report = engine.correlate(persona_filter="Taylor", personas_list=sample_personas, stories_list=stories)
    assert report.personas[0].addressed_pain_points == 0
    assert report.personas[0].coverage_percentage == 0.0
    assert not report.personas[0].pain_points[0].is_addressed


def test_zero_pain_points_persona_edge_case() -> None:
    engine = JourneyMapEngine()
    empty_persona = [PersonaProfile(name="EmptyPersona", role="Tester", pain_points=[], index=1)]
    report = engine.correlate(personas_list=empty_persona, stories_list=[])

    assert report.total_personas == 1
    assert report.total_pain_points == 0
    assert report.addressed_pain_points == 0
    assert report.overall_coverage_percentage == 100.0
    assert report.personas[0].coverage_percentage == 100.0


def test_format_markdown_output(sample_personas: list[PersonaProfile], sample_stories: list[dict[str, any]]) -> None:
    engine = JourneyMapEngine()
    report = engine.correlate(personas_list=sample_personas, stories_list=sample_stories)
    md = engine.format_markdown(report)

    assert "=== SpecOps Persona Customer Journey Map & Pain Point Matrix ===" in md
    assert "Overall Journey Coverage: 60.0%" in md
    assert "## Persona: Taylor — The Product Manager" in md
    assert "✅ Addressed" in md
    assert "⚠️ Unaddressed" in md
    assert "US-0043" in md


def test_format_json_output(sample_personas: list[PersonaProfile], sample_stories: list[dict[str, any]]) -> None:
    engine = JourneyMapEngine()
    report = engine.correlate(personas_list=sample_personas, stories_list=sample_stories)
    raw_json = engine.format_json(report)
    data = json.loads(raw_json)

    assert "summary" in data
    assert data["summary"]["total_personas"] == 2
    assert data["summary"]["total_pain_points"] == 5
    assert data["summary"]["addressed_pain_points"] == 3
    assert data["summary"]["overall_coverage_percentage"] == 60.0
    assert len(data["personas"]) == 2


def test_generate_html_zero_dependencies(sample_personas: list[PersonaProfile], sample_stories: list[dict[str, any]]) -> None:
    engine = JourneyMapEngine()
    report = engine.correlate(personas_list=sample_personas, stories_list=sample_stories)
    html_output = engine.generate_html(report)

    assert "<!DOCTYPE html>" in html_output
    assert 'meta name="spec-ops:report-type" content="customer-journey-map"' in html_output
    assert 'meta name="spec-ops:journey-coverage" content="60.0"' in html_output
    assert 'meta name="spec-ops:total-pain-points" content="5"' in html_output
    assert "http://" not in html_output
    assert "https://" not in html_output
    assert "<script>" in html_output


def test_export_html_to_custom_path(tmp_path: Path, sample_personas: list[PersonaProfile], sample_stories: list[dict[str, any]]) -> None:
    engine = JourneyMapEngine(repo_root=tmp_path)
    report = engine.correlate(personas_list=sample_personas, stories_list=sample_stories)
    dest = tmp_path / "custom" / "journey.html"
    exported_path = engine.export_html(report, output_path=dest)

    assert exported_path == dest
    assert dest.is_file()
    assert "<!DOCTYPE html>" in dest.read_text(encoding="utf-8")


def test_handle_journey_command_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    config = SpecOpsConfig(root_dir=tmp_path)

    # 1. Test markdown format
    ret = handle_journey_command(config, fmt="markdown")
    assert ret == 0
    captured = capsys.readouterr()
    assert "SpecOps Persona Customer Journey Map" in captured.out

    # 2. Test json format
    ret_json = handle_journey_command(config, fmt="json")
    assert ret_json == 0
    captured_json = capsys.readouterr()
    parsed = json.loads(captured_json.out)
    assert "summary" in parsed

    # 3. Test html export
    out_file = tmp_path / "test-journey.html"
    ret_html = handle_journey_command(config, fmt="html", output=str(out_file))
    assert ret_html == 0
    assert out_file.is_file()
