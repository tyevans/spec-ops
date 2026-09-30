"""Comprehensive unit tests for tour_script.py to maximize mutmut mutant kill rate."""
from __future__ import annotations

import pytest

from spec_ops.visualizer.tour_script import (
    DEFAULT_TOUR_STEPS,
    TourStep,
    generate_uat_receipt,
    get_tour_steps,
    verify_sandbox_prd,
)


def test_verify_sandbox_prd_empty_or_non_string():
    """Verify empty or non-string inputs fail gracefully."""
    for val in [None, 123, [], {}, "", "   \n\t  "]:
        res = verify_sandbox_prd(val)  # type: ignore
        assert res["valid"] is False
        assert res["badge"] == ""
        assert res["errors"] == ["PRD content cannot be empty."]
        assert res["metadata"] == {}


def test_verify_sandbox_prd_missing_opening_delimiter():
    """Verify frontmatter without starting delimiter fails."""
    md = "title: My PRD\n---\nBody text"
    res = verify_sandbox_prd(md)
    assert res["valid"] is False
    assert res["errors"] == ["Missing YAML frontmatter delimiter '---' at start."]


def test_verify_sandbox_prd_missing_closing_delimiter():
    """Verify frontmatter without closing delimiter fails."""
    md = "---\ntitle: My PRD\nstatus: Idea\nNo closing delimiter"
    res = verify_sandbox_prd(md)
    assert res["valid"] is False
    assert res["errors"] == ["Missing closing YAML frontmatter delimiter '---'."]


def test_verify_sandbox_prd_malformed_yaml():
    """Verify syntax error in frontmatter YAML fails."""
    md = "---\n: : : not valid yaml\n---\n## Body"
    res = verify_sandbox_prd(md)
    assert res["valid"] is False
    assert any("Malformed YAML frontmatter:" in e for e in res["errors"])


def test_verify_sandbox_prd_non_mapping_yaml():
    """Verify YAML that parses to a list or scalar fails."""
    md_list = "---\n- item1\n- item2\n---\n## Body"
    res1 = verify_sandbox_prd(md_list)
    assert res1["valid"] is False
    assert res1["errors"] == ["YAML frontmatter must be a key-value mapping."]

    md_scalar = "---\njust a single string\n---\n## Body"
    res2 = verify_sandbox_prd(md_scalar)
    assert res2["valid"] is False
    assert res2["errors"] == ["YAML frontmatter must be a key-value mapping."]


def test_verify_sandbox_prd_missing_title_and_id():
    """Verify missing both title and id fails."""
    md = (
        "---\n"
        "status: Idea\n"
        "persona: Taylor\n"
        "problem_statement: A real problem\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Body\n"
    )
    res = verify_sandbox_prd(md)
    assert res["valid"] is False
    assert any("PRD must have a title or id in frontmatter." in e for e in res["errors"])


def test_verify_sandbox_prd_title_or_id_alone_accepted():
    """Verify either title or id alone satisfies identifier invariant."""
    md_id_only = (
        "---\n"
        "id: PRD-0007\n"
        "status: Idea\n"
        "persona: Taylor\n"
        "problem_statement: Problem\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Body\n"
    )
    res1 = verify_sandbox_prd(md_id_only)
    assert res1["valid"] is True
    assert res1["metadata"]["id"] == "PRD-0007"

    md_title_only = (
        "---\n"
        "title: New PRD Title\n"
        "status: Idea\n"
        "persona: Taylor\n"
        "problem_statement: Problem\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Body\n"
    )
    res2 = verify_sandbox_prd(md_title_only)
    assert res2["valid"] is True
    assert res2["metadata"]["title"] == "New PRD Title"


def test_verify_sandbox_prd_status_variants():
    """Verify status must be Idea (case-insensitive)."""
    for valid_status in ["Idea", "idea", "IDEA", "  Idea  "]:
        md = (
            f"---\n"
            f"title: Title\n"
            f"status: '{valid_status}'\n"
            f"persona: Taylor\n"
            f"problem_statement: Problem\n"
            f"outcomes:\n"
            f"  - Outcome 1\n"
            f"---\n\n"
            f"# Body\n"
        )
        res = verify_sandbox_prd(md)
        assert res["valid"] is True, f"Status {valid_status} should be valid"

    for invalid_status in ["Accepted", "Draft", "Shipped", "", None]:
        md = (
            f"---\n"
            f"title: Title\n"
            f"status: {invalid_status}\n"
            f"persona: Taylor\n"
            f"problem_statement: Problem\n"
            f"outcomes:\n"
            f"  - Outcome 1\n"
            f"---\n\n"
            f"# Body\n"
        )
        res = verify_sandbox_prd(md)
        assert res["valid"] is False
        assert any("PRD status must be 'Idea'" in e for e in res["errors"])


