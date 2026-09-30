"""Hypothesis property tests for dynamic unblocking and dependency DAG satisfaction."""

from pathlib import Path
from hypothesis import given, settings, strategies as st

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.core.models import Task


@st.composite
def dependency_dag_tasks(draw):
    """Generates a valid topological DAG of tasks with priority ranks."""
    n = draw(st.integers(min_value=2, max_value=8))
    tasks = []
    for i in range(1, n + 1):
        task_id = f"TASK-{str(i).zfill(4)}"
        # Can only depend on tasks created before it (acyclic guarantee)
        possible_deps = [f"TASK-{str(j).zfill(4)}" for j in range(1, i)]
        deps = draw(st.lists(st.sampled_from(possible_deps), unique=True)) if possible_deps else []
        priority = draw(st.integers(min_value=1, max_value=100))
        tasks.append((task_id, deps, priority))
    return tasks


@settings(deadline=None)
@given(tasks=dependency_dag_tasks(), completion_count=st.integers(min_value=0, max_value=8))
def test_hypothesis_dynamic_unblocking_invariants(tmp_path_factory, tasks, completion_count):
    """Property Invariant: Dynamic unblocking identifies strictly ready tasks in priority order."""
    base_dir = tmp_path_factory.mktemp("hypothesis_dag")
    backlog_dir = base_dir / "backlog"
    refined_dir = backlog_dir / "refined"
    complete_dir = backlog_dir / "complete"
    refined_dir.mkdir(parents=True)
    complete_dir.mkdir(parents=True)

    # Write all tasks as Refined
    for tid, deps, prio in tasks:
        raw_id = tid.replace("TASK-", "")
        t = Task(
            id=raw_id,
            title=f"Task {tid}",
            status="Refined",
            dependencies=deps,
            file_path=refined_dir / f"{raw_id}-task.md",
            priority_rank=prio,
        )
        write_task_file(t)

    queue = BacklogQueue(backlog_dir)

    # Invariant check: query ready unblocked tasks
    ready = queue.get_ready_unblocked_tasks()
    completed_ids = queue.get_completed_task_ids()

    # Property 1: All ready tasks must have all their dependencies satisfied in completed_ids
    for r in ready:
        for dep in r.dependencies:
            assert dep in completed_ids, f"Task {r.canonical_id} is unblocked but dependency {dep} is not complete"

    # Property 2: Ready tasks must be strictly sorted by priority_rank
    priorities = [r.priority_rank for r in ready]
    assert priorities == sorted(priorities), f"Ready tasks are not ordered by priority_rank: {priorities}"

    # Now complete up to completion_count ready tasks sequentially
    steps = min(completion_count, len(ready))
    for i in range(steps):
        current_ready = queue.get_ready_unblocked_tasks()
        if not current_ready:
            break
        to_complete = current_ready[0]
        queue.complete_task(to_complete)

        # After each completion, re-check invariants
        new_ready = queue.get_ready_unblocked_tasks()
        new_completed = queue.get_completed_task_ids()

        assert to_complete.canonical_id in new_completed
        assert to_complete.canonical_id not in [nr.canonical_id for nr in new_ready]

        for nr in new_ready:
            for dep in nr.dependencies:
                assert dep in new_completed, f"Task {nr.canonical_id} released before dependency {dep} completed"
            assert nr.priority_rank >= new_ready[0].priority_rank
