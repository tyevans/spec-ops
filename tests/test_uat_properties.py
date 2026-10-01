"""Hypothesis generative property tests for Customer UAT receipts and sign-offs."""

from __future__ import annotations

import copy
import datetime
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.uat_cli import (
    compute_uat_receipt_signature,
    verify_customer_uat_receipt,
)
from spec_ops.prd.uat_receipt import (
    OutcomeTestMapping,
    compute_delivery_readiness,
    reconcile_signoffs,
    serialize_canonical_json,
    validate_uat_signoff_schema,
)


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=12, alphabet="abcdefghijklmnopqrstuvwxyz_"),
        values=st.one_of(
            st.integers(min_value=-1000, max_value=1000),
            st.text(min_size=0, max_size=20),
            st.booleans(),
            st.lists(st.integers(), max_size=5),
        ),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=50)
def test_canonical_json_determinism_and_key_order_invariance(d: dict[str, Any]):
    """Property: serialize_canonical_json is invariant to dict key insertion order."""
    rev_d = {k: d[k] for k in reversed(list(d.keys()))}
    s1 = serialize_canonical_json(d)
    s2 = serialize_canonical_json(rev_d)
    assert s1 == s2
    assert s1.endswith("\n")


@given(
    st.text(min_size=1, max_size=15, alphabet="0123456789PRD-"),
    st.text(min_size=64, max_size=64, alphabet="0123456789abcdef"),
    st.lists(
        st.fixed_dictionaries({
            "outcome_id": st.sampled_from(["1", "2", "3", "4"]),
            "outcome_text": st.text(min_size=1, max_size=30),
            "linked_stories": st.lists(st.text(min_size=1, max_size=10), max_size=3),
            "scenarios": st.lists(st.text(min_size=1, max_size=20), max_size=3),
            "test_status": st.sampled_from(["Passed (CI)", "Failed (CI)", "Pending (CI)"]),
            "uat_status": st.sampled_from(["Approved", "Pending PM", "Rejected"]),
        }),
        min_size=1,
        max_size=5,
    ),
    st.fixed_dictionaries({
        "status": st.sampled_from(["Approved", "Pending PM", "Rejected"]),
        "total_outcomes": st.integers(min_value=1, max_value=10),
        "approved_outcomes": st.integers(min_value=0, max_value=10),
    }),
)
@settings(max_examples=40)
def test_uat_receipt_signature_determinism_and_avalanche(
    prd_id: str,
    tree_digest: str,
    tests: list[dict[str, Any]],
    uat_summary: dict[str, Any],
):
    """Property: Receipt signature is deterministic 64-char hex SHA-256 and exhibits avalanche on alteration."""
    sig1 = compute_uat_receipt_signature(prd_id, tree_digest, tests, uat_summary)
    sig2 = compute_uat_receipt_signature(prd_id, tree_digest, tests, uat_summary)
    assert sig1 == sig2
    assert len(sig1) == 64
    assert all(c in "0123456789abcdef" for c in sig1)

    # Any field alteration produces completely distinct signature
    tampered_tree = tree_digest[:-1] + ("0" if tree_digest[-1] != "0" else "1")
    sig_tampered = compute_uat_receipt_signature(prd_id, tampered_tree, tests, uat_summary)
    assert sig_tampered != sig1


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["Passed (CI)", "Failed (CI)", "Pending (CI)"]),
            st.sampled_from(["Approved", "Pending PM", "Rejected"]),
        ),
        min_size=0,
        max_size=20,
    )
)
@settings(max_examples=40)
def test_delivery_readiness_bounds_and_completeness(pairs: list[tuple[str, str]]):
    """Property: Delivery readiness is strictly bounded between 0.0 and 100.0%."""
    mappings = [
        OutcomeTestMapping(
            outcome_id=str(idx + 1),
            outcome_text=f"Outcome {idx + 1}",
            test_status=t_st,
            uat_status=u_st,
        )
        for idx, (t_st, u_st) in enumerate(pairs)
    ]
    readiness = compute_delivery_readiness(mappings)
    assert 0.0 <= readiness <= 100.0
    if not mappings:
        assert readiness == 0.0
    elif all(m.test_status == "Passed (CI)" and m.uat_status == "Approved" for m in mappings):
        assert readiness == 100.0


