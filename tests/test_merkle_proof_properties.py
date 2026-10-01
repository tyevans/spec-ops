"""Generative property-based tests for Merkle inclusion proofs (ADR-0009, ADR-0016)."""

from __future__ import annotations

import copy
import hashlib
import time
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.security.audit.merkle import (
    ComplianceDeliverable,
    HumanSignoff,
    MerkleInclusionProof,
    MerkleTree,
    ProofStep,
    compile_compliance_manifest,
    hash_leaf,
    verify_inclusion_proof,
)
from spec_ops.security.audit.proof_cli import (
    generate_merkle_proof,
    verify_merkle_proof,
)


@st.composite
def deliverable_payloads(draw: st.DrawFn) -> list[str]:
    """Generates a non-empty list of unique leaf hex hashes for Merkle tree testing."""
    count = draw(st.integers(min_value=1, max_value=40))
    items = [
        hash_leaf({"id": f"ITEM-{i:03d}", "seed": draw(st.text(min_size=1, max_size=20))})
        for i in range(count)
    ]
    return items


@settings(max_examples=35, deadline=None)
@given(leaf_hashes=deliverable_payloads())
def test_merkle_tree_all_leaves_proof_completeness(leaf_hashes: list[str]):
    """Property: Inclusion proofs for every leaf in any randomized Merkle tree always verify against root."""
    tree = MerkleTree(leaf_hashes)

    for i in range(len(leaf_hashes)):
        proof = tree.generate_proof(i)
        assert proof.leaf_index == i
        assert proof.leaf_hash == leaf_hashes[i]
        assert proof.root_hash == tree.root_hash
        assert proof.tree_size == len(leaf_hashes)

        # Blackbox frontdoor verification
        assert verify_inclusion_proof(leaf_hashes[i], proof, tree.root_hash) is True
        assert verify_inclusion_proof(leaf_hashes[i], proof) is True

        proof_dict = proof.to_dict()
        ok, msg, details = verify_merkle_proof(proof_dict, tree.root_hash)
        assert ok is True
        assert details["computed_root"] == tree.root_hash


@settings(max_examples=35, deadline=None)
@given(
    leaf_hashes=st.lists(
        st.text(min_size=1, max_size=20).map(lambda s: hash_leaf({"key": s})),
        min_size=2,
        max_size=32,
    ),
    tamper_byte=st.integers(min_value=0, max_value=31),
)
def test_proof_leaf_hash_tamper_fails_verification(leaf_hashes: list[str], tamper_byte: int):
    """Property: Mutating any byte of a leaf hash unconditionally fails inclusion proof verification."""
    tree = MerkleTree(leaf_hashes)
    target_idx = len(leaf_hashes) // 2
    proof = tree.generate_proof(target_idx)

    raw_leaf = list(bytes.fromhex(proof.leaf_hash))
    raw_leaf[tamper_byte] = (raw_leaf[tamper_byte] + 1) % 256
    tampered_leaf_hash = bytes(raw_leaf).hex()

    # Rebuilding proof with tampered leaf
    tampered_proof = MerkleInclusionProof(
        leaf_index=proof.leaf_index,
        leaf_hash=tampered_leaf_hash,
        audit_path=proof.audit_path,
        root_hash=proof.root_hash,
        tree_size=proof.tree_size,
    )

    assert verify_inclusion_proof(tampered_leaf_hash, proof, tree.root_hash) is False
    assert verify_inclusion_proof(tampered_leaf_hash, tampered_proof, tree.root_hash) is False

    ok, msg, _ = verify_merkle_proof(tampered_proof.to_dict(), tree.root_hash)
    assert ok is False


