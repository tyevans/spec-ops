"""Generative property invariant tests for Persona Customer Journey Map Visualizer."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.persona_models import PersonaProfile
from spec_ops.prd.journey_map import CustomerJourneyReport, JourneyMapEngine

# Strategy for Persona Profile
persona_names_strategy = st.sampled_from(["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha", "Quinn", "Sam"])
roles_strategy = st.sampled_from([
    "The Agentic Architect", "The AI Lead", "The Autonomous Agent",
    "The IC Developer", "The Product Manager", "The Security Officer",
])
pain_point_text_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")),
    min_size=1,
    max_size=60,
)


@st.composite
def persona_profiles_strategy(draw: Any) -> list[PersonaProfile]:
    names = draw(st.lists(persona_names_strategy, min_size=0, max_size=6, unique=True))
    profiles = []
    for idx, name in enumerate(names, start=1):
        role = draw(roles_strategy)
        pain_points = draw(st.lists(pain_point_text_strategy, min_size=0, max_size=6))
        profiles.append(
            PersonaProfile(
                name=name,
                role=role,
                pain_points=pain_points,
                index=idx,
            )
        )
    return profiles


@st.composite
def stories_strategy(draw: Any) -> list[dict[str, Any]]:
    n_stories = draw(st.integers(min_value=0, max_value=12))
    stories = []
    statuses = ["Accepted", "Shipped", "Complete", "Proposed", "Refined", "Draft"]
    for i in range(n_stories):
        p_name = draw(st.sampled_from(["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha", "Unknown"]))
        status = draw(st.sampled_from(statuses))
        pain_point_ref = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=8), st.text(min_size=3, max_size=20)))
        stories.append({
            "id": f"US-{i+1:04d}",
            "title": f"User Story {i+1}",
            "persona": p_name,
            "status": status,
            "governing_prd": "PRD-0001",
            "pain_point": pain_point_ref,
            "pain_points": [pain_point_ref] if pain_point_ref is not None else [],
            "content": f"Story addressing pain point for {p_name}.",
        })
    return stories


class TestJourneyMapProperties:
    """Hypothesis invariant verification for Customer Journey Map and coverage computation."""

    @given(personas=persona_profiles_strategy(), stories=stories_strategy())
    @settings(max_examples=100)
    def test_journey_coverage_strictly_bounded(
        self, personas: list[PersonaProfile], stories: list[dict[str, Any]]
    ) -> None:
        """Asserts journey coverage percentages are bounded strictly between 0.0% and 100.0%."""
        engine = JourneyMapEngine()
        report = engine.correlate(personas_list=personas, stories_list=stories, prds_list=[])

        # Overall coverage invariants
        assert math.isfinite(report.overall_coverage_percentage)
        assert 0.0 <= report.overall_coverage_percentage <= 100.0
        assert 0 <= report.addressed_pain_points <= report.total_pain_points
        assert report.addressed_pain_points + report.unaddressed_pain_points == report.total_pain_points
        assert report.total_personas == len(personas)

        # Per-persona invariants
        for p_map in report.personas:
            assert math.isfinite(p_map.coverage_percentage)
            assert 0.0 <= p_map.coverage_percentage <= 100.0
            assert 0 <= p_map.addressed_pain_points <= p_map.total_pain_points
            assert p_map.addressed_pain_points + p_map.unaddressed_pain_points == p_map.total_pain_points
            assert len(p_map.pain_points) == p_map.total_pain_points

            # Persona traceability invariant: every pain point must trace to canonical persona ID
            for pt in p_map.pain_points:
                assert pt.persona_id == p_map.persona_id
                assert pt.persona_name == p_map.persona_name
                assert isinstance(pt.is_addressed, bool)

    @given(
        personas=persona_profiles_strategy(),
        stories=stories_strategy(),
        filter_query=st.text(min_size=0, max_size=15),
    )
    @settings(max_examples=60)
    def test_arbitrary_filter_preserves_bounds_and_safety(
        self,
        personas: list[PersonaProfile],
        stories: list[dict[str, Any]],
        filter_query: str,
    ) -> None:
        """Asserts arbitrary filter queries never cause numerical errors or boundary violations."""
        engine = JourneyMapEngine()
        report = engine.correlate(
            persona_filter=filter_query if filter_query.strip() else None,
            personas_list=personas,
            stories_list=stories,
            prds_list=[],
        )

        assert math.isfinite(report.overall_coverage_percentage)
        assert 0.0 <= report.overall_coverage_percentage <= 100.0
        assert report.total_personas <= len(personas)
        for p in report.personas:
            assert 0.0 <= p.coverage_percentage <= 100.0
            assert p.addressed_pain_points <= p.total_pain_points

    @given(personas=persona_profiles_strategy(), stories=stories_strategy())
    @settings(max_examples=40)
    def test_json_and_html_serialization_integrity(
        self, personas: list[PersonaProfile], stories: list[dict[str, Any]]
    ) -> None:
        """Asserts report serializes cleanly to valid JSON and HTML without errors."""
        engine = JourneyMapEngine()
        report = engine.correlate(personas_list=personas, stories_list=stories, prds_list=[])

        # JSON integrity
        json_output = engine.format_json(report)
        parsed = json.loads(json_output)
        assert "summary" in parsed
        assert "personas" in parsed
        assert parsed["summary"]["total_pain_points"] == report.total_pain_points
        assert parsed["summary"]["overall_coverage_percentage"] == round(report.overall_coverage_percentage, 1)

        # HTML integrity
        html_output = engine.generate_html(report)
        assert "<!DOCTYPE html>" in html_output
        assert "spec-ops:journey-coverage" in html_output
        assert "http://" not in html_output and "https://" not in html_output  # Zero external CDN
