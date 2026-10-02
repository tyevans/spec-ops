"""BDD step definitions for US-0119: PRD Lint UI & Component Stories."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.lint_ui import LINT_COMPONENT_STORIES, render_lint_html

scenarios("features/us_0119_prd_lint_ui.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


@given("quality audit reports containing unfalsifiable outcomes and missing personas")
def init_mock_reports(bdd_ctx: dict[str, Any]):
    bdd_ctx["reports"] = [
        {
            "file_path": "docs/project/product/idea/prd-0077.md",
            "is_valid": False,
            "error_count": 1,
            "warning_count": 1,
            "falsifiable_count": 1,
            "unfalsifiable_count": 1,
            "diagnostics": [
                {
                    "rule_id": "PRD-LINT-001",
                    "severity": "warning",
                    "line": 4,
                    "message": "Missing target persona",
                    "suggestion": {
                        "line": 4,
                        "original_text": "target_persona: unknown",
                        "suggested_text": "target_persona: Alex",
                        "remediation_hint": "Select persona",
                    },
                },
                {
                    "rule_id": "PRD-LINT-002",
                    "severity": "error",
                    "line": 15,
                    "message": "Subjective term detected",
                    "suggestion": {
                        "line": 15,
                        "original_text": "- fast UI",
                        "suggested_text": "- executes in <200ms",
                        "remediation_hint": "Falsifiable metric",
                    },
                },
            ],
        }
    ]


@when("the PRD lint HTML dashboard is rendered")
def render_dashboard(bdd_ctx: dict[str, Any]):
    html = render_lint_html(reports=bdd_ctx.get("reports"))
    bdd_ctx["html"] = html


@then("the resulting document contains valid HTML5 structure")
def verify_html5_structure(bdd_ctx: dict[str, Any]):
    html: str = bdd_ctx["html"]
    assert "<!DOCTYPE html>" in html
    assert "<html lang=\"en\">" in html
    assert "</html>" in html
    assert "<title>" in html


@then("the document embeds the audit reports and component stories catalog")
def verify_embedded_data(bdd_ctx: dict[str, Any]):
    html: str = bdd_ctx["html"]
    assert "PRD-LINT-001" in html
    assert "PRD-LINT-002" in html
    assert "PRDLintSummaryCard" in html
    assert "LineLevelSuggestionCard" in html


@given("the PRD lint component story catalog")
def init_stories_catalog(bdd_ctx: dict[str, Any]):
    bdd_ctx["stories"] = LINT_COMPONENT_STORIES


@when("an architect inspects the available UI component stories")
def inspect_stories(bdd_ctx: dict[str, Any]):
    stories = bdd_ctx["stories"]
    bdd_ctx["component_keys"] = list(stories.keys())


@then("stories exist for summary cards, diagnostic issue items, line-level suggestions, diff modals, and filter toolbars")
def verify_expected_stories(bdd_ctx: dict[str, Any]):
    keys = bdd_ctx["component_keys"]
    expected = [
        "PRDLintSummaryCard",
        "PRDDiagnosticItem",
        "LineLevelSuggestionCard",
        "RemediationDiffModal",
        "LintFilterToolbar",
    ]
    for exp in expected:
        assert exp in keys, f"Missing story {exp}"


@then("each story defines expected properties and default mock state")
def verify_story_schema(bdd_ctx: dict[str, Any]):
    stories = bdd_ctx["stories"]
    for name, story in stories.items():
        assert "title" in story, f"{name} missing title"
        assert "description" in story, f"{name} missing description"
        assert "props" in story and isinstance(story["props"], list), f"{name} invalid props"
        assert "default_state" in story and isinstance(story["default_state"], dict), f"{name} invalid default_state"
