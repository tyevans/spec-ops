"""Hypothesis generative property invariant tests for hybrid delivery velocity (ADR-0009)."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.velocity import calculate_hybrid_velocity
from spec_ops.core.models import Task
from spec_ops.core.provenance import CommitRecord


@st.composite
def task_and_commits_strategy(draw):
    """Generates synthetic tasks and arbitrary commit histories."""
    num_tasks = draw(st.integers(min_value=1, max_value=15))
    tasks = []
    task_ids = []
    for i in range(num_tasks):
        cid = f"TASK-{str(i + 1).zfill(4)}"
        task_ids.append(cid)
        status = draw(st.sampled_from(["Complete", "Complete", "Refined", "Proposed"]))
        tasks.append(
            Task(
                id=cid,
                title=f"Task {i + 1}",
                status=status,
                claimed_at="2026-09-30T10:00:00Z",
                completed_at="2026-09-30T10:30:00Z" if status == "Complete" else "",
            )
        )

    # Generate random commits linking to task IDs
    num_commits = draw(st.integers(min_value=0, max_value=30))
    commits = []
    for c_idx in range(num_commits):
        c_hash = f"{c_idx:040x}"
        linked_tasks = draw(st.lists(st.sampled_from(task_ids), min_size=0, max_size=3, unique=True))
        is_auto = draw(st.booleans())
        author = "Agent Worker" if is_auto else "Human Dev"
        trailers = {"SpecOps-Worker": "worker-1"} if is_auto else {}
        commits.append(
            CommitRecord(
                full_hash=c_hash,
                short_hash=c_hash[:7],
                author=author,
                email="test@specops.test",
                date="2026-09-30",
                subject=f"commit {c_idx}",
                body=f"Commit body\n",
                trailers=trailers,
                task_ids=linked_tasks,
                is_autonomous=is_auto,
            )
        )

    return tasks, commits


@settings(max_examples=50)
@given(tc=task_and_commits_strategy())
def test_velocity_unique_completed_tasks_invariant(tc):
    """Asserts that velocity metrics match exact count of unique completed tasks without double counting."""
    tasks, commits = tc
    tmp_path = Path("/tmp")

    report = calculate_hybrid_velocity(
        repo_root=tmp_path,
        window="14d",
        include_rescues=False,
        tasks=tasks,
        commits=commits,
    )

    am = report.agent_metrics
    hm = report.human_metrics
    tot = report.hybrid_total

    # 1. Total delivered tasks MUST equal Agent delivered + Human delivered exactly
    assert tot.tasks_delivered == am.tasks_delivered + hm.tasks_delivered

    # 2. Total delivered tasks MUST NOT exceed total completed tasks in backlog
    completed_task_ids = {t.canonical_id for t in tasks if t.status.lower() == "complete"}
    assert tot.tasks_delivered <= len(completed_task_ids)
    assert tot.tasks_delivered == len(completed_task_ids)

    # 3. Merged commits MUST partition cleanly without double counting or loss
    assert tot.merged_commits == am.merged_commits + hm.merged_commits
    assert tot.merged_commits == len(commits)

    # 4. Cycle time invariants: cycle times must be non-negative
    assert am.avg_cycle_time_minutes >= 0.0
    assert hm.avg_cycle_time_minutes >= 0.0
    assert tot.avg_cycle_time_minutes >= 0.0

    # 5. Non-negative delivery velocities
    assert am.tasks_per_week >= 0.0
    assert hm.tasks_per_week >= 0.0
    assert tot.tasks_per_week >= 0.0
