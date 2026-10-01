"""Hypothesis generative property invariant tests for Merkle compliance manifest (ADR-0009, ADR-0016)."""

from __future__ import annotations

import random
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.security.merkle_manifest import (
    EMPTY_ROOT_HASH,
    build_merkle_manifest,
    generate_file_proof,
    verify_file_proof,
)

safe_segment = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_.-", min_size=1, max_size=20)
safe_path = st.lists(safe_segment, min_size=1, max_size=3).map(lambda parts: "/".join(parts))
arbitrary_artifacts = st.dictionaries(
    keys=safe_path,
    values=st.binary(min_size=0, max_size=500),
    min_size=1,
    max_size=20,
)


@settings(max_examples=50, deadline=None)
@given(artifacts=arbitrary_artifacts)
def test_merkle_manifest_construction_deterministic(artifacts: dict[str, bytes]):
    """Invariant: Generating a Merkle manifest twice for identical inputs produces identical root hash and leaves."""
    fixed_ts = "2026-10-01T12:00:00Z"
    manifest1 = build_merkle_manifest(artifacts, standard="soc2", generated_at=fixed_ts)
    manifest2 = build_merkle_manifest(artifacts, standard="soc2", generated_at=fixed_ts)

    assert manifest1.root_hash == manifest2.root_hash
    assert manifest1.tree_size == manifest2.tree_size
    assert manifest1.leaves == manifest2.leaves
    assert manifest1.to_json() == manifest2.to_json()


@settings(max_examples=50, deadline=None)
@given(artifacts=arbitrary_artifacts)
def test_merkle_manifest_order_independent(artifacts: dict[str, bytes]):
    """Invariant: Merkle tree construction is order-independent regardless of dictionary insertion order."""
    items = list(artifacts.items())
    shuffled_items = list(items)
    random.shuffle(shuffled_items)
    shuffled_artifacts = dict(shuffled_items)

    fixed_ts = "2026-10-01T12:00:00Z"
    manifest_orig = build_merkle_manifest(artifacts, standard="soc2", generated_at=fixed_ts)
    manifest_shuffled = build_merkle_manifest(shuffled_artifacts, standard="soc2", generated_at=fixed_ts)

    assert manifest_orig.root_hash == manifest_shuffled.root_hash
    assert manifest_orig.tree_size == manifest_shuffled.tree_size
    assert [l["entity_id"] for l in manifest_orig.leaves] == [l["entity_id"] for l in manifest_shuffled.leaves]


@settings(max_examples=50, deadline=None)
@given(artifacts=arbitrary_artifacts)
def test_merkle_manifest_leaf_mutation_alters_root_hash(artifacts: dict[str, bytes]):
    """Invariant: Mutating the content of any single leaf artifact strictly alters the computed Merkle root."""
    fixed_ts = "2026-10-01T12:00:00Z"
    original_manifest = build_merkle_manifest(artifacts, standard="soc2", generated_at=fixed_ts)

    # Pick a target file and mutate its content
    target_path = random.choice(list(artifacts.keys()))
    original_content = artifacts[target_path]
    mutated_content = original_content + b"\x00_tampered" if original_content != b"\xff" else b"\x00"

    mutated_artifacts = dict(artifacts)
    mutated_artifacts[target_path] = mutated_content

    mutated_manifest = build_merkle_manifest(mutated_artifacts, standard="soc2", generated_at=fixed_ts)
    assert mutated_manifest.root_hash != original_manifest.root_hash


@settings(max_examples=50, deadline=None)
@given(artifacts=arbitrary_artifacts)
def test_merkle_manifest_path_mutation_alters_root_hash(artifacts: dict[str, bytes]):
    """Invariant: Renaming a file path (even with identical content) alters the computed Merkle root."""
    fixed_ts = "2026-10-01T12:00:00Z"
    original_manifest = build_merkle_manifest(artifacts, standard="soc2", generated_at=fixed_ts)

    target_path = random.choice(list(artifacts.keys()))
    content = artifacts[target_path]
    renamed_artifacts = dict(artifacts)
    del renamed_artifacts[target_path]
    renamed_artifacts[f"{target_path}_renamed.txt"] = content

    renamed_manifest = build_merkle_manifest(renamed_artifacts, standard="soc2", generated_at=fixed_ts)
    assert renamed_manifest.root_hash != original_manifest.root_hash


@settings(max_examples=40, deadline=None)
@given(artifacts=arbitrary_artifacts)
def test_merkle_manifest_inclusion_proof_validity(artifacts: dict[str, bytes]):
    """Invariant: Every file in a manifest yields a valid inclusion proof, and corrupted proofs fail verification."""
    manifest = build_merkle_manifest(artifacts, standard="soc2")
    target_path = random.choice(list(artifacts.keys()))

    proof = generate_file_proof(manifest, target_path)
    assert verify_file_proof(proof) is True
    assert verify_file_proof(proof, root_hash=manifest.root_hash) is True

    # Mutating root fails verification
    assert verify_file_proof(proof, root_hash="00" * 32) is False

    # Mutating leaf hash fails verification
    tampered_proof = dict(proof)
    tampered_proof["leaf_hash"] = "ff" * 32
    assert verify_file_proof(tampered_proof) is False


def test_merkle_manifest_empty_invariants():
    """Invariant: An empty artifact dictionary yields tree size 0 and EMPTY_ROOT_HASH."""
    manifest = build_merkle_manifest({})
    assert manifest.tree_size == 0
    assert manifest.root_hash == EMPTY_ROOT_HASH
    assert len(manifest.leaves) == 0
