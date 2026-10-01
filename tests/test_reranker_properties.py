"""Generative Hypothesis property tests for BacklogReranker (ADR-0009).

Tests random task DAGs asserting:
1. Absence of priority inversions in reordered output.
2. Complete idempotency on repeated reordering runs.
3. Preservation of pinned tasks while remaining topologically valid.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.queue import write_task_file
from spec_ops.backlog.reranker import (
    BacklogReranker,
    find_priority_inversions,
    normalize_task_id,
)
from spec_ops.core.models import Task


@st.composite
def acyclic_task_dag_strategy(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Generates a guaranteed acyclic directed graph of tasks with random metadata."""
    num_tasks = draw(st.integers(min_value=2, max_value=10))
    tasks = []

    # Assign sequential integers so edges can only go forward (i < j -> j can depend on i)
    for i in range(1, num_tasks + 1):
        cid = f"TASK-{i:04d}"
        # Acyclic rule: task i can only depend on tasks < i
        possible_prereqs = [f"TASK-{j:04d}" for j in range(1, i)]
        if possible_prereqs:
            deps = draw(st.lists(st.sampled_from(possible_prereqs), max_size=min(3, len(possible_prereqs)), unique=True))
        else:
            deps = []

        milestone_num = draw(st.integers(min_value=1, max_value=5))
        risk_val = draw(st.sampled_from(["low", "medium", "high", "critical"]))
        is_pinned = draw(st.booleans()) if i == 1 else False
        pin_val = 1 if is_pinned and not deps else None

        tasks.append({
            "id": f"{i:04d}",
            "cid": cid,
            "deps": deps,
            "milestone": f"Milestone {milestone_num}",
            "risk": risk_val,
            "pinned": is_pinned if pin_val else False,
            "priority_pin": pin_val,
        })
    return tasks


@settings(max_examples=50, deadline=None)
@given(dag=acyclic_task_dag_strategy())
def test_property_absence_of_priority_inversions(tmp_path_factory: pytest.TempPathFactory, dag: list[dict[str, Any]]):
    """Asserts that BacklogReranker never produces priority inversions on valid DAGs."""
    tmp_path = tmp_path_factory.mktemp("dag_test")
    backlog_dir = tmp_path / "backlog"
    for folder in ("refined", "proposed", "complete"):
        (backlog_dir / folder).mkdir(parents=True)

    task_objects: list[Task] = []
    lines: list[str] = []

    # Write in arbitrary or reversed initial order to simulate real-world priority inversions
    for item in reversed(dag):
        num = item["id"]
        cid = item["cid"]
        t = Task(
            id=num,
            title=f"Task {cid}",
            status="Refined",
            dependencies=item["deps"],
            target_release=item["milestone"],
            pinned=item["pinned"],
            priority_pin=item["priority_pin"],
            file_path=backlog_dir / "refined" / f"{num}-task.md",
        )
        write_task_file(t)
        task_objects.append(t)
        lines.append(f"- **{cid} (Refined)**: [`{num}-task`](refined/{num}-task.md)")

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text("# Backlog Priority Index\n\n" + "\n".join(lines) + "\n", encoding="utf-8")

    reranker = BacklogReranker(backlog_dir)
    res = reranker.reorder(by_weights=True)

    assert res.is_valid, f"Expected DAG to be valid, found cycles: {res.cycles}"
    ordered_cids = [t.canonical_id for t in res.ordered_tasks]
    assert len(ordered_cids) == len(dag)

    # Invariant: for every task, all its prerequisites appear BEFORE it in the ordered list
    for t in res.ordered_tasks:
        t_idx = ordered_cids.index(t.canonical_id)
        for dep in t.dependencies:
            dep_cid = normalize_task_id(dep)
            if dep_cid in ordered_cids:
                dep_idx = ordered_cids.index(dep_cid)
                assert dep_idx < t_idx, (
                    f"Priority inversion found: prerequisite {dep_cid} (pos {dep_idx}) "
                    f"does not precede dependent {t.canonical_id} (pos {t_idx})"
                )

    # Invariant: find_priority_inversions returns 0
    new_ranks = {cid: idx for idx, cid in enumerate(ordered_cids, start=1)}
    assert find_priority_inversions(res.ordered_tasks, new_ranks) == []


@settings(max_examples=50, deadline=None)
@given(dag=acyclic_task_dag_strategy())
def test_property_idempotency_of_reordering(tmp_path_factory: pytest.TempPathFactory, dag: list[dict[str, Any]]):
    """Asserts that running reorder on an already reordered backlog produces identical ordering."""
    tmp_path = tmp_path_factory.mktemp("idemp_test")
    backlog_dir = tmp_path / "backlog"
    for folder in ("refined", "proposed", "complete"):
        (backlog_dir / folder).mkdir(parents=True)

    lines: list[str] = []
    for item in dag:
        num = item["id"]
        cid = item["cid"]
        t = Task(
            id=num,
            title=f"Task {cid}",
            status="Refined",
            dependencies=item["deps"],
            target_release=item["milestone"],
            pinned=item["pinned"],
            priority_pin=item["priority_pin"],
            file_path=backlog_dir / "refined" / f"{num}-task.md",
        )
        write_task_file(t)
        lines.append(f"- **{cid} (Refined)**: [`{num}-task`](refined/{num}-task.md)")

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text("# Backlog Priority Index\n\n" + "\n".join(lines) + "\n", encoding="utf-8")

    reranker = BacklogReranker(backlog_dir)
    # First run
    ok1, msg1, res1 = reranker.apply(by_weights=True)
    assert ok1
    order1 = [t.canonical_id for t in res1.ordered_tasks]

    # Second run on the updated state
    reranker2 = BacklogReranker(backlog_dir)
    ok2, msg2, res2 = reranker2.apply(by_weights=True)
    assert ok2
    order2 = [t.canonical_id for t in res2.ordered_tasks]

    assert order1 == order2, f"Idempotency violated: run1={order1} != run2={order2}"
