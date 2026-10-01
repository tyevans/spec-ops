"""Hypothesis generative property tests for INVEST decomposition and DoR contract synthesis (ADR-0009)."""

from __future__ import annotations

from pathlib import Path
import string

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from spec_ops.backlog.dor_gate import audit_task_health
from spec_ops.backlog.dor_synthesizer import DORSynthesizer
from spec_ops.config.loader import load_config
from spec_ops.core.parser import parse_task
from spec_ops.prd.invest_decomposer import INVESTDecomposer
from spec_ops.scaffold.init import init_project

SAFE_CHARS = string.ascii_letters + " "
SAFE_SLUG = string.ascii_letters + string.digits + "_-"


@st.composite
def prd_specifications(draw):
    title = draw(st.text(alphabet=SAFE_CHARS, min_size=5, max_size=40)).strip()
    if not title:
        title = "Core Feature Engine"
    component = draw(st.sampled_from(["worker", "core", "orchestrator", "security", "backlog"]))
    num_outcomes = draw(st.integers(min_value=1, max_value=4))

    outcomes = []
    for _ in range(num_outcomes):
        text = draw(st.text(alphabet=SAFE_CHARS, min_size=5, max_size=50)).strip()
        if not text:
            text = "Deterministic contract validation"
        is_spike = draw(st.booleans())
        if is_spike:
            text = f"Architectural spike and benchmark prototype for {text}"
        outcomes.append(text)

    return {
        "title": title,
        "component": component,
        "outcomes": outcomes,
    }


@pytest.fixture(scope="module")
def property_test_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("invest_properties")
    init_project(root, name="InvestProperties")
    config = load_config(root_dir=root)

    # Scaffold baseline accepted PRD and story
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0001-baseline.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Baseline PRD\n"
        "status: Accepted\n"
        "target_persona: Jordan (The AI-Native Engineering Lead)\n"
        "component: core\n"
        "---\n"
        "# PRD-0001 — Baseline PRD\n\n"
        "## Checkable Outcomes\n"
        "1. Baseline outcome.\n",
        encoding="utf-8",
    )

    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0001-baseline.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Baseline User Story\n"
        "status: Accepted\n"
        "persona: Jordan (The AI-Native Engineering Lead)\n"
        "governing_prd: PRD-0001\n"
        "---\n"
        "# US-0001 — Baseline Story\n\n"
        "## Acceptance Criteria\n\n"
        "```gherkin\n"
        "Scenario: Baseline\n"
        "  Given a\n  When b\n  Then c\n"
        "```\n",
        encoding="utf-8",
    )

    return {"root": root, "config": config}


@settings(max_examples=25, deadline=None)
@given(spec=prd_specifications())
def test_invest_decomposer_generative_invariants(property_test_env, spec):
    root = property_test_env["root"]
    config = property_test_env["config"]

    # Write PRD
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-9999-property-gen.md"

    outcomes_block = "\n".join(f"{i+1}. {o}" for i, o in enumerate(spec["outcomes"]))
    prd_content = f"""---
id: '9999'
title: "{spec['title']}"
status: Accepted
target_persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
component: {spec['component']}
---

# PRD-9999 — {spec['title']}

## Checkable Outcomes
{outcomes_block}
"""
    prd_file.write_text(prd_content, encoding="utf-8")

    out_dir = root / "temp_out_invest"
    out_dir.mkdir(parents=True, exist_ok=True)

    decomposer = INVESTDecomposer(config)
    results = decomposer.decompose("PRD-9999", output_dir=out_dir)

    assert len(results) >= len(spec["outcomes"])

    for item in results:
        task_path = item["path"]
        assert task_path.is_file()
        parsed = parse_task(task_path)
        assert parsed is not None

        # Verify invariant: Every generated slice or spike satisfies Definition of Ready
        report = audit_task_health(parsed, config, strict=True)
        assert report.is_ready is True, f"Generated task failed DoR: {report.errors}"

        # Verify invariant: Scoped to expected bounded context
        assert parsed.target_bc == spec["component"]

        # Verify invariant: Content contains Gherkin scenarios and property testing hooks
        text = task_path.read_text(encoding="utf-8")
        assert "## Acceptance Criteria" in text
        assert "```gherkin" in text
        assert "## Mutation Testing Scope" in text
        assert "## Hypothesis Invariant Properties" in text


@settings(max_examples=25, deadline=None)
@given(
    has_bc=st.booleans(),
    has_prds=st.booleans(),
    has_adrs=st.booleans(),
    has_gherkin=st.booleans(),
    has_mutation=st.booleans(),
    has_hypothesis=st.booleans(),
    has_persona=st.booleans(),
    title_suffix=st.text(alphabet=SAFE_CHARS, min_size=3, max_size=20),
)
def test_dor_synthesizer_generative_completeness(
    property_test_env,
    has_bc,
    has_prds,
    has_adrs,
    has_gherkin,
    has_mutation,
    has_hypothesis,
    has_persona,
    title_suffix,
):
    root = property_test_env["root"]
    config = property_test_env["config"]

    raw_title = f"Synthesizer Property Test {title_suffix.strip() or 'Default'}"
    fm_lines = ["---", "id: '8888'", f'title: "{raw_title}"', "status: Proposed"]
    if has_bc:
        fm_lines.append("target_bc: core")
    if has_prds:
        fm_lines.append("governing_prds:\n  - PRD-0001")
    if has_adrs:
        fm_lines.append("governing_adrs:\n  - ADR-0001\n  - ADR-0002")
    if has_persona:
        fm_lines.append("persona: Jordan (The AI-Native Engineering Lead)")
    fm_lines.append("---")

    body_sections = [f"# TASK-8888: {raw_title}", "## Summary", "Testing generative synthesis."]
    if has_gherkin:
        body_sections.append("## Acceptance Criteria\n\n```gherkin\nScenario: Test\nGiven a\nWhen b\nThen c\n```")
    if has_mutation:
        body_sections.append("## Mutation Testing Scope\n- mutmut target >=80%")
    if has_hypothesis:
        body_sections.append("## Hypothesis Invariant Properties\n- @given(...) invariant check")

    raw_content = "\n".join(fm_lines) + "\n\n" + "\n\n".join(body_sections) + "\n"

    target_file = root / "docs" / "project" / "backlog" / "proposed" / "8888-prop-test.md"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(raw_content, encoding="utf-8")

    synthesizer = DORSynthesizer(config)
    ok, msg, details = synthesizer.synthesize("TASK-8888")

    assert ok is True
    parsed_after = parse_task(target_file)
    assert parsed_after is not None

    # Invariant: Any arbitrary combination of missing fields is synthesized to satisfy 100% DoR
    report = audit_task_health(parsed_after, config, strict=True)
    assert report.is_ready is True, f"Failed DoR synthesis on combination: {report.errors}"
