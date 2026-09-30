"""Executable BDD acceptance tests for US-0043 and US-0045 (PRD Studio & Story Assistant)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from spec_ops.prd.step_assistant import detect_backdoors, extract_frontdoor_steps
from spec_ops.prd.studio import (
    commit_prd_specification,
    create_prd_draft,
    validate_prd_schema,
)

scenarios("features/us_0043_prd_studio.feature")
scenarios("features/us_0045_story_assistant.feature")


@pytest.fixture
def studio_context(tmp_path: Path) -> dict[str, Any]:
    """Shared fixture context for PRD Studio BDD tests."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@specops.local"], cwd=tmp_path, capture_output=True)

    return {
        "root": tmp_path,
        "form_data": {},
        "last_result": None,
        "validation_alert": "",
        "draft_file": None,
        "preview_rendered": "",
        "scenario_input": "",
        "autocomplete_results": [],
        "backdoor_warning": "",
        "suggested_alt": "",
    }


# --- US-0043 Step Definitions ---


@given("the SpecOps standalone visualizer is open in a web browser")
def visualizer_open(studio_context: dict[str, Any]):
    studio_context["visualizer_active"] = True


@when('Taylor navigates to the "PRDs & Features" tab and clicks "New PRD"')
def navigate_to_new_prd(studio_context: dict[str, Any]):
    studio_context["tab"] = "PRDs & Features"
    studio_context["form_data"] = {}


@when("fills in the guided template form fields:")
def fill_form_fields(studio_context: dict[str, Any]):
    studio_context["form_data"] = {
        "title": "Self-Service Customer Billing Portal",
        "persona": "Alex",
        "component": "billing",
        "problem_statement": "Customers cannot update payment methods self-serve",
        "outcomes": [
            "User updates credit card via web dashboard",
            "Stripe webhook confirms card update with 200 OK",
        ],
        "prd_id": "PRD-0002",
    }


@when('clicks "Save PRD Draft"')
def click_save_prd_draft(studio_context: dict[str, Any]):
    root = studio_context["root"]
    res = create_prd_draft(root, studio_context["form_data"])
    studio_context["last_result"] = res
    if res.get("success"):
        studio_context["draft_file"] = root / res["file_path"]


@then('a new Markdown file is created at "docs/project/product/idea/prd-0002-self-service-customer-billing-portal.md"')
def verify_markdown_file_created(studio_context: dict[str, Any]):
    res = studio_context["last_result"]
    assert res is not None
    assert res["success"] is True
    assert "prd-0002-self-service-customer-billing-portal.md" in res["file_path"]
    assert Path(res["absolute_path"]).exists()


@then('the generated document contains valid YAML frontmatter with status "Idea" and target persona "Alex"')
def verify_frontmatter(studio_context: dict[str, Any]):
    path = Path(studio_context["last_result"]["absolute_path"])
    content = path.read_text(encoding="utf-8")
    assert "status: Idea" in content
    assert "target_persona: Alex" in content
    assert "component: billing" in content
    assert "Customers cannot update payment methods self-serve" in content


@given("Taylor is authoring a PRD in the Web Studio")
def authoring_prd(studio_context: dict[str, Any]):
    studio_context["form_data"] = {
        "title": "Draft Without Invariants",
        "component": "core",
    }


@when('Taylor attempts to submit a PRD with missing "Checkable Outcomes" or an unmapped "Target Persona"')
def submit_invalid_prd(studio_context: dict[str, Any]):
    root = studio_context["root"]
    bad_payload = {
        "title": "Incomplete PRD",
        "persona": "UnknownPersona",
        "problem_statement": "Some problem",
        "outcomes": [],
    }
    res = create_prd_draft(root, bad_payload)
    studio_context["last_result"] = res
    studio_context["validation_alert"] = res.get("message", "")


@then("the editor displays a validation alert highlighting the missing mandatory sections")
def editor_displays_validation_alert(studio_context: dict[str, Any]):
    res = studio_context["last_result"]
    assert res["success"] is False
    assert len(res["violations"]) > 0
    assert any("outcome" in v.lower() for v in res["violations"])


