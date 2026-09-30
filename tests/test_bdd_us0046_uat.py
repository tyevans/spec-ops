"""Executable BDD acceptance tests for US-0046: Living Customer UAT Verification Matrix."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.uat import load_uat_signoffs, record_uat_signoff
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html, serialize_project_data

scenarios("features/us_0046_customer_uat_matrix.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


@pytest.fixture
def uat_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="UATApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Accepted PRD-0001
    prd_accepted_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_accepted_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_accepted_dir / "prd-0001-visualizer.md"
    prd_file.write_text(
        """---
id: '0001'
title: Visualizer & Deep Linking
status: Accepted
target_persona: Taylor (The Product Manager)
component: visualizer
---

# PRD-0001 — Visualizer & Deep Linking

## Checkable Outcomes

1. Visualizer renders 2D force-directed canvas.
2. Deep linking opens entity detail drawer.

## Linked User Stories

- `US-0006`
- `US-0010`
""",
        encoding="utf-8",
    )

    # Stories
    stories_accepted_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_accepted_dir.mkdir(parents=True, exist_ok=True)

    (stories_accepted_dir / "us-0006.md").write_text(
        """---
id: '0006'
title: Living 2D Graph Visualizer
status: Accepted
governing_prd: PRD-0001
---

# US-0006
```gherkin
Scenario: Visualizer renders 2D force-directed canvas
  Given a project graph
  When visualizer is launched
  Then canvas renders nodes
```
""",
        encoding="utf-8",
    )

    (stories_accepted_dir / "us-0010.md").write_text(
        """---
id: '0010'
title: Deep Linking
status: Accepted
governing_prd: PRD-0001
---

