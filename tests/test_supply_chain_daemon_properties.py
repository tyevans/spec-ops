"""Hypothesis generative property invariant tests for supply-chain lockfile daemon (ADR-0009, TASK-0157)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.security.supply_chain_daemon import (
    LockfileAttestation,
    LockfileIntegrityReport,
    SupplyChainSentinel,
)


@st.composite
def lockfile_with_single_byte_mutation(draw):
    """Generates base lockfile bytes and a mutated version differing by a single byte."""
    base_text = draw(
        st.text(
            min_size=10,
            max_size=2000,
            alphabet=st.characters(blacklist_categories=("Cs",)),
        )
    )
    base_bytes = bytearray(base_text.encode("utf-8"))
    if not base_bytes:
        base_bytes = bytearray(b"version = 1\n")

    idx = draw(st.integers(min_value=0, max_value=len(base_bytes) - 1))
    orig_byte = base_bytes[idx]

    mutation_type = draw(st.sampled_from(["replace", "insert", "delete"]))

    mutated_bytes = bytearray(base_bytes)
    if mutation_type == "replace":
        diff_byte = draw(st.integers(min_value=0, max_value=255).filter(lambda b: b != orig_byte))
        mutated_bytes[idx] = diff_byte
    elif mutation_type == "insert":
        ins_byte = draw(st.integers(min_value=0, max_value=255))
        mutated_bytes.insert(idx, ins_byte)
    else:  # delete
        if len(mutated_bytes) > 1:
            del mutated_bytes[idx]
        else:
            mutated_bytes.append(draw(st.integers(min_value=0, max_value=255)))

    return bytes(base_bytes), bytes(mutated_bytes)


@settings(max_examples=50, deadline=None)
@given(mutation_data=lockfile_with_single_byte_mutation())
def test_single_byte_alteration_produces_distinct_digest_and_deterministic_failure(
    tmp_path_factory, mutation_data
):
    """Invariant: Any single-byte alteration to lockfile text produces a distinct SHA-256 digest

    and causes verification to fail deterministically.
    """
    base_bytes, mutated_bytes = mutation_data
    assert base_bytes != mutated_bytes

    base_digest = hashlib.sha256(base_bytes).hexdigest()
    mutated_digest = hashlib.sha256(mutated_bytes).hexdigest()

    # Cryptographic invariant: different byte content must produce distinct SHA-256 digest
    assert base_digest != mutated_digest

    test_dir = tmp_path_factory.mktemp("lockfile_prop")
    uv_lock = test_dir / "uv.lock"
    pyp = test_dir / "pyproject.toml"

    pyp.write_text('[project]\nname = "property-test"\nversion = "0.1.0"\n', encoding="utf-8")
    uv_lock.write_bytes(base_bytes)

    sentinel = SupplyChainSentinel(test_dir)

    # Record baseline attestation
    attestation = sentinel.generate_attestation(test_dir)
    assert attestation.lockfile_sha256 == base_digest
    sentinel.record_attestation(test_dir, attestation)

    # Verify baseline is clean initially if lockfile matches
    initial_report = sentinel.verify_integrity(test_dir)
    assert initial_report.current_digest == base_digest
    assert initial_report.attested_digest == base_digest
    # Either clean or fails only if base was invalid TOML/pinning, but digests must match
    assert initial_report.current_digest == initial_report.attested_digest

    # Apply single-byte mutation
    uv_lock.write_bytes(mutated_bytes)

    # Verification MUST fail deterministically due to digest mismatch
    mutated_report = sentinel.verify_integrity(test_dir)
    assert mutated_report.is_clean is False
    assert mutated_report.current_digest == mutated_digest
    assert mutated_report.attested_digest == base_digest
    assert mutated_report.current_digest != mutated_report.attested_digest

    # Discrepancies must explicitly include the digest mismatch
    has_digest_mismatch = any(
        "lockfile digest mismatch" in d.lower() or "unauthorized supply-chain modification" in d.lower()
        for d in mutated_report.discrepancies
    )
    assert has_digest_mismatch is True


@settings(max_examples=30, deadline=None)
@given(
    pkg_count=st.integers(min_value=0, max_value=1000),
    is_valid=st.booleans(),
    discrepancies=st.lists(st.text(min_size=1, max_size=50), max_size=5),
)
def test_attestation_roundtrip_serialization_property(pkg_count, is_valid, discrepancies):
    """Invariant: LockfileAttestation serializes and deserializes losslessly."""
    att = LockfileAttestation(
        timestamp="2026-10-01T12:00:00+00:00",
        lockfile_sha256="a" * 64,
        pyproject_sha256="b" * 64,
        package_count=pkg_count,
        is_valid=is_valid,
        discrepancies=discrepancies,
    )
    d = att.to_dict()
    assert json.loads(json.dumps(d)) == d

    recovered = LockfileAttestation.from_dict(d)
    assert recovered.timestamp == att.timestamp
    assert recovered.lockfile_sha256 == att.lockfile_sha256
    assert recovered.pyproject_sha256 == att.pyproject_sha256
    assert recovered.package_count == att.package_count
    assert recovered.is_valid == att.is_valid
    assert recovered.discrepancies == att.discrepancies


@settings(max_examples=30, deadline=None)
@given(
    is_clean=st.booleans(),
    discrepancies=st.lists(st.text(min_size=1, max_size=50), max_size=5),
)
def test_integrity_report_summary_and_dict_properties(is_clean, discrepancies):
    """Invariant: LockfileIntegrityReport to_dict and summary conform to contract."""
    report = LockfileIntegrityReport(
        is_clean=is_clean,
        current_digest="c" * 64,
        attested_digest="d" * 64,
        discrepancies=discrepancies,
    )
    d = report.to_dict()
    assert d["is_clean"] == is_clean
    assert d["current_digest"] == "c" * 64
    assert d["attested_digest"] == "d" * 64
    assert d["discrepancies"] == discrepancies

    summary = report.summary()
    assert isinstance(summary, str)
    if is_clean:
        assert "verified" in summary.lower()
    else:
        assert "tampering" in summary.lower() or "discrepancies" in summary.lower()
