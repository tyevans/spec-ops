"""Hypothesis generative property tests for PRD shipping validation and release gates."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.shipping import (
    reconcile_shipping_uat_status,
    validate_shipping_tasks,
    validate_shipping_tests,
)


class DummyTask:
    def __init__(self, task_id: str, status: str):
        self.canonical_id = task_id
        self.status = status


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["TASK-0001", "TASK-0002", "TASK-0003", "TASK-0004", "TASK-0005"]),
            st.sampled_from(["Complete", "Refined", "Proposed", "InProgress", "Draft"]),
        ),
        min_size=1,
        max_size=20,
        unique_by=lambda x: x[0],
    ),
    st.text(min_size=1, max_size=10, alphabet="0123456789"),
)
@settings(max_examples=50)
def test_shipping_tasks_invariant_strict_completion_gate(task_specs: list[tuple[str, str]], prd_num: str):
    """Property: validate_shipping_tasks strictly aborts if any task is not Complete."""
    prd_id = f"PRD-{prd_num.zfill(4)}"
    tasks = [DummyTask(tid, status) for tid, status in task_specs]

    all_complete = all(t.status == "Complete" for t in tasks)
    is_valid, err_msg = validate_shipping_tasks(tasks, prd_id)

    if all_complete:
        assert is_valid is True
        assert err_msg == ""
    else:
        assert is_valid is False
        assert f"Cannot ship {prd_id}: Incomplete tasks remaining" in err_msg
        # Incomplete tasks must be named in the error message
        for t in tasks:
            if t.status != "Complete":
                assert t.canonical_id in err_msg
                assert t.status in err_msg


@given(
    st.sampled_from(["Passed (CI)", "Failed (CI)", "Pending (CI)", "Error"]),
    st.integers(min_value=0, max_value=50),
    st.integers(min_value=0, max_value=20),
    st.text(min_size=1, max_size=10, alphabet="0123456789"),
)
@settings(max_examples=50)
def test_shipping_tests_invariant_frontdoor_verification_gate(
    status: str, total_scenarios: int, failed_scenarios: int, prd_num: str
):
    """Property: validate_shipping_tests strictly aborts if status != Passed (CI) or failed > 0."""
    prd_id = f"PRD-{prd_num.zfill(4)}"
    test_summary = {
        "status": status,
        "total_scenarios": total_scenarios,
        "failed_scenarios": failed_scenarios,
    }
    stories = [MagicMock()]

    is_valid, err_msg = validate_shipping_tests(stories, test_summary, prd_id)

    if status == "Passed (CI)" and failed_scenarios == 0:
        assert is_valid is True
        assert err_msg == ""
    else:
        assert is_valid is False
        assert f"Cannot ship {prd_id}: Linked BDD user stories or tests failed frontdoor verification" in err_msg


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["1", "2", "3", "4", "5", "6"]),
            st.sampled_from(["Approved", "Pending PM", "Rejected", "None"]),
        ),
        min_size=1,
        max_size=15,
        unique_by=lambda x: x[0],
    ),
    st.text(min_size=1, max_size=10, alphabet="0123456789"),
)
@settings(max_examples=50)
def test_shipping_uat_status_reconciliation(outcome_specs: list[tuple[str, str]], prd_num: str):
    """Property: reconcile_shipping_uat_status is approved iff all outcome IDs have Approved status."""
    prd_id = f"PRD-{prd_num.zfill(4)}"
    outcome_ids = [spec[0] for spec in outcome_specs]
    signoffs: dict[str, Any] = {}

    for oid, status in outcome_specs:
        if status != "None":
            signoffs[f"{prd_id}:{oid}"] = {"status": status}

    signoffs_data = {"signoffs": signoffs}
    all_approved, summary = reconcile_shipping_uat_status(prd_id, outcome_ids, signoffs_data)

    expected_approved_count = sum(
        1 for oid, status in outcome_specs if status == "Approved"
    )
    assert summary["total_outcomes"] == len(outcome_ids)
    assert summary["approved_outcomes"] == expected_approved_count

    if expected_approved_count == len(outcome_ids):
        assert all_approved is True
        assert summary["status"] == "Approved"
    else:
        assert all_approved is False
        assert summary["status"] == "Pending PM"