# US-0010
```gherkin
Scenario: Deep linking opens entity detail drawer
  Given a node permalink
  When navigated
  Then drawer opens
```
""",
        encoding="utf-8",
    )

    # Initial sign-off: outcome 2 approved, outcome 1 pending
    record_uat_signoff(
        repo_root=repo,
        prd_id="PRD-0001",
        outcome_id="2",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="Deep linking verified",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup uat test repo"], cwd=repo, check=True, capture_output=True)

    from spec_ops.config.loader import load_config

    config = load_config(repo)

    return {
        "repo": repo,
        "config": config,
        "html": "",
        "data": {},
        "cli_result": None,
    }


# ==============================================================================
# Scenario: Inspecting Customer UAT Readiness Matrix
# ==============================================================================


@given("a project with accepted PRDs, user stories, and passing CI runs")
def given_project_with_accepted_prds(uat_context: dict[str, Any]):
    repo: Path = uat_context["repo"]
    assert (repo / "docs" / "project" / "product" / "accepted" / "prd-0001-visualizer.md").exists()


@when('Taylor opens the visualizer and clicks the "UAT Readiness" tab')
def taylor_opens_visualizer(uat_context: dict[str, Any]):
    config = uat_context["config"]
    html = generate_standalone_html(config)
    uat_context["html"] = html
    data = serialize_project_data(config)
    uat_context["data"] = data
    assert 'data-tab="uat"' in html
    assert "UAT Readiness" in html


@then("each PRD checkable outcome is displayed with its linked Gherkin scenario execution status:")
def outcomes_displayed_with_status(uat_context: dict[str, Any]):
    data = uat_context["data"]
    uat = data.get("uat", {})
    matrix = uat.get("matrix", [])

    assert len(matrix) >= 2
    outcome_map = {m["outcome_id"]: m for m in matrix}

    # Outcome 1
    o1 = outcome_map["1"]
    assert "Visualizer renders 2D force-directed canvas" in o1["outcome_text"]
    assert "US-0006" in o1["linked_stories"]
    assert o1["test_status"] == "Passed (CI)"
    assert o1["uat_status"] == "Pending PM"

    # Outcome 2
    o2 = outcome_map["2"]
    assert "Deep linking opens entity detail drawer" in o2["outcome_text"]
    assert "US-0010" in o2["linked_stories"]
    assert o2["test_status"] == "Passed (CI)"
    assert o2["uat_status"] == "Approved"


@then("overall customer delivery readiness is calculated as a percentage.")
def delivery_readiness_percentage(uat_context: dict[str, Any]):
    data = uat_context["data"]
    uat = data.get("uat", {})
    readiness = uat.get("readiness_percentage")
    assert isinstance(readiness, (int, float))
    # 1 of 2 is approved, so 50.0%
    assert readiness == 50.0


# ==============================================================================
# Scenario: Recording PM Business Acceptance Sign-Off
# ==============================================================================


@given('a checkable outcome whose automated Gherkin scenario is "Passed (CI)"')
def outcome_with_passing_scenario(uat_context: dict[str, Any]):
    data = uat_context["data"]
    if not data:
        uat_context["data"] = serialize_project_data(uat_context["config"])
    matrix = uat_context["data"]["uat"]["matrix"]
    o1 = next(m for m in matrix if m["outcome_id"] == "1")
    assert o1["test_status"] == "Passed (CI)"


@when('Taylor reviews the running application and toggles the outcome status to "Approved (PM UAT)"')
def toggle_outcome_status(uat_context: dict[str, Any]):
    repo: Path = uat_context["repo"]
    # Record PM business acceptance sign-off
    record_uat_signoff(
        repo_root=repo,
        prd_id="PRD-0001",
        outcome_id="1",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="Verified multi-tab switching and drawer responsiveness on Chromium",
    )


@when('enters review notes: "Verified multi-tab switching and drawer responsiveness on Chromium"')
def enter_review_notes(uat_context: dict[str, Any]):
    # Notes were recorded in previous step
    pass


@then('the sign-off metadata (timestamp, reviewer: Taylor, outcome ID) is recorded in "docs/project/product/uat-signoff.json"')
def signoff_metadata_recorded(uat_context: dict[str, Any]):
    repo: Path = uat_context["repo"]
    signoffs_file = repo / "docs" / "project" / "product" / "uat-signoff.json"
    assert signoffs_file.exists()

    data = json.loads(signoffs_file.read_text(encoding="utf-8"))
    signoff = data["signoffs"]["PRD-0001:1"]
    assert signoff["outcome_id"] == "1"
    assert "Taylor" in signoff["reviewer"]
    assert signoff["status"] == "Approved"
    assert "Verified multi-tab switching" in signoff["notes"]
    assert "timestamp" in signoff


@then("the UAT matrix updates immediately with a green acceptance badge.")
def matrix_updates_with_green_badge(uat_context: dict[str, Any]):
    config = uat_context["config"]
    data = serialize_project_data(config)
    o1 = next(m for m in data["uat"]["matrix"] if m["outcome_id"] == "1")
    assert o1["uat_status"] == "Approved"
    # Both outcomes approved now -> 100.0%
    assert data["uat"]["readiness_percentage"] == 100.0


# ==============================================================================
# Scenario: Preventing Release Integration without Mandatory PM UAT Sign-Off
# ==============================================================================


@given("an engineering pull request attempting to mark a milestone complete")
def pr_attempting_to_complete_milestone(uat_context: dict[str, Any]):
    repo: Path = uat_context["repo"]
    # Re-create state where outcome 2 lacks approved PM sign-off
    signoffs_file = repo / "docs" / "project" / "product" / "uat-signoff.json"
    payload = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            "PRD-0001:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0001",
                "status": "Approved",
                "reviewer": "Taylor <taylor@specops.local>",
                "timestamp": "2026-09-29T18:00:00Z",
                "notes": "Verified",
            }
        },
    }
    signoffs_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@when('the CI preflight gate runs "spec-ops health --check-uat"')
def run_health_check_uat(uat_context: dict[str, Any]):
    repo: Path = uat_context["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "health", "--check-uat"]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=CLI_ENV)
    uat_context["cli_result"] = res


@when("any high-priority checkable outcome lacks approved PM UAT sign-off")
def outcome_lacks_approved_signoff(uat_context: dict[str, Any]):
    res = uat_context["cli_result"]
    assert res.returncode != 0


@then('the preflight check fails with: "Release blocked: UAT sign-off missing for PRD-0001 Outcome 2"')
def check_fails_with_blocked_message(uat_context: dict[str, Any]):
    res = uat_context["cli_result"]
    assert res.returncode == 1
    assert "Release blocked: UAT sign-off missing for PRD-0001 Outcome 2" in res.stdout


@then("instructs the team to request Taylor's sign-off via the UAT visualizer matrix.")
def instructs_team_to_request_signoff(uat_context: dict[str, Any]):
    res = uat_context["cli_result"]
    assert "request Taylor's sign-off via the UAT visualizer matrix" in res.stdout
