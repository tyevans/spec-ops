"""Executable BDD scenarios for cryptographic release verification (US-0055, TASK-0149)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.security.ed25519 import ed25519_keypair, ssh_encode_ed25519_pub
from spec_ops.security.release_verifier import sign_release_manifest

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios("features/us_0055_release_verification.feature")


@pytest.fixture
def bdd_release_context(tmp_path: Path) -> dict[str, Any]:
    """Sets up an initialized git repository with authorized signers and manifest fixtures."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Auditor"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "auditor@specops.dev"], cwd=repo, check=True)

    # Generate test Ed25519 keypair
    seed = b"testseed_sasha_ed25519_32bytes!"
    _, pub = ed25519_keypair(seed)
    ssh_line = ssh_encode_ed25519_pub(pub)

    # Write .allowed_signers
    allowed_signers = repo / ".allowed_signers"
    allowed_signers.write_text(
        f"sasha@specops.dev {ssh_line} Sasha Security Officer\n",
        encoding="utf-8",
    )

    return {
        "repo": repo,
        "seed": seed,
        "pub": pub,
        "signer": "sasha@specops.dev",
        "cli_res": None,
    }


# ==============================================================================
# Given Steps
# ==============================================================================


@given('a release manifest signed by an authorized key in ".allowed_signers"')
def valid_signed_release_manifest(bdd_release_context: dict[str, Any]):
    repo: Path = bdd_release_context["repo"]
    seed = bdd_release_context["seed"]
    signer = bdd_release_context["signer"]

    raw_manifest = {
        "$schema": "spec-ops/release-manifest-v1",
        "version": "1.0",
        "prd": {
            "id": "PRD-0002",
            "title": "Enterprise Security Engine",
            "persona": "Sasha",
        },
        "verified_tree_digest": "a" * 64,
        "completed_tasks": [{"id": "TASK-0149", "commit_sha": "abc1234"}],
        "test_verification": {"status": "Passed (CI)", "failed_scenarios": 0},
        "uat_verification": {"status": "Approved", "total_outcomes": 2, "approved_outcomes": 2},
    }

    signed = sign_release_manifest(raw_manifest, seed, signer, algorithm="ed25519")
    manifest_file = repo / "release-manifest.json"
    manifest_file.write_text(json.dumps(signed, indent=2), encoding="utf-8")


@given("a release manifest whose payload has been modified post-signing")
def tampered_release_manifest(bdd_release_context: dict[str, Any]):
    repo: Path = bdd_release_context["repo"]
    seed = bdd_release_context["seed"]
    signer = bdd_release_context["signer"]

    raw_manifest = {
        "$schema": "spec-ops/release-manifest-v1",
        "version": "1.0",
        "prd": {
            "id": "PRD-0002",
            "title": "Enterprise Security Engine",
            "persona": "Sasha",
        },
        "verified_tree_digest": "a" * 64,
        "completed_tasks": [{"id": "TASK-0149", "commit_sha": "abc1234"}],
        "test_verification": {"status": "Passed (CI)", "failed_scenarios": 0},
        "uat_verification": {"status": "Approved"},
    }

    signed = sign_release_manifest(raw_manifest, seed, signer, algorithm="ed25519")

    # Tamper with the payload after signing without updating signature
    signed["prd"]["title"] = "Tampered Security Engine Title"
    signed["verified_tree_digest"] = "f" * 64

    manifest_file = repo / "release-manifest.json"
    manifest_file.write_text(json.dumps(signed, indent=2), encoding="utf-8")


# ==============================================================================
# When Steps
# ==============================================================================


@when('the auditor executes "spec-ops release verify --manifest release-manifest.json"')
def execute_release_verify(bdd_release_context: dict[str, Any]):
    repo: Path = bdd_release_context["repo"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "release",
            "verify",
            "--manifest",
            "release-manifest.json",
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_release_context["cli_res"] = res


# ==============================================================================
# Then Steps
# ==============================================================================


@then("the verification succeeds with exit code 0")
def verify_success_exit_code_0(bdd_release_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_release_context["cli_res"]
    assert res.returncode == 0, f"Expected returncode 0, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then("the report confirms cryptographic validity and signer identity")
def verify_report_confirms_validity_and_signer(bdd_release_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_release_context["cli_res"]
    combined = res.stdout + "\n" + res.stderr
    assert "VALID" in combined or "valid" in combined.lower()
    assert bdd_release_context["signer"] in combined


@then("the verification fails with exit code 1")
def verify_failure_exit_code_1(bdd_release_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_release_context["cli_res"]
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then("identifies the signature mismatch error")
def verify_identifies_signature_mismatch(bdd_release_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_release_context["cli_res"]
    combined = res.stdout + "\n" + res.stderr
    assert "signature mismatch" in combined.lower()
