"""Executable BDD acceptance tests for US-0046: Living Customer UAT Verification Matrix CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.uat import record_uat_signoff
from spec_ops.scaffold.init import init_project

scenarios("features/us_0046_uat_cli.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_cli(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Invokes spec-ops CLI through public entry point."""
    cmd = [sys.executable, "-m", "spec_ops.cli.main", *args]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=CLI_ENV)


@pytest.fixture
def uat_cli_context(tmp_path: Path) -> dict[str, Any]:
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

    return {
        "repo": repo,
        "last_res": None,
    }


# ==============================================================================
# Scenario 1: Inspecting Customer UAT Readiness Matrix via CLI
# ==============================================================================


@given("a project with accepted PRDs, user stories, and passing CI runs")
def given_project_with_prds(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    assert (repo / "docs" / "project" / "product" / "accepted" / "prd-0001-visualizer.md").exists()


@when('Taylor runs "spec-ops prd uat status"')
def run_prd_uat_status(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    res = run_cli(repo, ["prd", "uat", "status"])
    assert res.returncode == 0
    uat_cli_context["last_res"] = res


@then("the UAT readiness table displays checkable outcomes with their linked stories")
def uat_readiness_table_displays_outcomes(uat_cli_context: dict[str, Any]):
    res = uat_cli_context["last_res"]
    assert "=== Customer UAT Readiness Matrix ===" in res.stdout
    assert "PRD-0001 Outcome 1" in res.stdout
    assert "PRD-0001 Outcome 2" in res.stdout
    assert "US-0006" in res.stdout
    assert "US-0010" in res.stdout


@then(parsers.parse("overall customer delivery readiness is reported as {percentage}"))
def overall_delivery_readiness_reported(uat_cli_context: dict[str, Any], percentage: str):
    res = uat_cli_context["last_res"]
    assert f"Overall Delivery Readiness: {percentage}" in res.stdout


# ==============================================================================
# Scenario 2: Recording PM Business Acceptance Sign-Off via CLI
# ==============================================================================


@given('a checkable outcome whose automated Gherkin scenario is "Passed (CI)"')
def outcome_whose_scenario_passed(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    res = run_cli(repo, ["prd", "uat", "status", "--json"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    matrix = data.get("matrix", [])
    o1 = next(m for m in matrix if m["outcome_id"] == "1")
    assert o1["test_status"] == "Passed (CI)"
    assert o1["uat_status"] == "Pending PM"


@when(
    parsers.parse(
        'Taylor runs "spec-ops prd uat sign --prd {prd} --outcome {outcome} --reviewer {reviewer} --notes {notes}"'
    )
)
def run_prd_uat_sign(uat_cli_context: dict[str, Any], prd: str, outcome: str, reviewer: str, notes: str):
    repo: Path = uat_cli_context["repo"]
    res = run_cli(
        repo,
        [
            "prd",
            "uat",
            "sign",
            "--prd",
            prd,
            "--outcome",
            outcome,
            "--reviewer",
            reviewer,
            "--notes",
            notes,
        ],
    )
    assert res.returncode == 0
    uat_cli_context["last_res"] = res


@then('the sign-off metadata is recorded in "docs/project/product/uat-signoff.json"')
def signoff_metadata_recorded_in_json(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    signoffs_file = repo / "docs" / "project" / "product" / "uat-signoff.json"
    assert signoffs_file.exists()
    data = json.loads(signoffs_file.read_text(encoding="utf-8"))
    assert "PRD-0001:1" in data["signoffs"]
    entry = data["signoffs"]["PRD-0001:1"]
    assert entry["status"] == "Approved"
    assert "Taylor" in entry["reviewer"]
    assert "Verified multi-tab switching" in entry["notes"]


@then(parsers.parse('running "spec-ops prd uat status" reports {percentage} delivery readiness'))
def running_status_reports_percentage(uat_cli_context: dict[str, Any], percentage: str):
    repo: Path = uat_cli_context["repo"]
    res = run_cli(repo, ["prd", "uat", "status"])
    assert res.returncode == 0
    assert f"Overall Delivery Readiness: {percentage}" in res.stdout


# ==============================================================================
# Scenario 3: Preventing Release Integration without Mandatory PM UAT Sign-Off
# ==============================================================================


@given("an engineering pull request attempting to mark a milestone complete")
def pr_attempting_milestone_completion(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    # Reset outcome 2 sign-off to unapproved state
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
def run_ci_gate_check_uat(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    res = run_cli(repo, ["health", "--check-uat"])
    uat_cli_context["last_res"] = res


@when("any high-priority checkable outcome lacks approved PM UAT sign-off")
def outcome_lacks_approved_pm_signoff(uat_cli_context: dict[str, Any]):
    res = uat_cli_context["last_res"]
    assert res.returncode != 0


@then(parsers.parse('the preflight check fails with: "{expected_msg}"'))
def check_fails_with_expected_msg(uat_cli_context: dict[str, Any], expected_msg: str):
    res = uat_cli_context["last_res"]
    assert res.returncode == 1
    assert expected_msg in res.stdout


@then("instructs the team to request Taylor's sign-off via the UAT visualizer matrix.")
def instructs_to_request_pm_signoff(uat_cli_context: dict[str, Any]):
    res = uat_cli_context["last_res"]
    assert "request Taylor's sign-off via the UAT visualizer matrix" in res.stdout


# ==============================================================================
# Scenario 4: Generating and Verifying Cryptographic Customer UAT Receipt
# ==============================================================================


@given("a project with approved PM UAT sign-offs")
def project_with_approved_signoffs(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    # Sign off all outcomes
    record_uat_signoff(repo, "PRD-0001", "1", "Taylor <taylor@specops.local>", "Approved")
    record_uat_signoff(repo, "PRD-0001", "2", "Taylor <taylor@specops.local>", "Approved")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: sign off all outcomes"], cwd=repo, check=True, capture_output=True)


@when('Taylor runs "spec-ops prd uat receipt --prd PRD-0001"')
def run_generate_uat_receipt(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    res = run_cli(repo, ["prd", "uat", "receipt", "--prd", "PRD-0001"])
    assert res.returncode == 0
    uat_cli_context["last_res"] = res


@then("a tamper-evident Customer UAT receipt is generated with valid SHA-256 tree digest")
def uat_receipt_generated_with_sha(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    receipt_file = repo / "dist" / "uat" / "PRD-0001-uat-receipt.json"
    assert receipt_file.is_file()

    data = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert data["$schema"] == "spec-ops/uat-receipt-v1"
    assert data["prd"]["id"] == "PRD-0001"
    assert len(data["verified_tree_digest"]) == 64
    assert len(data["receipt_signature"]) == 64
    assert data["uat_verification"]["status"] == "Approved"


@then('verifying the receipt with "spec-ops prd uat receipt --prd PRD-0001 --verify" succeeds')
def verify_uat_receipt_succeeds(uat_cli_context: dict[str, Any]):
    repo: Path = uat_cli_context["repo"]
    res = run_cli(repo, ["prd", "uat", "receipt", "--prd", "PRD-0001", "--verify"])
    assert res.returncode == 0
    assert "verified successfully" in res.stdout