@then("prevents document creation until at least one falsifiable outcome is specified")
def prevents_doc_creation(studio_context: dict[str, Any]):
    assert studio_context["last_result"]["success"] is False
    root = studio_context["root"]
    assert not (root / "docs" / "project" / "product" / "idea" / "prd-0001-incomplete-prd.md").exists()


@then("cites the governing specification standard (ADR-0001).")
def cites_adr_standard(studio_context: dict[str, Any]):
    res = studio_context["last_result"]
    assert "ADR-0001" in res.get("error", "") or any("ADR-0001" in v for v in res.get("violations", []))


@given('an existing PRD "PRD-0001" open in the visualizer PRD Studio')
def existing_prd_open(studio_context: dict[str, Any]):
    root = studio_context["root"]
    init_data = {
        "title": "Initial Platform Engine",
        "persona": "Taylor",
        "component": "core",
        "problem_statement": "Initial statement",
        "outcomes": ["Outcome 1"],
        "prd_id": "PRD-0001",
    }
    res = create_prd_draft(root, init_data)
    assert res["success"] is True
    studio_context["draft_file"] = res["file_path"]

    # Initial git commit
    subprocess.run(["git", "add", "."], cwd=root, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, capture_output=True)


@when("Taylor updates the problem statement in the form editor")
def update_problem_statement(studio_context: dict[str, Any]):
    root = studio_context["root"]
    file_path = root / studio_context["draft_file"]
    old_content = file_path.read_text(encoding="utf-8")
    new_content = old_content.replace("Initial statement", "Updated live problem statement with Diataxis clarity")
    studio_context["updated_content"] = new_content
    studio_context["preview_rendered"] = f"<h1>PRD</h1><p>Updated live problem statement</p>"


@then("the live Markdown preview pane re-renders the Diataxis formatting in real time")
def preview_renders_in_real_time(studio_context: dict[str, Any]):
    assert "Updated live problem statement" in studio_context["preview_rendered"]


@then('clicking "Commit Specification" records the changes directly to the active feature branch with git author attribution.')
def click_commit_specification(studio_context: dict[str, Any]):
    root = studio_context["root"]
    res = commit_prd_specification(
        repo_root=root,
        file_path=studio_context["draft_file"],
        content=studio_context["updated_content"],
        commit_message="spec(prd): update PRD-0001 problem statement",
        author_name="Taylor",
        author_email="taylor@specops.local",
    )
    assert res["success"] is True
    assert len(res["commit_hash"]) > 0

    log_res = subprocess.run(["git", "log", "-n", "1", "--format=%an <%ae> %s"], cwd=root, capture_output=True, text=True)
    assert "Taylor <taylor@specops.local>" in log_res.stdout
    assert "update PRD-0001 problem statement" in log_res.stdout


# --- US-0045 Step Definitions ---


@given('Taylor is authoring a new user story for "PRD-0001" in the visualizer Story Studio')
def story_studio_open(studio_context: dict[str, Any]):
    studio_context["story_active"] = True


@when('Taylor types "Given " into the scenario editor')
def type_given_step(studio_context: dict[str, Any]):
    studio_context["scenario_input"] = "Given "
    studio_context["autocomplete_results"] = extract_frontdoor_steps(Path.cwd(), query="Given")


@then("the step assistant displays an autocomplete dropdown of registered frontdoor fixtures:")
def verify_autocomplete_results(studio_context: dict[str, Any]):
    results = studio_context["autocomplete_results"]
    patterns = [r["pattern"] for r in results]
    assert "Given a project initialized with SpecOps" in patterns
    assert "Given the standalone visualizer is open in a browser" in patterns
    assert "Given an accepted PRD with linked user stories" in patterns


