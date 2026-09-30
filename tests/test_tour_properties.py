"""Hypothesis property tests for visualizer guided tour and discovery sandbox (ADR-0009)."""
from __future__ import annotations

from pathlib import Path
import re

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest
import yaml

from spec_ops.visualizer.tour_script import (
    DEFAULT_TOUR_STEPS,
    generate_uat_receipt,
    get_tour_steps,
    verify_sandbox_prd,
)

KNOWN_PERSONAS = ["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha"]


@st.composite
def valid_idea_prd_strategy(draw):
    """Generates syntactically valid Idea PRD documents."""
    prd_id = draw(st.from_regex(r"PRD-[0-9]{4}", fullmatch=True))
    raw_title = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ", min_size=5, max_size=50))
    title = raw_title.strip() or "Valid Discovery PRD"
    persona = draw(st.sampled_from(KNOWN_PERSONAS))
    raw_problem = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?", min_size=10, max_size=100))
    problem = raw_problem.strip() or "Customer self-service management is blocked"
    outcomes = draw(st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ", min_size=5, max_size=40).map(str.strip).filter(bool), min_size=1, max_size=5))

    fm = {
        "id": prd_id,
        "title": title,
        "status": "Idea",
        "persona": persona,
        "problem_statement": problem,
        "outcomes": outcomes,
    }
    fm_yaml = yaml.safe_dump(fm, default_flow_style=False, sort_keys=False)
    outcomes_body = "\n".join(f"- [ ] {o}" for o in outcomes)

    md = (
        f"---\n"
        f"{fm_yaml}"
        f"---\n\n"
        f"# {title}\n\n"
        f"## Problem Statement\n{problem}\n\n"
        f"## Checkable Outcomes\n{outcomes_body}\n"
    )
    return md, prd_id, title, persona


@settings(max_examples=100)
@given(valid_idea_prd_strategy())
def test_property_valid_idea_prds_always_pass(generated):
    """Property: All syntactically complete Idea PRDs validate deterministically."""
    md, prd_id, title, persona = generated
    res = verify_sandbox_prd(md)

    assert res["valid"] is True
    assert res["badge"] == "PMaC Ready: Your first specification is git-locked!"
    assert len(res["errors"]) == 0
    assert res["metadata"]["id"] == prd_id
    assert res["metadata"]["title"] == title
    assert res["metadata"]["persona"] == persona
    assert res["metadata"]["status"] == "Idea"

    # Determinism invariant
    res2 = verify_sandbox_prd(md)
    assert res2 == res


@settings(max_examples=100)
@given(st.text())
def test_property_arbitrary_string_resilience(random_text):
    """Property: verify_sandbox_prd never raises unhandled exceptions on arbitrary strings."""
    res = verify_sandbox_prd(random_text)
    assert isinstance(res, dict)
    assert "valid" in res
    assert "badge" in res
    assert "errors" in res
    assert "metadata" in res
    assert isinstance(res["valid"], bool)
    assert isinstance(res["errors"], list)
    if not res["valid"]:
        assert res["badge"] == ""
        assert len(res["errors"]) > 0


@settings(max_examples=50)
@given(
    valid_idea_prd_strategy(),
    st.sampled_from(["Accepted", "Draft", "Shipped", "Review", "Proposed"]),
)
def test_property_non_idea_status_always_rejected(generated, non_idea_status):
    """Property: Any status other than 'Idea' must fail sandbox discovery validation."""
    md, _, _, _ = generated
    tampered_md = re.sub(r"status:\s*Idea", f"status: {non_idea_status}", md)
    res = verify_sandbox_prd(tampered_md)

    assert res["valid"] is False
    assert res["badge"] == ""
    assert any("status must be 'idea'" in e.lower() for e in res["errors"])


def test_tutorial_markdown_snippets_syntax_validity():
    """Property: All code blocks in the PM onboarding tutorial parse without syntax errors."""
    tutorial_path = Path("docs/tutorials/02-product-manager-onboarding.md")
    assert tutorial_path.exists()
    content = tutorial_path.read_text(encoding="utf-8")

    # Extract Gherkin blocks
    gherkin_blocks = re.findall(r"```gherkin\s*\n(.*?)\n```", content, re.DOTALL)
    assert len(gherkin_blocks) >= 1
    for block in gherkin_blocks:
        assert "Scenario:" in block
        assert "Given " in block
        assert "When " in block
        assert "Then " in block
