"""Hypothesis generative property tests for Customer UAT release gatekeeper determinism."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.uat_gatekeeper import (
    canonical_prd_id,
    compute_uat_token_signature,
    evaluate_uat_gate,
    export_uat_token,
)
from spec_ops.scaffold.init import init_project


@st.composite
def outcome_records_strategy(draw: st.DrawFn) -> list[dict[str, str]]:
    num_outcomes = draw(st.integers(min_value=1, max_value=8))
    statuses = ["Approved", "Pending", "Rejected"]
    records = []
    for i in range(1, num_outcomes + 1):
        status = draw(st.sampled_from(statuses))
        records.append(
            {
                "outcome_id": str(i),
                "outcome_text": f"Checkable requirement outcome {i}",
                "status": status,
                "reviewer": "Taylor Lead PM <taylor@specops.local>",
                "timestamp": "2026-10-01T12:00:00+00:00",
                "notes": "Testing notes",
            }
        )
    return records


@given(
    prd_num=st.integers(min_value=1, max_value=9999),
    tree_digest=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64),
    signer=st.text(min_size=3, max_size=40).filter(lambda s: "\n" not in s),
    outcomes=outcome_records_strategy(),
)
@settings(max_examples=50)
def test_token_signature_determinism_property(
    prd_num: int, tree_digest: str, signer: str, outcomes: list[dict[str, str]]
) -> None:
    """Property: compute_uat_token_signature is a pure deterministic function with no side-effects."""
    sig1 = compute_uat_token_signature(f"PRD-{prd_num}", tree_digest, signer, outcomes)
    sig2 = compute_uat_token_signature(f"PRD-{prd_num}", tree_digest, signer, outcomes)
    assert sig1 == sig2
    assert len(sig1) == 64


@given(
    prd_num=st.integers(min_value=1, max_value=9999),
)
@settings(max_examples=30)
def test_canonical_prd_id_property(prd_num: int) -> None:
    """Property: canonical_prd_id normalizes any PRD variation into standard PRD-XXXX format."""
    variants = [
        str(prd_num),
        f"prd-{prd_num}",
        f"PRD-{prd_num}",
        f"prd_{prd_num}",
        f"prd {prd_num}",
    ]
    expected = f"PRD-{str(prd_num).zfill(4)}"
    for v in variants:
        assert canonical_prd_id(v) == expected


def test_gate_decision_determinism(tmp_path: Path) -> None:
    """Property: Gate evaluation is idempotent and purely functional given repository state."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="DetermApp", target_dir=repo)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-0005-feature.md"
    prd_file.write_text(
        """---
id: PRD-0005
title: Feature
status: Accepted
---
# PRD-0005: Feature
## Checkable Outcomes
1. Outcome one
2. Outcome two
""",
        encoding="utf-8",
    )

    dec1 = evaluate_uat_gate(repo, "PRD-0005", strict=False)
    dec2 = evaluate_uat_gate(repo, "PRD-0005", strict=False)

    assert dec1.decision == dec2.decision
    assert dec1.readiness_percentage == dec2.readiness_percentage
    assert dec1.approved_outcomes == dec2.approved_outcomes
    assert dec1.total_outcomes == dec2.total_outcomes
    assert dec1.blocking_reasons == dec2.blocking_reasons