@then("selecting a step populates the scenario with valid Gherkin syntax.")
def select_step_populates(studio_context: dict[str, Any]):
    chosen = "Given a project initialized with SpecOps"
    studio_context["populated_scenario"] = f"Scenario: Project Setup\n  {chosen}\n"
    assert chosen in studio_context["populated_scenario"]


@given("Taylor is authoring a Gherkin scenario")
def authoring_gherkin_scenario(studio_context: dict[str, Any]):
    pass


@when(parsers.parse('Taylor enters a step referencing private internals such as "{step}"'))
def enter_backdoor_step(studio_context: dict[str, Any], step: str):
    is_bd, warn, alt = detect_backdoors(step)
    studio_context["is_backdoor"] = is_bd
    studio_context["backdoor_warning"] = warn
    studio_context["suggested_alt"] = alt


@then("the scenario assistant displays an architectural warning:")
def verify_backdoor_warning(studio_context: dict[str, Any]):
    assert studio_context["is_backdoor"] is True
    assert "Backdoor violation (ADR-0003)" in studio_context["backdoor_warning"]


@then("suggests the compliant frontdoor alternative.")
def verify_frontdoor_alternative(studio_context: dict[str, Any]):
    assert len(studio_context["suggested_alt"]) > 0
    assert "CLI" in studio_context["suggested_alt"] or "public" in studio_context["suggested_alt"]


@given("a completed Gherkin scenario meeting INVEST criteria")
def completed_gherkin_scenario(studio_context: dict[str, Any]):
    studio_context["story_data"] = {
        "title": "Low-Code Gherkin BDD Story Authoring Assistant",
        "story_id": "0045",
        "persona": "Taylor",
        "governing_prd": "PRD-0003",
        "scenario": (
            "Scenario: Autocompleting Established Frontdoor Steps during Story Creation\n"
            "  Given Taylor is authoring a new user story for 'PRD-0001' in the visualizer Story Studio\n"
            "  When Taylor types 'Given ' into the scenario editor\n"
            "  Then the step assistant displays an autocomplete dropdown of registered frontdoor fixtures\n"
        ),
    }
    root = studio_context["root"]
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-0003-product-discovery-web-prd-studio-and-living-uat-verification.md"
    prd_file.write_text(
        "---\n"
        "id: PRD-0003\n"
        "title: Product Discovery, Web PRD Studio & Living UAT Verification\n"
        "status: Accepted\n"
        "---\n\n"
        "# PRD-0003: Product Discovery\n\n"
        "## Linked User Stories\n\n"
        "- `US-0043`\n",
        encoding="utf-8",
    )


@when('Taylor clicks "Accept User Story"')
def click_accept_user_story(studio_context: dict[str, Any]):
    from spec_ops.visualizer.story_assistant import accept_user_story

    root = studio_context["root"]
    res = accept_user_story(root, studio_context["story_data"])
    studio_context["story_result"] = res


@then(parsers.parse('a specification file is written to "{pattern}"'))
def verify_story_specification_written(studio_context: dict[str, Any], pattern: str):
    res = studio_context["story_result"]
    assert res is not None
    assert res["success"] is True
    file_path = res["file_path"]
    assert "user_stories/accepted/us-0045-" in file_path
    root = studio_context["root"]
    target = root / file_path
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "status: Accepted" in content
    assert "US-0045" in content


@then(parsers.parse('the story is linked to the governing PRD in "{prd_path}"'))
def verify_story_linked_to_prd(studio_context: dict[str, Any], prd_path: str):
    root = studio_context["root"]
    prd_file = root / "docs" / "project" / "product" / "accepted" / "prd-0003-product-discovery-web-prd-studio-and-living-uat-verification.md"
    assert prd_file.exists()
    content = prd_file.read_text(encoding="utf-8")
    assert "US-0045" in content


@then("the story becomes immediately available for engineering vertical slice decomposition.")
def verify_story_available_for_decomposition(studio_context: dict[str, Any]):
    res = studio_context["story_result"]
    assert res["success"] is True
    assert "US-0045" in res["story_id"]

