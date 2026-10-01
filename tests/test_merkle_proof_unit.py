"""Comprehensive blackbox unit tests for Merkle inclusion proof CLI and verification engine."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.security.audit.merkle import (
    ComplianceDeliverable,
    ComplianceManifest,
    HumanSignoff,
    MerkleTree,
    compile_compliance_manifest,
    hash_leaf,
)
from spec_ops.security.audit.proof_cli import (
    generate_merkle_proof,
    verify_merkle_proof,
)

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}


@pytest.fixture
def sample_manifest(tmp_path: Path) -> tuple[Path, ComplianceManifest]:
    """Generates a multi-deliverable compliance manifest and saves it to disk."""
    signoff = HumanSignoff(
        reviewer="Sasha",
        email="sasha@specops.dev",
        signature="ed25519:test_sig_001",
        timestamp="2026-09-30T12:00:00Z",
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
    manifest_path = tmp_path / "soc2-audit-manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    return manifest_path, manifest


def test_generate_merkle_proof_structure(sample_manifest: tuple[Path, ComplianceManifest]):
    """Verifies that generated inclusion proof contains all mandatory fields."""
    manifest_path, manifest = sample_manifest
    proof_dict = generate_merkle_proof(manifest_path, "TASK-0020")

    assert proof_dict["deliverable_id"] == "TASK-0020"
    assert proof_dict["leaf_index"] == 1
    assert proof_dict["root_hash"] == manifest.root_hash
    assert proof_dict["tree_size"] == 3
    assert proof_dict["standard"] == "soc2"
    assert proof_dict["algorithm"] == "sha256"
    assert len(proof_dict["audit_path"]) > 0
    assert "deliverable_data" in proof_dict
    assert proof_dict["deliverable_data"]["task_id"] == "TASK-0020"


def test_generate_merkle_proof_input_types(sample_manifest: tuple[Path, ComplianceManifest]):
    """Verifies generating proof from Path, JSON text, dict, and ComplianceManifest objects."""
    manifest_path, manifest = sample_manifest

    p1 = generate_merkle_proof(manifest_path, "TASK-0010")
    p2 = generate_merkle_proof(manifest_path.read_text(encoding="utf-8"), "TASK-0010")
    p3 = generate_merkle_proof(manifest.to_dict(), "TASK-0010")
    p4 = generate_merkle_proof(manifest, "TASK-0010")

    assert p1["leaf_hash"] == p2["leaf_hash"] == p3["leaf_hash"] == p4["leaf_hash"]
    assert p1["root_hash"] == p2["root_hash"] == p3["root_hash"] == p4["root_hash"]


def test_generate_merkle_proof_deliverable_not_found(sample_manifest: tuple[Path, ComplianceManifest]):
    """Verifies error when requested deliverable is absent from manifest."""
    manifest_path, _ = sample_manifest
    with pytest.raises(ValueError, match="not found in manifest"):
        generate_merkle_proof(manifest_path, "TASK-9999")


def test_verify_merkle_proof_offline_offline_success(sample_manifest: tuple[Path, ComplianceManifest]):
    """Verifies valid inclusion proof against trusted root without loading full manifest."""
    manifest_path, manifest = sample_manifest
    proof_dict = generate_merkle_proof(manifest_path, "TASK-0030")

    ok, msg, details = verify_merkle_proof(proof_dict, manifest.root_hash)
    assert ok is True
    assert "verified successfully" in msg.lower()
    assert details["computed_root"] == manifest.root_hash
    assert details["steps_count"] == len(proof_dict["audit_path"])


def test_verify_merkle_proof_detects_tampered_payload(sample_manifest: tuple[Path, ComplianceManifest]):
    """Verifies that altering deliverable payload inside proof fails verification."""
    manifest_path, manifest = sample_manifest
    proof_dict = generate_merkle_proof(manifest_path, "TASK-0030")
    proof_dict["deliverable_data"]["commit_sha"] = "0000000000000000000000000000000000000000"

    ok, msg, details = verify_merkle_proof(proof_dict, manifest.root_hash)
    assert ok is False
    assert "payload hash mismatch" in msg


def test_verify_merkle_proof_detects_root_mismatch(sample_manifest: tuple[Path, ComplianceManifest]):
    """Verifies that verifying against wrong root hash fails."""
    manifest_path, _ = sample_manifest
    proof_dict = generate_merkle_proof(manifest_path, "TASK-0030")
    fake_root = "00" * 32

    ok, msg, details = verify_merkle_proof(proof_dict, fake_root)
    assert ok is False
    assert "Merkle root mismatch" in msg


def test_cli_audit_proof_generation_and_json(sample_manifest: tuple[Path, ComplianceManifest], tmp_path: Path):
    """Frontdoor CLI test for 'spec-ops audit proof' with --json and --out options."""
    manifest_path, manifest = sample_manifest
    out_file = tmp_path / "task-0030-proof.json"

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
            str(manifest_path),
            "--out",
            str(out_file),
            "--json",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )

    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["deliverable_id"] == "TASK-0030"
    assert data["root_hash"] == manifest.root_hash
    assert out_file.is_file()

    saved_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved_data == data


def test_cli_audit_proof_text_output(sample_manifest: tuple[Path, ComplianceManifest]):
    """Frontdoor CLI test for 'spec-ops audit proof' human-readable text output."""
    manifest_path, _ = sample_manifest

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "proof",
            "--deliverable",
            "TASK-0010",
            "--manifest",
            str(manifest_path),
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )

    assert res.returncode == 0
    assert "Merkle Inclusion Proof generated" in res.stdout
    assert "Leaf Index:" in res.stdout
    assert "Leaf Hash:" in res.stdout
    assert "Audit Path:" in res.stdout


def test_cli_audit_proof_missing_manifest():
    """Frontdoor CLI test asserting error when manifest file is missing."""
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "proof",
            "--deliverable",
            "TASK-0010",
            "--manifest",
            "nonexistent-manifest.json",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 1
    assert "Manifest file not found" in res.stderr or "Manifest file not found" in res.stdout


def test_cli_audit_verify_proof_frontdoor_success(sample_manifest: tuple[Path, ComplianceManifest], tmp_path: Path):
    """Frontdoor CLI test for 'spec-ops audit verify-proof' verifying valid proof against root."""
    manifest_path, manifest = sample_manifest
    proof_file = tmp_path / "proof.json"

    # Step 1: Generate proof
    subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "proof",
            "--deliverable",
            "TASK-0020",
            "--manifest",
            str(manifest_path),
            "--out",
            str(proof_file),
        ],
        check=True,
        env=CLI_ENV,
    )

    # Step 2: Verify proof with human-readable output
    res_text = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "verify-proof",
            str(proof_file),
            "--root",
            manifest.root_hash,
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res_text.returncode == 0
    assert "verified successfully" in res_text.stdout

    # Step 3: Verify proof with --json output
    res_json = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "verify-proof",
            str(proof_file),
            "--root",
            manifest.root_hash,
            "--json",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res_json.returncode == 0
    out_obj = json.loads(res_json.stdout)
    assert out_obj["ok"] is True
    assert out_obj["root_hash"] == manifest.root_hash


def test_cli_audit_verify_proof_tamper_fails(sample_manifest: tuple[Path, ComplianceManifest], tmp_path: Path):
    """Frontdoor CLI test asserting exit code 1 when proof is tampered."""
    manifest_path, manifest = sample_manifest
    proof_file = tmp_path / "proof.json"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "proof",
            "--deliverable",
            "TASK-0020",
            "--manifest",
            str(manifest_path),
            "--out",
            str(proof_file),
        ],
        check=True,
        env=CLI_ENV,
    )

    # Tamper with leaf hash
    data = json.loads(proof_file.read_text(encoding="utf-8"))
    data["leaf_hash"] = "99" * 32
    proof_file.write_text(json.dumps(data), encoding="utf-8")

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "audit",
            "verify-proof",
            str(proof_file),
            "--root",
            manifest.root_hash,
            "--json",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 1
    out_obj = json.loads(res.stdout)
    assert out_obj["ok"] is False


def test_single_leaf_manifest_proof(tmp_path: Path):
    """Verifies edge case where Merkle tree contains exactly 1 leaf."""
    deliv = ComplianceDeliverable(
        task_id="TASK-0001",
        prd_id="PRD-0001",
        story_ids=["US-0001"],
        commit_sha="a" * 40,
        prompt_sha256="b" * 64,
        test_results_digest="c" * 64,
    )
    manifest = compile_compliance_manifest([deliv], standard="soc2")
    manifest_file = tmp_path / "single.json"
    manifest_file.write_text(manifest.to_json(), encoding="utf-8")

    proof = generate_merkle_proof(manifest_file, "TASK-0001")
    assert proof["tree_size"] == 1
    assert proof["leaf_index"] == 0
    assert len(proof["audit_path"]) == 0
    assert proof["leaf_hash"] == manifest.root_hash

    ok, _, _ = verify_merkle_proof(proof, manifest.root_hash)
    assert ok is True
