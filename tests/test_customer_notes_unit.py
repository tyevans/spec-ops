"""Unit tests for living customer release notes generator (US-0049, PRD-0003)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.release.customer_notes import (
    CustomerReleaseNotesData,
    PersonaImpact,
    UATOutcome,
    build_customer_notes_data,
    extract_what_good_looks_like,
    extract_who_this_is_for,
    find_prd_file,
    generate_customer_release_notes,
    render_html_customer_notes,
    render_json_customer_notes,
    render_markdown_customer_notes,
    sanitize_customer_text,
    update_changelog,
)


def test_sanitize_customer_text() -> None:
    raw = "feat(core): implement living 2D visualizer 4a5b6c7 AST parser _THREAD_LOCK"
    sanitized = sanitize_customer_text(raw)
    assert "feat" not in sanitized
    assert "4a5b6c7" not in sanitized
    assert "AST" not in sanitized
    assert "_THREAD_LOCK" not in sanitized
    assert "implement living 2D visualizer parser" == sanitized


def test_find_prd_file(tmp_path: Path) -> None:
    shipped = tmp_path / "docs" / "project" / "product" / "shipped"
    shipped.mkdir(parents=True, exist_ok=True)
    p_file = shipped / "prd-0001-autonomous-engine.md"
    p_file.write_text("---\nid: '0001'\ntitle: Test Engine\n---\n", encoding="utf-8")

    config = SpecOpsConfig(root_dir=tmp_path)
    assert find_prd_file("PRD-0001", config) == p_file
    assert find_prd_file("0001", config) == p_file
    assert find_prd_file("PRD-9999", config) is None


def test_extract_sections() -> None:
    md = """
# PRD-0001
## Who this is for
- **Taylor (The Product Manager)**: Clear visual tracking without raw terminal commands.
- **Alex (The Architect)**: Version-locked specifications in git.

## What good looks like
1. **Interactive Visualizer**: Zero-dependency 2D canvas.
2. **Self-Healing Loop**: Automated test failure recovery.
"""
    who = extract_who_this_is_for(md)
    assert "taylor" in who
    assert "Clear visual tracking" in who["taylor"]
    assert "alex" in who
    assert "Version-locked specifications" in who["alex"]

    good = extract_what_good_looks_like(md)
    assert len(good) == 2
    assert good[0][0] == "Interactive Visualizer"
    assert "Zero-dependency 2D canvas" in good[0][1]


def test_render_markdown_and_jargon_omission() -> None:
    data = CustomerReleaseNotesData(
        prd_id="PRD-0001",
        title="SpecOps Autonomous Engine",
        status="Shipped",
        summary="Autonomous PMaC engine version-locked in git.",
        target_persona="Taylor",
        personas=[
            PersonaImpact(
                name="Taylor — The Product Manager",
                role="Product Manager",
                benefits=["Clear user acceptance testing (UAT) workflows."],
            )
        ],
        uat_outcomes=[
            UATOutcome(outcome="Running spec-ops init scaffolds 7 baseline ADRs.", verified=True)
        ],
        capabilities=[("Living 2D Graph Visualizer", "Zero-dependency canvas.")],
    )

    md = render_markdown_customer_notes(data)
    assert "# Release Notes: SpecOps Autonomous Engine (PRD-0001)" in md
    assert "## Verifiable Customer UAT Checkmarks" in md
    assert "- [x] Running spec-ops init scaffolds 7 baseline ADRs." in md
    assert "### Taylor — The Product Manager" in md
    assert "- Clear user acceptance testing (UAT) workflows." in md
    assert "chore:" not in md
    assert "spike:" not in md
    assert "refactor:" not in md


def test_render_html_xss_safety_and_checkmarks() -> None:
    data = CustomerReleaseNotesData(
        prd_id="PRD-0001",
        title="<script>alert('pwned')</script> Engine",
        status="Shipped",
        summary="Safe summary.",
        target_persona="Taylor",
        personas=[
            PersonaImpact(
                name="Alex",
                role="Architect",
                benefits=["<img src=x onerror=alert(1)> Safe benefit."],
            )
        ],
        uat_outcomes=[
            UATOutcome(outcome="Outcome with <b>bold</b> text.", verified=True)
        ],
        capabilities=[("Capability <XSS>", "Description & More")],
    )

    html_out = render_html_customer_notes(data, branded=True)
    assert "<!DOCTYPE html>" in html_out
    assert "<script>alert('pwned')</script>" not in html_out
    assert "&lt;script&gt;alert(&#x27;pwned&#x27;)&lt;/script&gt;" in html_out
    assert "<img src=x onerror=alert(1)>" not in html_out
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_out
    assert "✓ Verified UAT" in html_out
    assert "Verifiable Customer UAT Checkmarks" in html_out


def test_render_json() -> None:
    data = CustomerReleaseNotesData(
        prd_id="PRD-0001",
        title="SpecOps Autonomous Engine",
        status="Shipped",
        summary="Overview of release.",
        target_persona="Taylor",
        personas=[
            PersonaImpact(name="Taylor", role="PM", benefits=["Benefit 1"])
        ],
        uat_outcomes=[UATOutcome(outcome="Check 1", verified=True)],
        capabilities=[("Cap 1", "Desc 1")],
        stories=[("US-0001", "Story Title", "Taylor")],
    )

    json_str = render_json_customer_notes(data)
    parsed = json.loads(json_str)
    assert parsed["prd_id"] == "PRD-0001"
    assert parsed["uat_outcomes"][0]["outcome"] == "Check 1"
    assert parsed["uat_outcomes"][0]["verified"] is True
    assert parsed["personas"][0]["name"] == "Taylor"
    assert parsed["stories"][0]["id"] == "US-0001"


def test_generate_and_publish_customer_notes(tmp_path: Path) -> None:
    shipped = tmp_path / "docs" / "project" / "product" / "shipped"
    shipped.mkdir(parents=True, exist_ok=True)
    prd_file = shipped / "prd-0001-engine.md"
    prd_file.write_text(
        """---
id: '0001'
title: Engine PRD
status: Shipped
target_persona: Taylor
---
# PRD-0001
## Checkable Outcomes
1. Engine initializes with zero errors.
## Who this is for
- **Taylor (Product Manager)**: Live UAT verification.
""",
        encoding="utf-8",
    )

    config = SpecOpsConfig(root_dir=tmp_path)
    dest, content = generate_customer_release_notes(
        prd_id="PRD-0001",
        config=config,
        format_type="markdown",
        publish=True,
    )

    assert dest.is_file()
    assert dest == tmp_path / "docs" / "releases" / "prd-0001-release-notes.md"
    assert "Engine initializes with zero errors." in content

    # Verify changelog updated
    changelog = tmp_path / "docs" / "explanation" / "changelog.md"
    assert changelog.is_file()
    c_text = changelog.read_text(encoding="utf-8")
    assert "# Changelog" in c_text
    assert "[PRD-0001] Engine PRD" in c_text

    # Verify idempotent update on subsequent publish
    dest2, content2 = generate_customer_release_notes(
        prd_id="PRD-0001",
        config=config,
        format_type="markdown",
        publish=True,
    )
    c_text2 = changelog.read_text(encoding="utf-8")
    assert c_text2.count("[PRD-0001] Engine PRD") == 1
