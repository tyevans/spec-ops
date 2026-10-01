"""Executable BDD acceptance tests for US-0046: Standalone Customer UAT Matrix HTML Export."""

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
from spec_ops.prd.uat_export import verify_exported_matrix_proof
from spec_ops.scaffold.init import init_project

scenarios("features/us_0046_uat_matrix_export.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_cli(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Invokes spec-ops CLI through public entry point."""
    cmd = [sys.executable, "-m", "spec_ops.cli.main", *args]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=CLI_ENV)


@pytest.fixture
def uat_export_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="UATExportApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Create accepted PRD-0003
    prd_accepted_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_accepted_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_accepted_dir / "prd-0003-web-studio.md"
    prd_file.write_text(
        """---
id: '0003'
title: Product Discovery, Web PRD Studio & Living UAT Verification
status: Accepted
target_persona: Taylor (The Product Manager)
component: prd
---

# PRD-0003 — Product Discovery, Web PRD Studio & Living UAT Verification

## Checkable Outcomes

1. Running `spec-ops prd studio --open` launches a lightweight local web interface.
2. Running `spec-ops prd uat PRD-0003 --export` generates a tamper-evident HTML/PDF acceptance matrix.

## Linked User Stories

- `US-0046`
""",
        encoding="utf-8",
    )

    # Stories
    stories_accepted_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_accepted_dir.mkdir(parents=True, exist_ok=True)

    (stories_accepted_dir / "us-0046.md").write_text(
        """---
id: '0046'
title: Customer-Ready UAT Verification Matrix
status: Accepted
governing_prd: PRD-0003
---

# US-0046
```gherkin
Scenario: Standalone HTML Customer UAT Acceptance Matrix
  Given an accepted PRD with outcomes
  When export is executed
  Then report is generated
```
""",
        encoding="utf-8",
    )

    # Record sign-offs
    record_uat_signoff(
        repo_root=repo,
        prd_id="PRD-0003",
        outcome_id="1",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="Verified web studio interface",
    )
    record_uat_signoff(
        repo_root=repo,
        prd_id="PRD-0003",
        outcome_id="2",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="Verified tamper-evident HTML matrix generation",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup prd-0003 test repo"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "html_file": None,
        "html_content": "",
        "validation_result": None,
    }


# ==============================================================================
# Scenario 1: Standalone HTML Customer UAT Acceptance Matrix
# ==============================================================================


@given('an accepted PRD "PRD-0003" with checkable outcomes and approved customer signatures')
def prd_with_outcomes_and_signatures(uat_export_context: dict[str, Any]):
    repo: Path = uat_export_context["repo"]
    prd_path = repo / "docs" / "project" / "product" / "accepted" / "prd-0003-web-studio.md"
    assert prd_path.is_file()

    signoff_file = repo / "docs" / "project" / "product" / "uat-signoff.json"
    assert signoff_file.is_file()
    data = json.loads(signoff_file.read_text(encoding="utf-8"))
    assert "PRD-0003:1" in data["signoffs"]
    assert "PRD-0003:2" in data["signoffs"]


@when('the engineer runs "spec-ops prd uat export --prd PRD-0003 --format html"')
def run_export_command(uat_export_context: dict[str, Any]):
    repo: Path = uat_export_context["repo"]
    res = run_cli(repo, ["prd", "uat", "export", "--prd", "PRD-0003", "--format", "html"])
    assert res.returncode == 0, f"Command failed: {res.stderr}\nStdout: {res.stdout}"
    assert "Exported Customer UAT Acceptance Matrix for PRD-0003" in res.stdout

    html_file = repo / "dist" / "uat" / "PRD-0003-uat-matrix.html"
    uat_export_context["html_file"] = html_file
    uat_export_context["html_content"] = html_file.read_text(encoding="utf-8")


@then("a standalone HTML matrix is generated")
def standalone_html_matrix_generated(uat_export_context: dict[str, Any]):
    html_file: Path = uat_export_context["html_file"]
    assert html_file.is_file()
    content = uat_export_context["html_content"]
    assert "<!DOCTYPE html>" in content
    assert "<html" in content
    assert "</html>" in content


@then("the HTML contains verified checkable outcomes and cryptographic verification badges")
def html_contains_outcomes_and_badges(uat_export_context: dict[str, Any]):
    content = uat_export_context["html_content"]

    # Checkable outcomes rendered
    assert "Running `spec-ops prd studio --open` launches a lightweight local web interface" in content
    assert "Running `spec-ops prd uat PRD-0003 --export` generates a tamper-evident HTML/PDF acceptance matrix" in content

    # Cryptographic verification badges and proof block
    assert "Tamper-Evident Cryptographic Ledger Proof" in content
    assert "crypto-receipt-signature" in content
    assert "crypto-tree-digest" in content
    assert "crypto-ledger-digest" in content
    assert "100.0% Readiness" in content
    assert "Cryptographic Proof Sealed" in content

    # Zero external CDN / network calls
    assert "http://" not in content
    assert "https://" not in content


# ==============================================================================
# Scenario 2: Tamper-Evident Digest in Exported Acceptance Matrix
# ==============================================================================


@given('a generated HTML UAT acceptance matrix for "PRD-0003"')
def given_generated_matrix(uat_export_context: dict[str, Any]):
    if not uat_export_context.get("html_file") or not uat_export_context["html_file"].is_file():
        repo: Path = uat_export_context["repo"]
        res = run_cli(repo, ["prd", "uat", "export", "--prd", "PRD-0003", "--format", "html"])
        assert res.returncode == 0
        html_file = repo / "dist" / "uat" / "PRD-0003-uat-matrix.html"
        uat_export_context["html_file"] = html_file
        uat_export_context["html_content"] = html_file.read_text(encoding="utf-8")


@when("the file contents are validated")
def validate_file_contents(uat_export_context: dict[str, Any]):
    repo: Path = uat_export_context["repo"]
    html_file: Path = uat_export_context["html_file"]
    valid, issues = verify_exported_matrix_proof(html_file, repo)
    uat_export_context["validation_result"] = (valid, issues)


@then("the embedded cryptographic verification proof matches the signed ledger")
def embedded_proof_matches_signed_ledger(uat_export_context: dict[str, Any]):
    valid, issues = uat_export_context["validation_result"]
    assert valid is True, f"Validation failed with issues: {issues}"
    assert len(issues) == 0

    # Test tamper detection: tamper with ledger
    repo: Path = uat_export_context["repo"]
    html_file: Path = uat_export_context["html_file"]
    signoff_file = repo / "docs" / "project" / "product" / "uat-signoff.json"
    data = json.loads(signoff_file.read_text(encoding="utf-8"))
    data["signoffs"]["PRD-0003:1"]["status"] = "Rejected"
    signoff_file.write_text(json.dumps(data), encoding="utf-8")

    tampered_valid, tampered_issues = verify_exported_matrix_proof(html_file, repo)
    assert tampered_valid is False
    assert any("Tampering detected" in err for err in tampered_issues)
