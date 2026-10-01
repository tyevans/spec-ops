"""Generative property-based tests for BDD Scenario Coverage Matrix invariants using Hypothesis (ADR-0009)."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.bdd_matrix import (
    BDDCoverageAuditor,
    BDDCoverageMatrix,
    BDDScenarioItem,
    StoryCoverageReport,
    normalize_story_id,
)

safe_text = st.text(
    alphabet=st.characters(categories=["Lu", "Ll", "Nd", "Zs"]),
    min_size=1,
    max_size=50,
).map(lambda s: s.strip()).filter(lambda s: len(s) > 0 and "\n" not in s)


@st.composite
def gherkin_scenario_strategy(draw):
    title = draw(safe_text)
    keyword = draw(st.sampled_from(["Scenario", "Scenario Outline"]))
    tag = draw(st.one_of(st.none(), safe_text.map(lambda t: f"@{t.replace(' ', '_')}")))
    steps = [
        f"  Given condition {draw(safe_text)}",
        f"  When action {draw(safe_text)}",
        f"  Then outcome {draw(safe_text)}",
    ]
    block = []
    if tag:
        block.append(tag)
    block.append(f"{keyword}: {title}")
    block.extend(steps)
    return title, "\n".join(block)


@st.composite
def gherkin_document_strategy(draw):
    scenarios = draw(st.lists(gherkin_scenario_strategy(), min_size=0, max_size=10))
    expected_titles = []
    blocks = ["# Generated Story", "", "## Acceptance Criteria", ""]
    for title, block in scenarios:
        clean_title = title.strip().rstrip(":")
        if clean_title and clean_title not in expected_titles:
            expected_titles.append(clean_title)
        blocks.append("```gherkin")
        blocks.append(block)
        blocks.append("```")
        blocks.append("")
    return expected_titles, "\n".join(blocks)


@given(doc_data=gherkin_document_strategy())
@settings(max_examples=50)
def test_scenario_extraction_invariants(doc_data):
    """Property: For any syntactically valid Gherkin story content, scenario extraction

    is deterministic, has no duplicate entries, contains no empty items, and never crashes.
    """
    expected_titles, markdown = doc_data

    first_extraction = BDDCoverageAuditor.extract_scenarios_from_content(markdown)
    second_extraction = BDDCoverageAuditor.extract_scenarios_from_content(markdown)

    assert first_extraction == second_extraction, "Extraction must be strictly deterministic"
    assert len(first_extraction) == len(set(first_extraction)), "Extracted titles must not contain duplicates"
    assert all(len(t) > 0 for t in first_extraction), "No empty titles allowed"
    assert first_extraction == expected_titles


@given(
    story_id=st.one_of(
        st.integers(min_value=1, max_value=9999).map(lambda n: f"{n}"),
        st.integers(min_value=1, max_value=9999).map(lambda n: f"US-{n:04d}"),
        st.text(min_size=1, max_size=10).filter(lambda s: s.isalnum()),
    )
)
@settings(max_examples=50)
def test_normalize_story_id_invariants(story_id: str):
    """Property: normalize_story_id produces uppercase deterministic canonical prefixes."""
    norm1 = normalize_story_id(story_id)
    norm2 = normalize_story_id(story_id)

    assert norm1 == norm2
    assert norm1.startswith("US-")
    assert norm1.isupper()


@given(
    total=st.integers(min_value=0, max_value=100),
    covered_offset=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=50)
def test_matrix_coverage_pct_invariants(total: int, covered_offset: int):
    """Property: Coverage percentages are bounded within [0.0, 100.0] and serialization roundtrips cleanly."""
    covered = min(total, covered_offset)
    overall_pct = round((covered / total) * 100.0, 1) if total > 0 else 100.0

    report = StoryCoverageReport(
        story_id="US-9999",
        story_title="Generated",
        target_bc="core",
        total_scenarios=total,
        covered_scenarios=covered,
        coverage_pct=overall_pct,
        scenarios=[
            BDDScenarioItem(
                story_id="US-9999",
                story_title="Generated",
                scenario_title=f"Scenario {i}",
                is_covered=(i < covered),
                test_binding="test.py" if i < covered else None,
                target_bc="core",
            )
            for i in range(total)
        ],
    )

    matrix = BDDCoverageMatrix(
        stories=[report],
        total_stories=1,
        total_scenarios=total,
        covered_scenarios=covered,
        overall_coverage_pct=overall_pct,
    )

    assert 0.0 <= matrix.overall_coverage_pct <= 100.0
    data = matrix.to_dict()
    assert data["total_scenarios"] == total
    assert data["covered_scenarios"] == covered

    serialized = json.dumps(data)
    deserialized = json.loads(serialized)
    assert deserialized["total_scenarios"] == total
    assert deserialized["covered_scenarios"] == covered

    summary = matrix.summary()
    assert "SpecOps BDD Scenario Coverage Matrix" in summary
