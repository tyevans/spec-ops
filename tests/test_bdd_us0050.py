"""Executable BDD scenarios for US-0050 (Product Manager Onboarding Tutorial, Guided Tour & Sandbox)."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.docs.builder import build_docs_site
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html
from spec_ops.visualizer.tour_script import verify_sandbox_prd
from tests.test_visualizer import run_node_test

scenarios("features/us_0050_pm_onboarding_tutorial_and_tour.feature")


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "pm_project"
    init_project(project_dir, name="PMOnboardingProject")

    # Copy the tutorial into the project docs
    tutorials_dir = project_dir / "docs" / "tutorials"
    tutorials_dir.mkdir(parents=True, exist_ok=True)
    real_tutorial = Path("docs/tutorials/02-product-manager-onboarding.md").read_text(encoding="utf-8")
    (tutorials_dir / "02-product-manager-onboarding.md").write_text(real_tutorial, encoding="utf-8")

    out_site = project_dir / "site"
    config = load_config(root_dir=project_dir)
    build_docs_site(config, out_dir=out_site)

    html = generate_standalone_html(config)
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)

    return {
        "project_dir": project_dir,
        "config": config,
        "site_dir": out_site,
        "html": html,
        "project_data_js": scripts[0],
        "app_js": scripts[1],
        "tutorial_html": "",
        "sandbox_input": "",
        "sandbox_result": None,
    }


# --- Scenario 1: Accessing the Product Manager Diataxis Onboarding Tutorial ---


@given(parsers.parse('a SpecOps documentation site compiled with "{command}"'))
def given_docs_compiled(bdd_ctx: dict[str, Any], command: str):
    site_file = bdd_ctx["site_dir"] / "tutorials" / "02-product-manager-onboarding.html"
    assert site_file.exists(), f"Expected compiled tutorial at {site_file}"


@when(parsers.parse('Taylor navigates to "{doc_path}" in the browser'))
def when_navigates_to_tutorial(bdd_ctx: dict[str, Any], doc_path: str):
    html_rel = Path(doc_path).relative_to("docs").with_suffix(".html")
    html_path = bdd_ctx["site_dir"] / html_rel
    assert html_path.exists()
    bdd_ctx["tutorial_html"] = html_path.read_text(encoding="utf-8")


@then("a step-by-step tutorial is displayed covering PMaC philosophy, reading PRDs, writing Gherkin stories, and conducting UAT")
def then_tutorial_covers_core_topics(bdd_ctx: dict[str, Any]):
    html = bdd_ctx["tutorial_html"]
    # Check core PMaC topics
    assert "PMaC" in html or "Project Management as Code" in html
    assert "PRD" in html
    assert "Gherkin" in html
    assert "UAT" in html
    # Check step-by-step progression headings
    assert "What is Project Management as Code" in html
    assert "Reading PRDs" in html or "Navigating and Reading PRDs" in html
    assert "Authoring Executable Gherkin Stories" in html or "Writing" in html
    assert "Conducting Living UAT" in html or "Conducting UAT" in html


@then("all instructions avoid low-level terminal jargon in favor of browser and editor workflows.")
def then_instructions_avoid_terminal_jargon(bdd_ctx: dict[str, Any]):
    html = bdd_ctx["tutorial_html"]
    # Verify absence of developer terminal commands in tutorial text
    low_level_commands = [
        "git worktree",
        "git checkout -b",
        "git rebase",
        "git merge",
        "uv pip install",
        "uv run spec-ops",
        "chmod +x",
    ]
    for cmd in low_level_commands:
        assert cmd not in html.lower(), f"Unexpected terminal command '{cmd}' found in PM onboarding tutorial"
    # Verify presence of non-technical workflows
    assert "visualizer" in html.lower() or "browser" in html.lower()


# --- Scenario 2: Launching Interactive In-Browser Visualizer Guided Tour ---


@given("Taylor opens the SpecOps visualizer for the first time")
def given_taylor_opens_visualizer(bdd_ctx: dict[str, Any]):
    assert "showWelcomeModal" in bdd_ctx["html"]
    assert "startGuidedTour" in bdd_ctx["html"]


@when("the application detects no prior tour completion flag in localStorage")
def when_no_prior_completion_flag(bdd_ctx: dict[str, Any]):
    test_js = f"""
    {bdd_ctx["project_data_js"]}
    {bdd_ctx["app_js"]}
    assert.strictEqual(localStorage.getItem('specops_tour_completed'), null);
    """
    run_node_test(bdd_ctx["html"], test_js)


@then(parsers.parse('a lightweight welcome modal offers: "{offer_text}"'))
def then_welcome_modal_offers_tour(bdd_ctx: dict[str, Any], offer_text: str):
    test_js = f"""
    {bdd_ctx["project_data_js"]}
    {bdd_ctx["app_js"]}

    window.showWelcomeModal();
    const overlay = document.getElementById('welcome-overlay');
    assert.strictEqual(overlay.style.display, 'flex');
    const startBtn = document.getElementById('welcome-start-btn');
    assert(startBtn.textContent.includes("{offer_text}") || document.getElementById('welcome-modal').textContent.includes("{offer_text}"));
    """
    run_node_test(bdd_ctx["html"], test_js)


@then("stepping through the tour highlights PRDs & Features, Gantt timelines, UAT matrix, and deep-link permalinks")
def then_stepping_highlights_elements(bdd_ctx: dict[str, Any]):
    test_js = f"""
    {bdd_ctx["project_data_js"]}
    {bdd_ctx["app_js"]}

    window.startGuidedTour();
    const overlay = document.getElementById('tour-overlay');
    assert.strictEqual(overlay.style.display, 'flex');

    // Step 1: Highlights PRDs & Features (#tab-prds)
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 1 of 4'));
    assert(document.getElementById('tab-prds').classList.contains('tour-highlight'));

    // Step 2: Highlights Gantt timelines (#tab-gantt)
    window.nextTourStep();
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 2 of 4'));
    assert(!document.getElementById('tab-prds').classList.contains('tour-highlight'));
    assert(document.getElementById('tab-gantt').classList.contains('tour-highlight'));

    // Step 3: Highlights UAT matrix (#tab-matrix)
    window.nextTourStep();
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 3 of 4'));
    assert(document.getElementById('tab-matrix').classList.contains('tour-highlight'));

    // Step 4: Highlights deep-link permalinks (#drawer-permalink-btn)
    window.nextTourStep();
    assert(document.getElementById('tour-step-badge').textContent.includes('Step 4 of 4'));
    assert(document.getElementById('drawer-permalink-btn').classList.contains('tour-highlight'));
    """
    run_node_test(bdd_ctx["html"], test_js)


@then('clicking "Finish Tour" saves the preference and dismisses the highlights.')
def then_finish_tour_saves_and_dismisses(bdd_ctx: dict[str, Any]):
    test_js = f"""
    {bdd_ctx["project_data_js"]}
    {bdd_ctx["app_js"]}

    window.startGuidedTour();
    window.nextTourStep();
    window.nextTourStep();
    window.nextTourStep();

    // Finish tour
    window.nextTourStep();
    const overlay = document.getElementById('tour-overlay');
    assert.strictEqual(overlay.style.display, 'none');
    assert.strictEqual(localStorage.getItem('specops_tour_completed'), 'true');
    assert(!document.getElementById('drawer-permalink-btn').classList.contains('tour-highlight'));
    """
    run_node_test(bdd_ctx["html"], test_js)


# --- Scenario 3: Completing the Guided First PRD Shaping Exercise ---


@given("Taylor is following the onboarding tutorial in the visualizer sandbox")
def given_taylor_in_sandbox(bdd_ctx: dict[str, Any]):
    assert "verifySandboxClientPrd" in bdd_ctx["html"]
    assert "renderSandboxView" in bdd_ctx["html"]


@when(parsers.parse('Taylor completes the interactive exercise "{exercise_title}"'))
def when_taylor_completes_exercise(bdd_ctx: dict[str, Any], exercise_title: str):
    valid_prd = (
        "---\n"
        "id: PRD-0006\n"
        "title: Self-Service Customer Notification Center\n"
        "status: Idea\n"
        "persona: Taylor\n"
        "component: notifications\n"
        "problem_statement: Customers cannot customize notification alerts self-serve.\n"
        "outcomes:\n"
        "  - Users toggle weekly summary emails in web preferences\n"
        "  - Critical alerts route to primary admin email within 30 seconds\n"
        "---\n\n"
        "# Self-Service Customer Notification Center\n\n"
        "## Problem Statement\n"
        "Customers cannot customize notification alerts self-serve.\n\n"
        "## Checkable Outcomes\n"
        "- [ ] Users toggle weekly summary emails in web preferences\n"
        "- [ ] Critical alerts route to primary admin email within 30 seconds\n"
    )
    bdd_ctx["sandbox_input"] = valid_prd
    bdd_ctx["sandbox_result"] = verify_sandbox_prd(valid_prd)


@then("the tutorial verifies the generated Markdown structure locally")
def then_verifies_markdown_locally(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["sandbox_result"]
    assert res is not None
    assert res["valid"] is True
    assert len(res["errors"]) == 0

    # Also test client-side JS evaluation in Node harness
    escaped_prd = bdd_ctx["sandbox_input"].replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    test_js = f"""
    {bdd_ctx["project_data_js"]}
    {bdd_ctx["app_js"]}

    const prdText = `{escaped_prd}`;
    const clientRes = window.verifySandboxClientPrd(prdText);
    assert.strictEqual(clientRes.valid, true);
    assert.strictEqual(clientRes.errors.length, 0);

    // Test with DOM interaction
    const input = document.getElementById('sandbox-prd-input');
    input.value = prdText;
    const runRes = window.runSandboxVerification();
    assert.strictEqual(runRes.valid, true);
    """
    run_node_test(bdd_ctx["html"], test_js)


@then(parsers.parse('displays a celebratory confirmation badge: "{badge_text}".'))
def then_displays_celebratory_badge(bdd_ctx: dict[str, Any], badge_text: str):
    res = bdd_ctx["sandbox_result"]
    assert res["badge"] == badge_text

    escaped_prd = bdd_ctx["sandbox_input"].replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    test_js = f"""
    {bdd_ctx["project_data_js"]}
    {bdd_ctx["app_js"]}

    const input = document.getElementById('sandbox-prd-input');
    input.value = `{escaped_prd}`;
    window.runSandboxVerification();
    const badge = document.getElementById('sandbox-badge');
    assert(badge.textContent.includes("{badge_text}"));
    """
    run_node_test(bdd_ctx["html"], test_js)
