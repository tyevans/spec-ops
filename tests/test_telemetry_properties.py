"""Generative property-based tests for worker fleet telemetry aggregation (ADR-0009, TASK-0070)."""

from __future__ import annotations

from typing import Any
from hypothesis import given, strategies as st

from spec_ops.visualizer.telemetry_script import (
    aggregate_fleet_telemetry,
    classify_worker_status,
)

status_strategy = st.sampled_from([
    "Running", "Executing", "Self-Healing", "Stalled",
    "Stalled: Human Takeover Required", "Failed", "Deadlocked",
    "Complete", "Completed", "Done", "Shipped",
    "Rescued", "rescue_in_progress", "human_takeover", "taken_over",
    "Unknown", "",
])

attempt_strategy = st.sampled_from(["0/3", "1/3", "2/3", "3/3", "4/3", ""])
retries_strategy = st.sampled_from(["0/3", "1/3", "2/3", "3/3", "2/3 Self-Healing", ""])

worker_dict_strategy = st.fixed_dictionaries(
    {
        "task_id": st.from_regex(r"^TASK-[0-9]{4}$"),
        "status": status_strategy,
        "stalled": st.booleans(),
        "rescued": st.booleans(),
        "completed": st.booleans(),
        "attempt": attempt_strategy,
        "retries": retries_strategy,
        "memory_mb": st.floats(min_value=0.0, max_value=8192.0, allow_nan=False, allow_infinity=False),
        "cpu_percent": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        "elapsed_seconds": st.floats(min_value=0.0, max_value=86400.0, allow_nan=False, allow_infinity=False),
    }
)


@given(st.lists(worker_dict_strategy, max_size=50))
def test_fleet_telemetry_partition_invariant(workers: list[dict[str, Any]]) -> None:
    """Invariant (ADR-0009): Fleet telemetry metrics (active, stalled, rescued, completed counts)
    strictly partition total worker allocations without undercounts or overflows.
    """
    metrics = aggregate_fleet_telemetry(workers)

    # 1. Total matches input size (no undercount or overflow)
    assert metrics["total"] == len(workers)

    # 2. Strict partition equation
    partition_sum = (
        metrics["active"]
        + metrics["stalled"]
        + metrics["rescued"]
        + metrics["completed"]
    )
    assert partition_sum == metrics["total"]
    assert metrics["partition_valid"] is True

    # 3. Individual allocation partition verification
    categories = [classify_worker_status(w) for w in workers]
    assert categories.count("active") == metrics["active"]
    assert categories.count("stalled") == metrics["stalled"]
    assert categories.count("rescued") == metrics["rescued"]
    assert categories.count("completed") == metrics["completed"]

    # 4. Stalled tasks tracking
    assert len(metrics["stalled_tasks"]) == metrics["stalled"]
    for tid in metrics["stalled_tasks"]:
        assert tid.startswith("TASK-")

    # 5. Non-negative aggregates
    assert metrics["total_memory_mb"] >= 0.0
    assert 0.0 <= metrics["avg_cpu_percent"] <= 100.0 or metrics["total"] == 0
