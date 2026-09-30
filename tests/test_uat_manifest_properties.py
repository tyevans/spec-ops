"""Hypothesis property-based tests for living UAT receipts and release manifests."""

from __future__ import annotations

import datetime
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.manifest import compute_manifest_signature
from spec_ops.prd.uat_receipt import (
    OutcomeTestMapping,
    compute_delivery_readiness,
    reconcile_signoffs,
    serialize_canonical_json,
    validate_uat_signoff_schema,
)


@given(
    st.text(min_size=1, max_size=20),
    st.text(min_size=64, max_size=64, alphabet="0123456789abcdef"),
    st.lists(
        st.fixed_dictionaries({
            "id": st.sampled_from(["TASK-0001", "TASK-0002", "TASK-0003"]),
            "commit_sha": st.text(min_size=7, max_size=40, alphabet="0123456789abcdef"),
        }),
        max_size=5,
    ),
    st.fixed_dictionaries({
        "status": st.sampled_from(["Passed (CI)", "Failed (CI)"]),
        "total_scenarios": st.integers(min_value=0, max_value=100),
        "failed_scenarios": st.integers(min_value=0, max_value=10),
    }),
    st.fixed_dictionaries({
        "status": st.sampled_from(["Approved", "Pending PM"]),
        "total_outcomes": st.integers(min_value=1, max_value=20),
        "approved_outcomes": st.integers(min_value=0, max_value=20),
    }),
)
@settings(max_examples=40)
def test_manifest_signature_determinism_and_format(
    prd_id: str,
    tree_digest: str,
    tasks: list[dict[str, str]],
    test_sum: dict[str, Any],
    uat_sum: dict[str, Any],
):
    """Property: Manifest signature is a deterministic 64-character hex SHA-256 digest."""
    sig1 = compute_manifest_signature(prd_id, tree_digest, tasks, test_sum, uat_sum)
    sig2 = compute_manifest_signature(prd_id, tree_digest, tasks, test_sum, uat_sum)
    assert sig1 == sig2
    assert len(sig1) == 64
    assert all(c in "0123456789abcdef" for c in sig1)


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["Passed (CI)", "Failed (CI)", "Pending (CI)"]),
            st.sampled_from(["Approved", "Pending PM", "Rejected"]),
        ),
        min_size=0,
        max_size=30,
    )
)
@settings(max_examples=40)
def test_delivery_readiness_bounds(pairs: list[tuple[str, str]]):
    """Property: Delivery readiness is strictly bounded between 0.0 and 100.0."""
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
    st.tuples(
        st.sampled_from(["1", "2"]),
        st.integers(min_value=1700000000, max_value=1700000500),
        st.integers(min_value=1700000501, max_value=1700001000),
    )
)
@settings(max_examples=30)
def test_reconcile_signoffs_monotonic_progress(data: tuple[str, int, int]):
    """Property: Newer timestamps strictly supersede older timestamps during reconciliation."""
    out_id, t_early, t_late = data
    dt_early = datetime.datetime.fromtimestamp(t_early, datetime.timezone.utc).isoformat()
    dt_late = datetime.datetime.fromtimestamp(t_late, datetime.timezone.utc).isoformat()

    key = f"PRD-0001:{out_id}"
    early_state = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            key: {
                "outcome_id": out_id,
                "prd_id": "PRD-0001",
                "status": "Pending",
                "reviewer": "Taylor <taylor@example.com>",
                "timestamp": dt_early,
                "notes": "Early review",
            }
        },
    }
    late_state = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            key: {
                "outcome_id": out_id,
                "prd_id": "PRD-0001",
                "status": "Approved",
                "reviewer": "Taylor <taylor@example.com>",
                "timestamp": dt_late,
                "notes": "Late approved review",
            }
        },
    }

    # Reconciling in either order results in the late approved state
    merged1 = reconcile_signoffs(early_state, late_state)
    merged2 = reconcile_signoffs(late_state, early_state)

    assert merged1["signoffs"][key]["status"] == "Approved"
    assert merged1["signoffs"][key]["timestamp"] == dt_late
    assert merged1["signoffs"][key]["notes"] == "Late approved review"
    assert merged1["signoffs"][key]["status"] == merged2["signoffs"][key]["status"]
    assert len(merged1["signoffs"][key]["history"]) == 2