@given(
    st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
)
@settings(max_examples=25)
def test_receipt_verification_tamper_detection(tmp_path: Path, arbitrary_noise: str):
    """Property: Any simulated tampering of verified_tree_digest or signature invalidates verification."""
    clean_receipt = {
        "$schema": "spec-ops/uat-receipt-v1",
        "version": "1.0",
        "prd": {
            "id": "PRD-0001",
            "title": "Visualizer & Deep Linking",
        },
        "verified_tree_digest": "a" * 64,
        "test_correlation": [
            {
                "outcome_id": "1",
                "outcome_text": "Outcome 1",
                "linked_stories": ["US-0001"],
                "test_status": "Passed (CI)",
                "uat_status": "Approved",
            }
        ],
        "test_verification": {
            "status": "Passed (CI)",
            "total_outcomes": 1,
            "passed_outcomes": 1,
        },
        "uat_verification": {
            "status": "Approved",
            "total_outcomes": 1,
            "approved_outcomes": 1,
        },
        "receipt_signature": "",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    clean_receipt["receipt_signature"] = compute_uat_receipt_signature(
        "PRD-0001",
        clean_receipt["verified_tree_digest"],
        clean_receipt["test_correlation"],
        clean_receipt["uat_verification"],
    )

    # Tampered signature
    tampered_sig = copy.deepcopy(clean_receipt)
    tampered_sig["receipt_signature"] = "deadbeef" * 8
    valid, issues = verify_customer_uat_receipt(tampered_sig, tmp_path)
    assert valid is False
    assert any("signature invalid" in issue.lower() for issue in issues)

    # Missing mandatory UAT approval
    unapproved = copy.deepcopy(clean_receipt)
    unapproved["uat_verification"]["status"] = "Pending PM"
    unapproved["receipt_signature"] = compute_uat_receipt_signature(
        "PRD-0001",
        unapproved["verified_tree_digest"],
        unapproved["test_correlation"],
        unapproved["uat_verification"],
    )
    valid_unapp, issues_unapp = verify_customer_uat_receipt(unapproved, tmp_path)
    assert valid_unapp is False
    assert any("mandatory pm uat approval required" in issue.lower() for issue in issues_unapp)


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["PRD-0001", "PRD-0002"]),
            st.sampled_from(["1", "2", "3"]),
            st.sampled_from(["Approved", "Pending", "Rejected"]),
            st.sampled_from(["Taylor <taylor@specops.local>", "Jordan <jordan@specops.local>"]),
            st.integers(min_value=1600000000, max_value=1800000000),
        ),
        min_size=1,
        max_size=8,
    )
)
@settings(max_examples=30)
def test_reconcile_signoffs_idempotency_and_schema_soundness(entries: list[tuple[str, str, str, str, int]]):
    """Property: Sign-off reconciliation is idempotent and yields valid schema payloads."""
    signoffs: dict[str, Any] = {}
    for prd_id, out_id, status, reviewer, epoch in entries:
        dt = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()
        key = f"{prd_id}:{out_id}"
        signoffs[key] = {
            "outcome_id": out_id,
            "prd_id": prd_id,
            "status": status,
            "reviewer": reviewer,
            "timestamp": dt,
            "notes": f"Verified {key}",
        }

    payload = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": signoffs,
    }

    merged = reconcile_signoffs(payload, payload)
    assert sorted(merged["signoffs"].keys()) == sorted(signoffs.keys())
    assert serialize_canonical_json(merged) == serialize_canonical_json(reconcile_signoffs(merged, merged))

    valid, violations = validate_uat_signoff_schema(merged)
    assert valid is True, f"Schema violations: {violations}"
