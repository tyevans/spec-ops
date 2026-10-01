"""Hypothesis generative property tests for stalled claim reclamation.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0077.
Target Bounded Context: backlog. Mathematical invariant assertions across randomized inputs.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.queue import write_task_file
from spec_ops.backlog.reclaim import StalledClaimReclaimer
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project


@settings(max_examples=50)
@given(
    timeout_hours=st.floats(min_value=0.5, max_value=48.0),
    elapsed_ratio=st.floats(min_value=0.0, max_value=0.999),
)
def test_property_active_leases_never_reclaimed(tmp_path_factory, timeout_hours: float, elapsed_ratio: float):
    """Invariant: An active lease with activity age strictly below timeout is NEVER reclaimed."""
    tmp_path = tmp_path_factory.mktemp("active_prop")
    repo = tmp_path / "repo"
    init_project(repo, name="ActiveLeaseProp")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime(2026, 9, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
    elapsed_hours = timeout_hours * elapsed_ratio
    active_ts = (now - datetime.timedelta(seconds=elapsed_hours * 3600.0)).isoformat()

    task_file = refined_dir / "0001-task.md"
    task = Task(
        id="0001",
        title="Active Hypothesis Task",
        status="In-Progress",
        claimed_by="worker-hyp",
        claimed_at=active_ts,
        file_path=task_file,
    )
    write_task_file(task)

    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo, now=now)
    is_stalled, info = reclaimer.evaluate_task_claim(task, timeout_hours=timeout_hours)

    assert not is_stalled, f"Active claim with age {elapsed_hours:.3f}h incorrectly marked stalled under timeout {timeout_hours:.3f}h"
    assert info.status == "Active"


@settings(max_examples=50)
@given(
    timeout_hours=st.floats(min_value=0.5, max_value=48.0),
    excess_hours=st.floats(min_value=0.001, max_value=50.0),
)
def test_property_expired_leases_always_reclaimed(tmp_path_factory, timeout_hours: float, excess_hours: float):
    """Invariant: A lease with activity age exceeding timeout is ALWAYS detected as stalled."""
    tmp_path = tmp_path_factory.mktemp("expired_prop")
    repo = tmp_path / "repo"
    init_project(repo, name="ExpiredLeaseProp")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime(2026, 9, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
    elapsed_hours = timeout_hours + excess_hours
    expired_ts = (now - datetime.timedelta(seconds=elapsed_hours * 3600.0)).isoformat()

    task_file = refined_dir / "0002-task.md"
    task = Task(
        id="0002",
        title="Expired Hypothesis Task",
        status="In-Progress",
        claimed_by="worker-hyp",
        claimed_at=expired_ts,
        file_path=task_file,
    )
    write_task_file(task)

    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo, now=now)
    is_stalled, info = reclaimer.evaluate_task_claim(task, timeout_hours=timeout_hours)

    assert is_stalled, f"Expired claim with age {elapsed_hours:.3f}h not detected under timeout {timeout_hours:.3f}h"
    assert info.status == "Stalled"


@settings(max_examples=30)
@given(
    t1=st.floats(min_value=1.0, max_value=20.0),
    delta=st.floats(min_value=0.5, max_value=20.0),
    claim_ages=st.lists(st.floats(min_value=0.1, max_value=45.0), min_size=2, max_size=8),
)
def test_property_reclamation_monotonic_over_threshold(tmp_path_factory, t1: float, delta: float, claim_ages: list[float]):
    """Invariant: Increasing timeout threshold can only decrease or preserve the number of reclaimed tasks (monotonicity)."""
    t2 = t1 + delta  # t1 < t2
    tmp_path = tmp_path_factory.mktemp("monotonic_prop")
    repo = tmp_path / "repo"
    init_project(repo, name="MonotonicProp")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime(2026, 9, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
    priority_lines = ["# Backlog Priority Index\n"]

    for idx, age in enumerate(claim_ages, start=1):
        cid = f"{idx:04d}"
        t_file = refined_dir / f"{cid}-task.md"
        t_ts = (now - datetime.timedelta(seconds=age * 3600.0)).isoformat()
        t = Task(
            id=cid,
            title=f"Task {cid}",
            status="In-Progress",
            claimed_by=f"worker-{idx}",
            claimed_at=t_ts,
            file_path=t_file,
        )
        write_task_file(t)
        priority_lines.append(f"- **TASK-{cid} (In-Progress)**: [`{cid}-task`](refined/{cid}-task.md)")

    pfile = backlog_dir / "PRIORITY.md"
    pfile.write_text("\n".join(priority_lines) + "\n", encoding="utf-8")

    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo, now=now)
    res_t1 = reclaimer.reclaim(timeout_hours=t1, dry_run=True)
    res_t2 = reclaimer.reclaim(timeout_hours=t2, dry_run=True)

    # Monotonicity check: T2 > T1 => reclaimed(T2) subset of reclaimed(T1)
    set_t1 = set(res_t1.reclaimed_ids)
    set_t2 = set(res_t2.reclaimed_ids)
    assert set_t2.issubset(set_t1), f"Tasks reclaimed under larger timeout {t2} ({set_t2}) is not subset of smaller timeout {t1} ({set_t1})"
    assert res_t2.reclaimed_count <= res_t1.reclaimed_count


@settings(max_examples=30)
@given(
    timeout_hours=st.floats(min_value=1.0, max_value=24.0),
    claim_age_1=st.floats(min_value=0.5, max_value=10.0),
    claim_age_2=st.floats(min_value=15.0, max_value=30.0),
)
def test_property_reclamation_idempotent(tmp_path_factory, timeout_hours: float, claim_age_1: float, claim_age_2: float):
    """Invariant: Reclaiming twice consecutively at the same time point reclaims 0 additional tasks."""
    tmp_path = tmp_path_factory.mktemp("idempotent_prop")
    repo = tmp_path / "repo"
    init_project(repo, name="IdempotentProp")
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime(2026, 9, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
    t1_file = refined_dir / "0001-task.md"
    t1 = Task(
        id="0001",
        title="Task 1",
        status="In-Progress",
        claimed_by="worker-1",
        claimed_at=(now - datetime.timedelta(seconds=claim_age_1 * 3600.0)).isoformat(),
        file_path=t1_file,
    )
    write_task_file(t1)

    t2_file = refined_dir / "0002-task.md"
    t2 = Task(
        id="0002",
        title="Task 2",
        status="In-Progress",
        claimed_by="worker-2",
        claimed_at=(now - datetime.timedelta(seconds=claim_age_2 * 3600.0)).isoformat(),
        file_path=t2_file,
    )
    write_task_file(t2)

    pfile = backlog_dir / "PRIORITY.md"
    pfile.write_text(
        "# Backlog Priority Index\n\n"
        "- **TASK-0001 (In-Progress)**: [`0001-task`](refined/0001-task.md)\n"
        "- **TASK-0002 (In-Progress)**: [`0002-task`](refined/0002-task.md)\n",
        encoding="utf-8",
    )

    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo, now=now)
    first_res = reclaimer.reclaim(timeout_hours=timeout_hours, dry_run=False)
    second_res = reclaimer.reclaim(timeout_hours=timeout_hours, dry_run=False)

    assert second_res.reclaimed_count == 0, f"Expected 0 reclaims on second pass, got {second_res.reclaimed_count}"
    assert len(second_res.reclaimed_ids) == 0