def test_verify_sandbox_prd_persona_variants():
    """Verify target persona validation and KNOWN_PERSONAS enforcement."""
    for p in ["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha", "alex", "taylor"]:
        md = (
            f"---\n"
            f"title: Title\n"
            f"status: Idea\n"
            f"persona: {p}\n"
            f"problem_statement: Problem\n"
            f"outcomes:\n"
            f"  - Outcome 1\n"
            f"---\n\n"
            f"# Body\n"
        )
        res = verify_sandbox_prd(md)
        assert res["valid"] is True, f"Persona {p} should be valid"

    # target_persona alias
    md_alias = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "target_persona: Morgan\n"
        "problem_statement: Problem\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Body\n"
    )
    assert verify_sandbox_prd(md_alias)["valid"] is True

    # Missing persona
    md_missing = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "problem_statement: Problem\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Body\n"
    )
    res_miss = verify_sandbox_prd(md_missing)
    assert res_miss["valid"] is False
    assert any("Target persona is required" in e for e in res_miss["errors"])

    # Unknown persona
    md_unknown = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: AnonymousUser\n"
        "problem_statement: Problem\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Body\n"
    )
    res_unk = verify_sandbox_prd(md_unknown)
    assert res_unk["valid"] is False
    assert any("Target persona 'AnonymousUser' is not recognized" in e for e in res_unk["errors"])


def test_verify_sandbox_prd_problem_statement_in_body_or_frontmatter():
    """Verify problem statement can be provided in frontmatter or in markdown body."""
    # Only in frontmatter
    md_fm = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Alex\n"
        "problem_statement: Clear customer issue.\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Title\n\nSome body text\n"
    )
    assert verify_sandbox_prd(md_fm)["valid"] is True

    # Only in body under ## Problem Statement
    md_body1 = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Alex\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Title\n\n"
        "## Problem Statement\nCustomers need self service.\n"
    )
    assert verify_sandbox_prd(md_body1)["valid"] is True

    # Only in body under # The Problem
    md_body2 = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Alex\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# The Problem\nCritical workflow issue.\n"
    )
    assert verify_sandbox_prd(md_body2)["valid"] is True

    # Missing from both
    md_no_prob = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Alex\n"
        "outcomes:\n"
        "  - Outcome 1\n"
        "---\n\n"
        "# Title\n\nJust empty text\n"
    )
    res_no_prob = verify_sandbox_prd(md_no_prob)
    assert res_no_prob["valid"] is False
    assert any("Problem statement is required" in e for e in res_no_prob["errors"])


def test_verify_sandbox_prd_outcomes_in_body_or_frontmatter():
    """Verify outcomes can be provided in frontmatter list/string or in markdown body."""
    # Frontmatter string with newlines
    md_str = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Jordan\n"
        "problem_statement: Problem\n"
        "outcomes: \"- First outcome\\n- Second outcome\"\n"
        "---\n\n"
        "# Title\n"
    )
    assert verify_sandbox_prd(md_str)["valid"] is True

    # Body under ## Checkable Outcomes
    md_body_out = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Jordan\n"
        "problem_statement: Problem\n"
        "---\n\n"
        "# Title\n\n"
        "## Checkable Outcomes\n"
        "- [ ] User updates payment method\n"
    )
    assert verify_sandbox_prd(md_body_out)["valid"] is True

    # Body under ## Outcomes
    md_body_out2 = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Jordan\n"
        "problem_statement: Problem\n"
        "---\n\n"
        "# Title\n\n"
        "## Outcomes\n"
        "- Result is verified\n"
    )
    assert verify_sandbox_prd(md_body_out2)["valid"] is True

    # Missing from both
    md_no_out = (
        "---\n"
        "title: Title\n"
        "status: Idea\n"
        "persona: Jordan\n"
        "problem_statement: Problem\n"
        "---\n\n"
        "# Title\n\nNo outcomes listed here.\n"
    )
    res_no_out = verify_sandbox_prd(md_no_out)
    assert res_no_out["valid"] is False
    assert any("At least one checkable outcome is required" in e for e in res_no_out["errors"])


def test_get_tour_steps_and_default_steps():
    """Verify tour steps invariants: 4 steps, # selectors, sequential numbering."""
    steps = get_tour_steps()
    assert len(steps) == 4
    for i, s in enumerate(steps, 1):
        assert s["step"] == i
        assert len(s["title"]) > 0
        assert len(s["description"]) > 0
        assert s["selector"].startswith("#")

    # Specific targets for US-0050 & US-0107
    assert steps[0]["selector"] == "#tab-prds"
    assert steps[1]["selector"] == "#tab-gantt"
    assert steps[2]["selector"] == "#tab-matrix"
    assert steps[3]["selector"] == "#drawer-permalink-btn"


def test_generate_uat_receipt_comprehensive():
    """Verify UAT receipt generation with defaults and custom parameters."""
    r1 = generate_uat_receipt(
        feature_id="FEAT-001",
        prd_id="PRD-001",
        scenarios=["Scenario 1", "Scenario 2"],
        commits=["c123456", "c789012"],
        timestamp="2026-09-30T12:00:00Z",
    )
    assert r1["feature_id"] == "FEAT-001"
    assert r1["prd_id"] == "PRD-001"
    assert r1["timestamp"] == "2026-09-30T12:00:00Z"
    assert len(r1["hash"]) == 64
    assert "FEAT-001" in r1["markdown"]
    assert "PRD-001" in r1["markdown"]
    assert "c123456" in r1["markdown"]
    assert "Dual Sign-Off Signatures" in r1["markdown"]

    # Test default fallback values
    r2 = generate_uat_receipt(
        feature_id="FEAT-DEF",
        prd_id="PRD-DEF",
        scenarios=[],
    )
    assert r2["feature_id"] == "FEAT-DEF"
    assert r2["prd_id"] == "PRD-DEF"
    assert "**VERIFIED**: All criteria passed" in r2["markdown"]
    assert "Verified against repository HEAD commit history" in r2["markdown"]
