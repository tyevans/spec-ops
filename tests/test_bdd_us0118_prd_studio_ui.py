"""BDD step definitions for US-0118: PRD Studio UI and Component Stories."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.studio_ui import STUDIO_COMPONENT_STORIES, render_studio_html

scenarios("features/us_0118_prd_studio_ui.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


@given("the SpecOps component story catalog for PRD Studio")
def catalog_fixture(bdd_ctx: dict[str, Any]):
    bdd_ctx["catalog"] = STUDIO_COMPONENT_STORIES
    assert len(STUDIO_COMPONENT_STORIES) >= 4


@when(parsers.parse('inspecting the component story for "{component_name}"'))
def inspect_story(component_name: str, bdd_ctx: dict[str, Any]):
    assert component_name in bdd_ctx["catalog"]
    bdd_ctx["current_story"] = bdd_ctx["catalog"][component_name]


@then("the component story defines required props and valid default state")
def verify_props_and_state(bdd_ctx: dict[str, Any]):
    story = bdd_ctx["current_story"]
    assert "props" in story
    assert len(story["props"]) > 0
    assert "default_state" in story
    assert story["default_state"].get("is_valid") is True


@then("the component story specifies dynamic list manipulation capabilities.")
def verify_list_capabilities(bdd_ctx: dict[str, Any]):
    story = bdd_ctx["current_story"]
    assert "outcomes" in story["default_state"]
    assert len(story["default_state"]["outcomes"]) >= 2


@given(
    parsers.parse(
        'a PRD draft state seeded with title "{title}" and persona "{persona}"'
    )
)
def seeded_state(title: str, persona: str, bdd_ctx: dict[str, Any]):
    bdd_ctx["seed"] = {
        "session_id": "studio-test1234",
        "title": title,
        "persona": persona,
        "component": "prd",
        "problem_statement": "Test problem statement",
        "outcomes": ["First outcome", "Second outcome"],
        "stage": "idea",
        "is_dirty": False,
        "is_valid": True,
    }


@when("the studio HTML view is rendered")
def render_html_step(bdd_ctx: dict[str, Any]):
    html = render_studio_html(initial_state=bdd_ctx["seed"])
    bdd_ctx["html"] = html


@then("the output HTML contains the PRD title and persona options")
def verify_title_persona_in_html(bdd_ctx: dict[str, Any]):
    html = bdd_ctx["html"]
    assert "Self-Service Notification Center" in html
    assert '<option value="Taylor">Taylor</option>' in html
    assert '<option value="Alex">Alex</option>' in html


@then("the HTML embeds client-side scripts connecting to the studio REST API")
def verify_rest_api_scripts(bdd_ctx: dict[str, Any]):
    html = bdd_ctx["html"]
    assert "/api/studio/state" in html
    assert "/api/studio/draft/update" in html
    assert "/api/studio/draft/save" in html
    assert "/api/studio/draft/commit" in html


@then("the live Diataxis preview pane is present in the DOM structure.")
def verify_preview_pane(bdd_ctx: dict[str, Any]):
    html = bdd_ctx["html"]
    assert 'class="preview-pane"' in html
    assert "Diataxis Live Preview" in html
    assert 'id="previewContent"' in html
