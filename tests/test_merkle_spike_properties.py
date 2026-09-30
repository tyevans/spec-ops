"""Generative property-based tests for RFC 8785 canonicalization and Merkle compliance (ADR-0009)."""

from __future__ import annotations

import copy
import json
import random
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.security.merkle import (
    ComplianceDeliverable,
    HumanSignoff,
    MerkleTree,
    canonical_json_encode,
    compile_compliance_manifest,
    hash_leaf,
    verify_compliance_manifest,
    verify_inclusion_proof,
)

# Recursive JSON value strategy for testing canonical serialization
json_primitives = st.none() | st.booleans() | st.integers(min_value=-100000, max_value=100000) | st.text(max_size=30)
json_values = st.recursive(
    json_primitives,
    lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(min_size=1, max_size=15), children, max_size=5),
    max_leaves=15,
)


def _shuffle_dict_keys(val: Any) -> Any:
    """Recursively reconstructs dictionaries with randomized key insertion orders."""
    if isinstance(val, dict):
        items = list(val.items())
        random.shuffle(items)
        return {k: _shuffle_dict_keys(v) for k, v in items}
    if isinstance(val, list):
        return [_shuffle_dict_keys(x) for x in val]
    return val


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(val=json_values)
def test_canonical_json_encode_insertion_order_invariance(val: Any):
    """Property: Canonical JSON encoding produces identical bytes regardless of key insertion order."""
    val_a = copy.deepcopy(val)
    val_b = _shuffle_dict_keys(copy.deepcopy(val))

    bytes_a = canonical_json_encode(val_a)
    bytes_b = canonical_json_encode(val_b)
    assert bytes_a == bytes_b
    assert hash_leaf(val_a) == hash_leaf(val_b)


@settings(max_examples=35, deadline=None)
@given(
    task_num=st.integers(min_value=1, max_value=999),
    reviewer=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=2, max_size=20),
    commit_hex=st.text(alphabet="0123456789abcdef", min_size=40, max_size=40),
)
def test_deliverable_hash_determinism_across_whitespace_and_order(task_num: int, reviewer: str, commit_hex: str):
    """Property: Deliverable leaf hash is invariant to key order or source whitespace variations."""
    signoff = HumanSignoff(
        reviewer=reviewer,
        email=f"{reviewer.lower()}@specops.dev",
        signature=f"sig:{commit_hex[:8]}",
        timestamp="2026-09-29T18:00:00Z",
    )
    deliverable = ComplianceDeliverable(
        task_id=f"TASK-{task_num:04d}",
        prd_id="PRD-0002",
        story_ids=["US-0056", "US-0114"],
        commit_sha=commit_hex,
        prompt_sha256="aa" * 32,
        test_results_digest="bb" * 32,
        human_signoff=signoff,
    )

    dict_original = deliverable.to_dict()
    dict_shuffled = _shuffle_dict_keys(copy.deepcopy(dict_original))

    # Test whitespace variation in raw JSON before deserialization
    raw_formatted = json.dumps(dict_original, indent=4)
    dict_from_formatted = json.loads(raw_formatted)

    hash1 = deliverable.compute_leaf_hash()
    hash2 = hash_leaf(dict_shuffled)
    hash3 = hash_leaf(dict_from_formatted)

    assert hash1 == hash2 == hash3


@settings(max_examples=30, deadline=None)
@given(
    leaf_count=st.integers(min_value=1, max_value=30),
)
def test_merkle_inclusion_proof_holds_for_all_tree_sizes(leaf_count: int):
    """Property: For any valid tree of size N and leaf index m, inclusion proof verification passes."""
    leaves = [hash_leaf({"entity_index": i, "salt": "random_val"}) for i in range(leaf_count)]
    tree = MerkleTree(leaves)

    for m in range(leaf_count):
        proof = tree.generate_proof(m)
        assert proof.leaf_index == m
        assert proof.root_hash == tree.root_hash
        assert proof.tree_size == leaf_count
        assert verify_inclusion_proof(leaves[m], proof)


@settings(max_examples=25, deadline=None)
@given(
    deliverable_count=st.integers(min_value=1, max_value=8),
)
def test_manifest_compilation_invariant_to_deliverable_input_ordering(deliverable_count: int):
    """Property: Compiling compliance manifest yields identical root hash regardless of deliverable list order."""
    deliverables: list[ComplianceDeliverable] = []
    for i in range(deliverable_count):
        d = ComplianceDeliverable(
            task_id=f"TASK-{i:04d}",
            prd_id="PRD-0002",
            story_ids=[f"US-{(i + 10):04d}"],
            commit_sha=f"{i:040x}",
            prompt_sha256=f"{i:064x}",
            test_results_digest=f"digest-{i}",
        )
        deliverables.append(d)

    shuffled_deliverables = copy.deepcopy(deliverables)
    random.shuffle(shuffled_deliverables)

    fixed_time = "2026-09-29T18:00:00Z"
    manifest_a = compile_compliance_manifest(deliverables, standard="soc2", generated_at=fixed_time)
    manifest_b = compile_compliance_manifest(shuffled_deliverables, standard="soc2", generated_at=fixed_time)

    assert manifest_a.root_hash == manifest_b.root_hash
    assert manifest_a.tree_size == manifest_b.tree_size

    valid_a, errs_a = verify_compliance_manifest(manifest_a)
    valid_b, errs_b = verify_compliance_manifest(manifest_b)
    assert valid_a and len(errs_a) == 0
    assert valid_b and len(errs_b) == 0


@settings(max_examples=25, deadline=None)
@given(
    target_idx=st.integers(min_value=0, max_value=4),
    mutation_val=st.text(min_size=1, max_size=20),
)
def test_manifest_tamper_sensitivity_guarantee(target_idx: int, mutation_val: str):
    """Property: Mutating any field in any deliverable within a manifest unconditionally breaks integrity."""
    deliverables = [
        ComplianceDeliverable(
            task_id=f"TASK-{i:04d}",
            prd_id="PRD-0002",
            story_ids=[f"US-{i:04d}"],
            commit_sha=f"{i:040x}",
            prompt_sha256=f"{i:064x}",
            test_results_digest=f"results-{i}",
        )
        for i in range(5)
    ]
    manifest = compile_compliance_manifest(deliverables, standard="soc2")
    manifest_dict = manifest.to_dict()

    # Mutate a field in deliverable data at target_idx
    manifest_dict["leaves"][target_idx]["data"]["commit_sha"] = f"tampered_{mutation_val}"
    is_valid, errors = verify_compliance_manifest(manifest_dict)

    assert not is_valid
    assert len(errors) > 0
    corrupted_task = deliverables[target_idx].task_id
    assert any(corrupted_task in err for err in errors)
