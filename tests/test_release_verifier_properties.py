"""Hypothesis generative property tests for cryptographic release verification (ADR-0009, ADR-0014)."""

from __future__ import annotations

import base64
import copy
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

from spec_ops.security.ed25519 import (
    ed25519_keypair,
    ed25519_sign,
    ed25519_verify,
    ssh_decode_ed25519_pub,
    ssh_encode_ed25519_pub,
)
from spec_ops.security.release_verifier import (
    AuthorizedSigner,
    parse_allowed_signers,
    sign_release_manifest,
    verify_release_manifest_data,
)

# Strategies
seeds_strategy = st.binary(min_size=32, max_size=32)
payloads_strategy = st.binary(min_size=0, max_size=500)
clean_names = st.from_regex(r"^[a-zA-Z0-9_.-]+$", fullmatch=True)
clean_domains = st.from_regex(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$", fullmatch=True)


@given(seed=seeds_strategy, payload=payloads_strategy)
@settings(max_examples=25)
def test_property_ed25519_sign_verify_correctness(seed: bytes, payload: bytes):
    """Property: Ed25519 verification returns True if and only if payload and signature match authentic key."""
    _, pub = ed25519_keypair(seed)
    sig = ed25519_sign(seed, pub, payload)

    # Authentic key and payload -> True
    assert ed25519_verify(pub, payload, sig) is True

    # Tampered payload -> False
    tampered_payload = payload + b"!"
    assert ed25519_verify(pub, tampered_payload, sig) is False

    # Different keypair -> False
    diff_seed = bytes((b ^ 0xFF) for b in seed)
    _, diff_pub = ed25519_keypair(diff_seed)
    assert ed25519_verify(diff_pub, payload, sig) is False


@given(seed=seeds_strategy, payload=payloads_strategy, byte_idx=st.integers(min_value=0, max_value=63))
@settings(max_examples=25)
def test_property_ed25519_corrupted_signature_rejection(seed: bytes, payload: bytes, byte_idx: int):
    """Property: Any bit flip in the signature causes verification to return False."""
    _, pub = ed25519_keypair(seed)
    sig = bytearray(ed25519_sign(seed, pub, payload))
    sig[byte_idx] ^= 0x01
    assert ed25519_verify(pub, payload, bytes(sig)) is False


@given(raw_key=st.binary(min_size=32, max_size=32))
@settings(max_examples=25)
def test_property_ssh_key_encoding_roundtrip(raw_key: bytes):
    """Property: Any 32-byte public key roundtrips through OpenSSH format encoding/decoding."""
    ssh_line = ssh_encode_ed25519_pub(raw_key)
    decoded = ssh_decode_ed25519_pub(ssh_line)
    assert decoded == raw_key


@given(
    user=clean_names,
    domain=clean_domains,
    seed=seeds_strategy,
    has_namespace=st.booleans(),
)
@settings(max_examples=25)
def test_property_allowed_signers_parsing(user: str, domain: str, seed: bytes, has_namespace: bool):
    """Property: .allowed_signers parser extracts matching principal, key type, and public key bytes."""
    _, pub = ed25519_keypair(seed)
    email = f"{user}@{domain}".lower()
    ssh_line = ssh_encode_ed25519_pub(pub)

    ns_clause = 'namespaces="file,git" ' if has_namespace else ""
    line = f"{email} {ns_clause}{ssh_line} Comment for {user}\n"

    parsed = parse_allowed_signers(line)
    assert len(parsed) == 1
    record = parsed[0]
    assert email in record.principals
    assert record.key_type == "ssh-ed25519"
    assert record.pubkey_bytes == pub
    if has_namespace:
        assert "file" in record.namespaces
        assert "git" in record.namespaces


@given(
    seed=seeds_strategy,
    prd_num=st.integers(min_value=1, max_value=9999),
    tamper_field=st.sampled_from(["verified_tree_digest", "completed_tasks", "uat_verification"]),
)
@settings(max_examples=25)

def test_property_manifest_verification_integrity(seed: bytes, prd_num: int, tamper_field: str):
    """Property: Tampering with any signed manifest field causes verification to fail."""
    _, pub = ed25519_keypair(seed)
    signer = "sasha@specops.dev"
    prd_id = f"PRD-{str(prd_num).zfill(4)}"

    manifest = {
        "$schema": "spec-ops/release-manifest-v1",
        "prd": {"id": prd_id, "title": "Test PRD", "persona": "Sasha"},
        "verified_tree_digest": "e" * 64,
        "completed_tasks": [{"id": f"TASK-{prd_num}", "commit_sha": "abc1234"}],
        "test_verification": {"status": "Passed (CI)", "failed_scenarios": 0},
        "uat_verification": {"status": "Approved"},
    }

    signed = sign_release_manifest(manifest, seed, signer, algorithm="ed25519")
    auth_signer = AuthorizedSigner(
        principals=[signer],
        key_type="ssh-ed25519",
        pubkey_bytes=pub,
        raw_key="",
    )

    # Valid check
    valid_res = verify_release_manifest_data(signed, [auth_signer])
    assert valid_res.valid is True
    assert len(valid_res.errors) == 0

    # Tampered check
    tampered = copy.deepcopy(signed)
    if tamper_field == "verified_tree_digest":
        tampered["verified_tree_digest"] = "f" * 64
    elif tamper_field == "completed_tasks":
        tampered["completed_tasks"].append({"id": "TASK-9999", "commit_sha": "bad"})
    elif tamper_field == "uat_verification":
        tampered["uat_verification"]["status"] = "Rejected"

    tampered_res = verify_release_manifest_data(tampered, [auth_signer])
    assert tampered_res.valid is False
    assert any("signature mismatch" in err.lower() for err in tampered_res.errors)
