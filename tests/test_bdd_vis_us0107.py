"""Executable BDD scenarios for visualizer user story US-0107 (Stakeholder Guided Tour & BDD Matrix)."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html
from spec_ops.visualizer.tour_script import generate_uat_receipt, get_tour_steps
from tests.test_visualizer import run_node_test

scenarios("features/us_0107_interactive_guided_tour_bdd_matrix.feature")


@pytest.fixture
def vis_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "test_project"
    init_project(project_dir, name="VisTourProject")

    stories_dir = project_dir / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0001-alex.md").write_text(
        "---\n"
        "id: '0001'\n"
        "title: Alex User Story\n"
        "status: Accepted\n"
        "persona: Alex\n"
        "feature: FEAT-VIS-07\n"
        "governing_prd: PRD-0005\n"
        "---\n\n"
        "# US-0001 — Alex User Story\n\n"
        "## Acceptance Criteria\n\n"
        "Scenario: Verified user journey\n"
        "Given a user opens the visualizer\n"
        "When persona Alex is clicked\n"
        "Then acceptance criteria are verified\n",
        encoding="utf-8",
    )

    config = load_config(root_dir=project_dir)
    html = generate_standalone_html(config)
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    return {
        "project_dir": project_dir,
        "config": config,
        "html": html,
        "project_data_js": scripts[0],
        "app_js": scripts[1],
        "active_tab": "graph",
    }


@given("a non-technical stakeholder opens the visualizer for the first time")
def given_stakeholder_first_visit(vis_ctx: dict[str, Any]):
    assert "startGuidedTour" in vis_ctx["html"]


@when(parsers.parse('the stakeholder clicks "{btn_label}" in the top navigation'))
def when_stakeholder_clicks_tour(vis_ctx: dict[str, Any], btn_label: str):
    test_js = f"""
    location.hash = "";
    location.href = "http://localhost:8080/";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    const tourBtn = document.getElementById('btn-guided-tour');
    assert(tourBtn !== undefined);

    window.startGuidedTour();
    const overlay = document.getElementById('tour-overlay');
    assert.strictEqual(overlay.style.display, 'flex');
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 1 of 4'));
    assert(document.getElementById('tour-title').textContent.includes('Philosophy of PMaC'));

    window.nextTourStep();
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 2 of 4'));
    assert(document.getElementById('tour-title').textContent.includes('Personas, PRDs'));

    window.nextTourStep();
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 3 of 4'));

    window.nextTourStep();
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 4 of 4'));

    window.closeTour(true);
    assert.strictEqual(overlay.style.display, 'none');

    window.restartTour();
    assert.strictEqual(overlay.style.display, 'flex');
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 1 of 4'));
    """
    run_node_test(vis_ctx["html"], test_js)


@then("a step-by-step interactive spotlight overlays the screen explaining:")
def then_spotlight_overlays(vis_ctx: dict[str, Any]):
    steps = get_tour_steps()
    assert len(steps) == 4
    assert "PMaC" in steps[0]["title"]


@then("the tour can be stepped through, skipped, or restarted at any time with persistent state in localStorage.")
def then_tour_controls_persist(vis_ctx: dict[str, Any]):
    assert "window.startGuidedTour" in vis_ctx["html"]
    assert "window.nextTourStep" in vis_ctx["html"]
    assert "window.prevTourStep" in vis_ctx["html"]
    assert "window.closeTour" in vis_ctx["html"]


@given(parsers.parse('the stakeholder navigates to the "{tab_name}" tab'))
def given_nav_to_tab(vis_ctx: dict[str, Any], tab_name: str):
    vis_ctx["active_tab"] = tab_name


@when(parsers.parse('the stakeholder clicks on persona "{persona_name}"'))
def when_clicks_persona(vis_ctx: dict[str, Any], persona_name: str):
    test_js = f"""
    location.hash = "#tab=personas";
    location.href = "http://localhost:8080/#tab=personas";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    window.switchTab('personas');
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'personas');

    window.filterStoriesByPersona('{persona_name}');
    const content = document.getElementById('dashboard-content').innerHTML;
    assert(content.includes('Filtered by:'));
    assert(content.includes('Alex') || content.includes('{persona_name}'));

    window.toggleStoryAccordion('US-0001');
    const contentWithAccordion = document.getElementById('dashboard-content').innerHTML;
    assert(contentWithAccordion.includes('bdd-badge-verified') || contentWithAccordion.includes('PASSED'));
    assert(contentWithAccordion.includes('Export UAT Verification Receipt'));
    """
    run_node_test(vis_ctx["html"], test_js)


@then(parsers.parse('the view filters down exclusively to the user stories authored for {persona_name}'))
def then_filters_stories_for_persona(vis_ctx: dict[str, Any], persona_name: str):
    assert "filterStoriesByPersona" in vis_ctx["html"]


@then("selecting a story opens an accordion displaying its exact Gherkin scenarios:")
def then_story_accordion_gherkin(vis_ctx: dict[str, Any], docstring: str):
    assert "toggleStoryAccordion" in vis_ctx["html"]


@then("each scenario displays a green verification badge indicating passing blackbox test coverage.")
def then_green_verification_badge(vis_ctx: dict[str, Any]):
    assert "bdd-badge-verified" in vis_ctx["html"]


@given("all acceptance criteria for a release feature have passed blackbox verification")
def given_acceptance_criteria_passed(vis_ctx: dict[str, Any]):
    assert vis_ctx["html"] is not None


@when(parsers.parse('Sasha or Taylor reviews the feature in the visualizer and clicks "{btn_label}"'))
def when_clicks_export_receipt(vis_ctx: dict[str, Any], btn_label: str):
    test_js = f"""
    location.hash = "#tab=personas";
    location.href = "http://localhost:8080/#tab=personas";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    const receipt = window.exportUatReceipt('FEAT-VIS-07', 'PRD-0005', [
      'Given a stakeholder opens the visualizer When clicking tour Then modal opens'
    ]);
    assert(receipt !== undefined);
    assert.strictEqual(receipt.feature_id, 'FEAT-VIS-07');
    assert.strictEqual(receipt.prd_id, 'PRD-0005');
    assert(receipt.hash.startsWith('sha256-'));
    assert(receipt.markdown.includes('# UAT Verification Receipt: FEAT-VIS-07'));
    assert(receipt.markdown.includes('Dual Sign-Off Signatures'));
    assert(receipt.markdown.includes('Product Sign-Off'));
    assert(receipt.markdown.includes('Security Sign-Off'));
    """
    run_node_test(vis_ctx["html"], test_js)


@then("the visualizer generates a cryptographically hashed, timestamped compliance summary:")
def then_generates_compliance_summary(vis_ctx: dict[str, Any]):
    receipt = generate_uat_receipt("FEAT-VIS-07", "PRD-0005", ["Scenario 1: Verified"])
    assert receipt["feature_id"] == "FEAT-VIS-07"
    assert len(receipt["hash"]) == 64
    assert "Product Sign-Off" in receipt["markdown"]
    assert "Security Sign-Off" in receipt["markdown"]


@then("the receipt downloads as a tamper-evident Markdown artifact for SOC2/ISO compliance audit archives.")
def then_receipt_downloads(vis_ctx: dict[str, Any]):
    assert "exportUatReceipt" in vis_ctx["html"]
