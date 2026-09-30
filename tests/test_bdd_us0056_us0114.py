"""Executable BDD scenarios for Merkle compliance manifest generator and verifier (US-0056, US-0114)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios(
    "features/us_0056_merkle_compliance_audit_trail.feature",
    "features/us_0114_merkle_tree_audit_manifests.feature",
)


@pytest.fixture
def bdd_audit_context(tmp_path: Path) -> dict[str, Any]:
    """Sets up an initialized git repository with completed tasks, stories, and commit history."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Audit Officer"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "audit@example.com"], cwd=repo, check=True)

    backlog = repo / "docs" / "project" / "backlog"
    complete = backlog / "complete"
    complete.mkdir(parents=True)

    stories = repo / "docs" / "project" / "user_stories" / "accepted"
    stories.mkdir(parents=True)

    # User Story
    story_content = """---
id: '0056'
title: Tamper-Evident SOC2 Audit Trail Generator
status: Accepted
governing_prd: PRD-0002
---
# US-0056: Tamper-Evident SOC2 Audit Trail Generator
## Acceptance Criteria
Scenario: Generating a deterministic SOC2 compliance audit package
  Given a repository with completed tasks
"""
    (stories / "us-0056-tamper-evident-soc2-and-iso-audit-trail-generator.md").write_text(story_content, encoding="utf-8")

    # Completed Task
    task_content = """---
id: '0030'
title: Cryptographic Commit Verification
status: Complete
governing_prds:
  - PRD-0002
governing_stories:
  - US-0056
target_bc: security
commit_sha: '1111222233334444555566667777888899990000'
signed_off_by: 'Sasha <sasha@specops.dev>'
signoff_signature: 'ed25519:test_sig_val'
signed_off_at: '2026-09-29T18:00:00Z'
test_results_digest: 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'
---
# TASK-0030: Cryptographic Commit Verification
Task implementation details.
"""
    task_file = complete / "0030-cryptographic-commit-verification.md"
    task_file.write_text(task_content, encoding="utf-8")

    (repo / "specops.toml").write_text('[project]\nname = "MerkleAuditApp"\n', encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "feat(task-0030): complete task 0030"], cwd=repo, check=True)

    return {
        "repo": repo,
        "task_file": task_file,
        "task_id": "TASK-0030",
        "cli_res": None,
    }


# ==============================================================================
# Given Steps
# ==============================================================================


@given("a repository with completed tasks, linked user stories, and git commit history")
@given("a repository with completed tasks, linked user stories, test execution records, and signed commits")
def repository_with_completed_tasks(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    assert (repo / "docs" / "project" / "backlog" / "complete").exists()


@given('a task file in "docs/project/backlog/complete/" whose commit SHA or sign-off signature has been modified out-of-band')
def task_file_modified_out_of_band(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    task_file: Path = bdd_audit_context["task_file"]

    # Step 1: Export a valid baseline manifest
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "export", "--standard", "soc2", "--output", "dist/compliance/"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0

    # Step 2: Modify commit SHA or sign-off out-of-band
    content = task_file.read_text(encoding="utf-8")
    modified_content = content.replace("1111222233334444555566667777888899990000", "ffffffffffffffffffffffffffffffffffffffff")
    task_file.write_text(modified_content, encoding="utf-8")


# ==============================================================================
# When Steps
# ==============================================================================


@when('the security officer executes "spec-ops audit export --standard soc2 --output dist/compliance/"')
def execute_audit_export(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "export", "--standard", "soc2", "--output", "dist/compliance/"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_audit_context["cli_res"] = res


@when('the security officer executes "spec-ops audit verify"')
def execute_audit_verify_default(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "verify"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_audit_context["cli_res"] = res


@when('the security officer or auditor executes "spec-ops audit verify --manifest dist/compliance/soc2-audit-manifest.json"')
def execute_audit_verify_manifest(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "verify",
            "--manifest",
            "dist/compliance/soc2-audit-manifest.json",
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_audit_context["cli_res"] = res


# ==============================================================================
# Then Steps
# ==============================================================================


@then('a cryptographic audit manifest "soc2-audit-manifest.json" is generated')
@then('a cryptographic audit manifest "soc2-audit-manifest.json" is generated in "dist/compliance/"')
def verify_manifest_generated(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    manifest_path = repo / "dist" / "compliance" / "soc2-audit-manifest.json"
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["standard"] == "soc2"
    assert data["algorithm"] == "sha256"
    assert data["serialization"] == "RFC8785"
    assert len(data["leaves"]) > 0


@then("every completed deliverable records PRD ID, User Story Gherkin scenarios, Task metadata, agent prompt SHA-256, test execution logs, human reviewer signature, and git commit SHA")
def verify_deliverable_fields_recorded(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    manifest_path = repo / "dist" / "compliance" / "soc2-audit-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    for leaf in data["leaves"]:
        deliv = leaf["data"]
        assert "task_id" in deliv
        assert "prd_id" in deliv
        assert "story_ids" in deliv
        assert "commit_sha" in deliv
        assert "prompt_sha256" in deliv
        assert "test_results_digest" in deliv
        assert "human_signoff" in deliv
        assert "gherkin_scenarios" in deliv
        assert "metadata" in deliv

        # Validate non-empty values for required security fields
        assert len(deliv["commit_sha"]) == 40
        assert len(deliv["prompt_sha256"]) == 64
        assert deliv["human_signoff"] is not None
        assert "signature" in deliv["human_signoff"]


@then('a top-level Merkle root hash is computed and written to "dist/compliance/MERKLE_ROOT".')
def verify_top_level_merkle_root(bdd_audit_context: dict[str, Any]):
    repo: Path = bdd_audit_context["repo"]
    root_path = repo / "dist" / "compliance" / "MERKLE_ROOT"
    manifest_path = repo / "dist" / "compliance" / "soc2-audit-manifest.json"

    assert root_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root_content = root_path.read_text(encoding="utf-8").strip()

    assert root_content == data["root_hash"]
    assert len(root_content) == 64


@then("the verification command fails with returncode 1")
def verify_command_fails(bdd_audit_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_audit_context["cli_res"]
    assert res.returncode == 1


@then("outputs the corrupted task ID alongside the expected and computed SHA-256 integrity digests.")
def verify_corrupted_task_id_and_digests(bdd_audit_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_audit_context["cli_res"]
    combined = res.stderr + "\n" + res.stdout
    assert "TASK-0030" in combined
    assert "Expected SHA-256:" in combined or "expected" in combined.lower()
    assert "Computed SHA-256:" in combined or "computed" in combined.lower()