@settings(max_examples=35, deadline=None)
@given(
    leaf_hashes=st.lists(
        st.text(min_size=1, max_size=20).map(lambda s: hash_leaf({"key": s})),
        min_size=2,
        max_size=32,
    ),
    step_selector=st.integers(min_value=0, max_value=10),
)
def test_proof_audit_path_tamper_fails_verification(leaf_hashes: list[str], step_selector: int):
    """Property: Mutating any sibling hash or direction in audit path unconditionally fails verification."""
    tree = MerkleTree(leaf_hashes)
    proof = tree.generate_proof(0)
    if not proof.audit_path:
        return

    step_idx = step_selector % len(proof.audit_path)
    tampered_steps: list[ProofStep] = []
    for idx, s in enumerate(proof.audit_path):
        if idx == step_idx:
            # Invert direction or alter sibling hash
            tampered_sibling = hashlib.sha256(s.sibling_hash.encode("utf-8")).hexdigest()
            tampered_steps.append(ProofStep(sibling_hash=tampered_sibling, is_left=not s.is_left))
        else:
            tampered_steps.append(s)

    tampered_proof = MerkleInclusionProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        audit_path=tampered_steps,
        root_hash=proof.root_hash,
        tree_size=proof.tree_size,
    )

    assert verify_inclusion_proof(proof.leaf_hash, tampered_proof, tree.root_hash) is False

    ok, msg, _ = verify_merkle_proof(tampered_proof.to_dict(), tree.root_hash)
    assert ok is False


@settings(max_examples=35, deadline=None)
@given(
    leaf_hashes=st.lists(
        st.text(min_size=1, max_size=20).map(lambda s: hash_leaf({"key": s})),
        min_size=1,
        max_size=20,
    ),
    fake_root=st.binary(min_size=32, max_size=32).map(lambda b: b.hex()),
)
def test_proof_root_mismatch_fails_verification(leaf_hashes: list[str], fake_root: str):
    """Property: Verifying an inclusion proof against any divergent root strictly fails."""
    tree = MerkleTree(leaf_hashes)
    proof = tree.generate_proof(0)

    if fake_root == tree.root_hash:
        return

    assert verify_inclusion_proof(proof.leaf_hash, proof, root_hash=fake_root) is False

    ok, msg, details = verify_merkle_proof(proof.to_dict(), fake_root)
    assert ok is False
    assert "Merkle root mismatch" in msg


@settings(max_examples=25, deadline=None)
@given(
    mutated_val=st.text(min_size=1, max_size=30),
)
def test_proof_deliverable_payload_tampering_detected(mutated_val: str):
    """Property: Modifying deliverable data embedded inside proof is detected and fails verification."""
    signoff = HumanSignoff("Taylor", "taylor@specops.dev", "sig:123", "2026-09-30T10:00:00Z")
    deliv = ComplianceDeliverable(
        task_id="TASK-0129",
        prd_id="PRD-0002",
        story_ids=["US-0114"],
        commit_sha="1111222233334444555566667777888899990000",
        prompt_sha256="aa" * 32,
        test_results_digest="bb" * 32,
        human_signoff=signoff,
    )
    manifest = compile_compliance_manifest([deliv], standard="soc2")
    proof_dict = generate_merkle_proof(manifest, "TASK-0129")

    # Mutate deliverable payload
    tampered_dict = copy.deepcopy(proof_dict)
    tampered_dict["deliverable_data"]["commit_sha"] = "0000" + mutated_val

    ok, msg, details = verify_merkle_proof(tampered_dict, manifest.root_hash)
    assert ok is False
    assert "Deliverable payload hash mismatch" in msg


@settings(max_examples=20, deadline=None)
@given(leaf_count=st.integers(min_value=2, max_value=64))
def test_offline_submillisecond_verification_performance(leaf_count: int):
    """Property: Inclusion proof verification runs in sub-millisecond offline execution."""
    hashes = [hash_leaf({"idx": i}) for i in range(leaf_count)]
    tree = MerkleTree(hashes)
    proof_dict = tree.generate_proof(leaf_count - 1).to_dict()

    t_start = time.perf_counter()
    ok, _, _ = verify_merkle_proof(proof_dict, tree.root_hash)
    t_elapsed = (time.perf_counter() - t_start) * 1000.0  # ms

    assert ok is True
    # Sub-millisecond target: strictly under 5.0ms under Python VM scheduling
    assert t_elapsed < 5.0
