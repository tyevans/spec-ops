"""Executable BDD scenarios for Merkle inclusion proof generator and partial verification engine (US-0114)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.security.audit.merkle import (
    ComplianceDeliverable,
    HumanSignoff,
    compile_compliance_manifest,
)
from spec_ops.security.audit.proof_cli import generate_merkle_proof

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios("features/us_0114_merkle_inclusion_proofs.feature")


@pytest.fixture
def bdd_proof_context(tmp_path: Path) -> dict[str, Any]:
    """Sets up a test directory with compliance manifest and proof files."""
    dist_compliance = tmp_path / "dist" / "compliance"
    dist_compliance.mkdir(parents=True)

    signoff = HumanSignoff(
        reviewer="Sasha",
        email="sasha@specops.dev",
        signature="ed25519:bdd_proof_sig",
        timestamp="2026-09-30T15:00:00Z",
    )
    deliverables = [
        ComplianceDeliverable(
            task_id="TASK-0010",
            prd_id="PRD-0002",
            story_ids=["US-0056"],
            commit_sha="1111222233334444555566667777888899990000",
            prompt_sha256="aa" * 32,
            test_results_digest="bb" * 32,
            human_signoff=signoff,
        ),
        ComplianceDeliverable(
            task_id="TASK-0020",
            prd_id="PRD-0002",
            story_ids=["US-0056"],
            commit_sha="2222333344445555666677778888999900001111",
            prompt_sha256="cc" * 32,
            test_results_digest="dd" * 32,
            human_signoff=signoff,
        ),
        ComplianceDeliverable(
            task_id="TASK-0030",
            prd_id="PRD-0002",
            story_ids=["US-0114"],
            commit_sha="3333444455556666777788889999000011112222",
            prompt_sha256="ee" * 32,
            test_results_digest="ff" * 32,
            human_signoff=signoff,
        ),
    ]
    manifest = compile_compliance_manifest(deliverables, standard="soc2")
    manifest_file = dist_compliance / "soc2-audit-manifest.json"
    manifest_file.write_text(manifest.to_json(), encoding="utf-8")

    return {
        "root_dir": tmp_path,
        "manifest_file": manifest_file,
        "root_hash": manifest.root_hash,
        "cli_res": None,
    }


# ==============================================================================
# Given Steps
# ==============================================================================


@given("an exported compliance manifest with multiple SDLC deliverables and known root hash")
def manifest_with_deliverables(bdd_proof_context: dict[str, Any]):
    manifest_file: Path = bdd_proof_context["manifest_file"]
    assert manifest_file.is_file()


@given('a valid self-contained Merkle inclusion proof for "TASK-0030" and a trusted Merkle root hash')
def valid_proof_for_task_0030(bdd_proof_context: dict[str, Any]):
    root_dir: Path = bdd_proof_context["root_dir"]
    manifest_file: Path = bdd_proof_context["manifest_file"]
    proof_file = root_dir / "dist" / "compliance" / "proof-0030.json"

    proof_dict = generate_merkle_proof(manifest_file, "TASK-0030")
    proof_file.write_text(json.dumps(proof_dict, indent=2), encoding="utf-8")
    assert proof_file.is_file()


@given("an inclusion proof file whose leaf hash has been modified")
def tampered_proof_file(bdd_proof_context: dict[str, Any]):
    root_dir: Path = bdd_proof_context["root_dir"]
    manifest_file: Path = bdd_proof_context["manifest_file"]
    tampered_file = root_dir / "dist" / "compliance" / "tampered-proof.json"

    proof_dict = generate_merkle_proof(manifest_file, "TASK-0030")
    proof_dict["leaf_hash"] = "99" * 32
    tampered_file.write_text(json.dumps(proof_dict, indent=2), encoding="utf-8")
    assert tampered_file.is_file()


# ==============================================================================
# When Steps
# ==============================================================================


@when('the auditor executes "spec-ops audit proof --deliverable TASK-0030 --manifest dist/compliance/soc2-audit-manifest.json --out dist/compliance/proof-0030.json"')
def execute_audit_proof_generation(bdd_proof_context: dict[str, Any]):
    root_dir: Path = bdd_proof_context["root_dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "proof",
            "--deliverable",
            "TASK-0030",
            "--manifest",
            "dist/compliance/soc2-audit-manifest.json",
            "--out",
            "dist/compliance/proof-0030.json",
        ],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_proof_context["cli_res"] = res


@when('the auditor executes "spec-ops audit verify-proof dist/compliance/proof-0030.json --root TRUSTED_ROOT --json"')
def execute_verify_proof_valid(bdd_proof_context: dict[str, Any]):
    root_dir: Path = bdd_proof_context["root_dir"]
    root_hash: str = bdd_proof_context["root_hash"]

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "verify-proof",
            "dist/compliance/proof-0030.json",
            "--root",
            root_hash,
            "--json",
        ],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_proof_context["cli_res"] = res


@when('the auditor executes "spec-ops audit verify-proof dist/compliance/tampered-proof.json --root TRUSTED_ROOT --json"')
def execute_verify_proof_tampered(bdd_proof_context: dict[str, Any]):
    root_dir: Path = bdd_proof_context["root_dir"]
    root_hash: str = bdd_proof_context["root_hash"]

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "verify-proof",
            "dist/compliance/tampered-proof.json",
            "--root",
            root_hash,
            "--json",
        ],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_proof_context["cli_res"] = res


# ==============================================================================
# Then Steps
# ==============================================================================


@then('a self-contained Merkle inclusion proof "dist/compliance/proof-0030.json" is generated')
def verify_proof_file_exists(bdd_proof_context: dict[str, Any]):
    root_dir: Path = bdd_proof_context["root_dir"]
    proof_path = root_dir / "dist" / "compliance" / "proof-0030.json"
    assert proof_path.is_file()


@then("the proof records deliverable ID, leaf index, leaf hash, audit path, and root hash")
def verify_proof_fields(bdd_proof_context: dict[str, Any]):
    root_dir: Path = bdd_proof_context["root_dir"]
    proof_path = root_dir / "dist" / "compliance" / "proof-0030.json"
    data = json.loads(proof_path.read_text(encoding="utf-8"))

    assert data["deliverable_id"] == "TASK-0030"
    assert isinstance(data["leaf_index"], int)
    assert len(data["leaf_hash"]) == 64
    assert isinstance(data["audit_path"], list)
    assert len(data["root_hash"]) == 64
    assert data["root_hash"] == bdd_proof_context["root_hash"]


@then("the verification command succeeds with returncode 0")
def verify_returncode_0(bdd_proof_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_proof_context["cli_res"]
    assert res.returncode == 0


@then('the JSON output confirms verification status "ok"')
def verify_json_status_ok(bdd_proof_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_proof_context["cli_res"]
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["root_hash"] == bdd_proof_context["root_hash"]


@then("the verification command fails with returncode 1")
def verify_returncode_1(bdd_proof_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_proof_context["cli_res"]
    assert res.returncode == 1


@then('the JSON output reports "ok" as false')
def verify_json_status_false(bdd_proof_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_proof_context["cli_res"]
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "error" in data
