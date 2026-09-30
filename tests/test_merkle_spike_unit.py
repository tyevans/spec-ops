"""Blackbox unit tests for Merkle tree compliance data structures and manifest engine (ADR-0011)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from spec_ops.security.merkle import (
    EMPTY_ROOT_HASH,
    ComplianceDeliverable,
    ComplianceManifest,
    HumanSignoff,
    MerkleInclusionProof,
    MerkleLeaf,
    MerkleTree,
    ProofStep,
    canonical_json_encode,
    compile_compliance_manifest,
    extract_repo_compliance_deliverables,
    hash_internal_node,
    hash_leaf,
    verify_compliance_manifest,
    verify_inclusion_proof,
)


def test_canonical_json_serialization_key_sorting():
    """Verifies RFC 8785 canonical JSON sorting and elimination of whitespace variations."""
    dict_a = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    dict_b = {"nested": {"y": 8, "z": 9}, "a": 1, "b": 2}
    raw_json_str = '{\n  "nested": {\n    "y": 8,\n    "z": 9\n  },\n  "a": 1,\n  "b": 2\n}'

    encoded_a = canonical_json_encode(dict_a)
    encoded_b = canonical_json_encode(dict_b)
    encoded_raw = canonical_json_encode(json.loads(raw_json_str))

    assert encoded_a == encoded_b == encoded_raw
    assert encoded_a == b'{"a":1,"b":2,"nested":{"y":8,"z":9}}'


def test_canonical_json_utf16_surrogate_code_unit_sorting():
    """Verifies RFC 8785 UTF-16 code unit ordering where surrogates precede BMP private-use area."""
    data = {"\uE000": "private_use", "\U00010000": "supplementary"}
    encoded = canonical_json_encode(data)
    assert encoded == b'{"\xf0\x90\x80\x80":"supplementary","\xee\x80\x80":"private_use"}'


def test_domain_separated_hashing_collision_resistance():
    """Verifies RFC 6962 0x00 and 0x01 domain separation prefixes eliminate second-preimage confusion."""
    payload = {"key": "value"}
    leaf_h = hash_leaf(payload)

    encoded = canonical_json_encode(payload)
    manual_leaf = hashlib.sha256(b"\x00" + encoded).hexdigest()
    assert leaf_h == manual_leaf

    left_hex = "aa" * 32
    right_hex = "bb" * 32
    node_h = hash_internal_node(left_hex, right_hex)
    manual_node = hashlib.sha256(b"\x01" + bytes.fromhex(left_hex) + bytes.fromhex(right_hex)).hexdigest()
    assert node_h == manual_node

    combined_payload = bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
    assert leaf_h != node_h
    assert hash_leaf(combined_payload) != node_h


def test_empty_and_single_leaf_merkle_trees():
    """Verifies RFC 6962 edge cases for empty and single-leaf trees."""
    empty_tree = MerkleTree([])
    assert empty_tree.tree_size == 0
    assert empty_tree.root_hash == EMPTY_ROOT_HASH

    single_leaf = hash_leaf({"id": "TASK-0001"})
    tree_one = MerkleTree([single_leaf])
    assert tree_one.tree_size == 1
    assert tree_one.root_hash == single_leaf

    proof_one = tree_one.generate_proof(0)
    assert len(proof_one.audit_path) == 0
    assert verify_inclusion_proof(single_leaf, proof_one)


def test_power_of_two_split_calculation():
    """Verifies RFC 6962 power-of-2 split tree construction across odd and even leaf counts."""
    leaves = [hash_leaf({"id": f"item-{i}"}) for i in range(5)]
    tree = MerkleTree(leaves)

    k = 4
    left_sub = MerkleTree(leaves[:k])
    right_sub = MerkleTree(leaves[k:])
    expected_root = hash_internal_node(left_sub.root_hash, right_sub.root_hash)

    assert tree.root_hash == expected_root


@pytest.mark.parametrize("size", [2, 3, 4, 7, 8, 13])
def test_merkle_inclusion_proof_completeness(size: int):
    """Verifies that valid inclusion proofs reconstruct the Merkle root for all leaves in tree."""
    leaves = [hash_leaf({"item_id": f"DELIV-{i:03d}"}) for i in range(size)]
    tree = MerkleTree(leaves)

    for i in range(size):
        proof = tree.generate_proof(i)
        assert proof.leaf_index == i
        assert proof.leaf_hash == leaves[i]
        assert proof.root_hash == tree.root_hash
        assert proof.tree_size == size
        assert verify_inclusion_proof(leaves[i], proof, tree.root_hash)


def test_merkle_inclusion_proof_tamper_detection():
    """Verifies that tampered leaves, sibling nodes, or roots fail inclusion verification."""
    leaves = [hash_leaf({"val": i}) for i in range(6)]
    tree = MerkleTree(leaves)
    proof = tree.generate_proof(2)

    assert verify_inclusion_proof(leaves[2], proof)

    tampered_leaf = hash_leaf({"val": "tampered"})
    assert not verify_inclusion_proof(tampered_leaf, proof)

    tampered_steps = [
        ProofStep(sibling_hash="ff" * 32, is_left=step.is_left) if idx == 0 else step
        for idx, step in enumerate(proof.audit_path)
    ]
    tampered_proof = MerkleInclusionProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        audit_path=tampered_steps,
        root_hash=proof.root_hash,
        tree_size=proof.tree_size,
    )
    assert not verify_inclusion_proof(leaves[2], tampered_proof)
    assert not verify_inclusion_proof(leaves[2], proof, root_hash="00" * 32)


def test_merkle_proof_serialization_round_trip():
    """Verifies dictionary serialization and deserialization of inclusion proofs."""
    leaves = [hash_leaf({"task": f"TASK-{i}"}) for i in range(4)]
    tree = MerkleTree(leaves)
    proof = tree.generate_proof(1)

    proof_dict = proof.to_dict()
    reconstituted = MerkleInclusionProof.from_dict(proof_dict)

    assert reconstituted.leaf_index == proof.leaf_index
    assert reconstituted.leaf_hash == proof.leaf_hash
    assert reconstituted.root_hash == proof.root_hash
    assert verify_inclusion_proof(leaves[1], reconstituted)


def test_compile_compliance_manifest_structure():
    """Verifies compiling SDLC deliverables into an immutable compliance manifest."""
    signoff = HumanSignoff(
        reviewer="Sasha",
        email="sasha@specops.dev",
        signature="ed25519:test_sig_abc123",
        timestamp="2026-09-29T18:00:00Z",
    )
    deliverables = [
        ComplianceDeliverable(
            task_id="TASK-0031",
            prd_id="PRD-0002",
            story_ids=["US-0056", "US-0114"],
            commit_sha="913d0f28b7891234567890abcdef1234567890ab",
            prompt_sha256="11" * 32,
            test_results_digest="22" * 32,
            human_signoff=signoff,
            gherkin_scenarios=["Scenario: Generating a deterministic SOC2 compliance audit package"],
        ),
        ComplianceDeliverable(
            task_id="TASK-0030",
            prd_id="PRD-0002",
            story_ids=["US-0055"],
            commit_sha="870bae08b7891234567890abcdef1234567890ab",
            prompt_sha256="33" * 32,
            test_results_digest="44" * 32,
            human_signoff=signoff,
            gherkin_scenarios=["Scenario: Verifying commit signature threshold"],
        ),
    ]

    manifest = compile_compliance_manifest(deliverables, standard="soc2", generated_at="2026-09-29T18:30:00Z")

    assert manifest.standard == "soc2"
    assert manifest.tree_size == 2
    assert manifest.version == "1.0.0"
    assert manifest.serialization == "RFC8785"
    assert manifest.leaf_prefix == "00"
    assert manifest.node_prefix == "01"
    assert manifest.leaves[0].entity_id == "TASK-0030"
    assert manifest.leaves[1].entity_id == "TASK-0031"

    valid, errors = verify_compliance_manifest(manifest)
    assert valid
    assert len(errors) == 0


def test_verify_compliance_manifest_detects_out_of_band_tampering():
    """Verifies that out-of-band modifications to commit SHA, signoff, or root fail verification."""
    signoff = HumanSignoff("Sasha", "sasha@specops.dev", "sig:valid", "2026-09-29T18:00:00Z")
    deliv = ComplianceDeliverable(
        task_id="TASK-0031",
        prd_id="PRD-0002",
        story_ids=["US-0056"],
        commit_sha="abc1234",
        prompt_sha256="11" * 32,
        test_results_digest="22" * 32,
        human_signoff=signoff,
    )
    manifest = compile_compliance_manifest([deliv], standard="soc2")
    manifest_dict = manifest.to_dict()

    # Tamper with commit SHA in deliverable data
    manifest_dict["leaves"][0]["data"]["commit_sha"] = "tampered_commit_sha"
    valid, errors = verify_compliance_manifest(manifest_dict)
    assert not valid
    assert any("Tampered deliverable 'TASK-0031'" in err for err in errors)

    # Tamper with signoff signature
    manifest_dict_2 = manifest.to_dict()
    manifest_dict_2["leaves"][0]["data"]["human_signoff"]["signature"] = "forged_signature"
    valid_2, errors_2 = verify_compliance_manifest(manifest_dict_2)
    assert not valid_2
    assert any("TASK-0031" in err for err in errors_2)

    # Tamper with claimed root hash
    manifest_dict_3 = manifest.to_dict()
    manifest_dict_3["root_hash"] = "00" * 32
    valid_3, errors_3 = verify_compliance_manifest(manifest_dict_3)
    assert not valid_3
    assert any("Merkle root mismatch" in err for err in errors_3)


def test_extract_repo_compliance_deliverables(tmp_path: Path):
    """Verifies extracting compliance deliverables from completed task backlog files."""
    complete_dir = tmp_path / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True)

    task_content = """---
id: '0030'
title: Dual Custody Commit Signoff
status: Complete
governing_prds:
  - PRD-0002
governing_stories:
  - US-0055
target_bc: security
---
# TASK-0030: Dual Custody Commit Signoff
Task details here.
"""
    (complete_dir / "0030-dual-custody.md").write_text(task_content, encoding="utf-8")

    deliverables = extract_repo_compliance_deliverables(tmp_path)
    assert len(deliverables) == 1
    d = deliverables[0]
    assert d.task_id == "TASK-0030"
    assert d.prd_id == "PRD-0002"
    assert "US-0055" in d.story_ids
    assert d.human_signoff is not None
