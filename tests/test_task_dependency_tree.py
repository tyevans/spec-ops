"""Unit and property-based tests for TaskDependencyTreeEngine."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from rich.tree import Tree

from spec_ops.backlog.tree import TaskDependencyTreeEngine, normalize_task_id
from spec_ops.core.models import BlockerInfo, Task


def make_dummy_task(
    num: int,
    status: str = "Proposed",
    dependencies: list[str] | None = None,
    blocker_question: str = "",
    spike_id: str = "",
) -> Task:
    blocker = (
        BlockerInfo(type="unknown", question=blocker_question, spike_id=spike_id)
        if blocker_question
        else None
    )
    return Task(
        id=f"{num:04d}",
        title=f"Task {num}",
        status="Blocked" if blocker_question else status,
        dependencies=dependencies or [],
        file_path=Path(f"docs/project/backlog/{status.lower()}/{num:04d}-task.md"),
        priority_rank=num,
        blocker=blocker,
    )


def test_linear_dependency_chain():
    # T1 (Complete) -> T2 (Refined, unblocked) -> T3 (Proposed, blocked by T2)
    t1 = make_dummy_task(1, status="Complete")
    t2 = make_dummy_task(2, status="Refined", dependencies=["TASK-0001"])
    t3 = make_dummy_task(3, status="Proposed", dependencies=["TASK-0002"])

    engine = TaskDependencyTreeEngine([t1, t2, t3], completed_ids={"TASK-0001"})

    assert engine.states["TASK-0001"].is_complete
    assert engine.states["TASK-0002"].is_ready
    assert not engine.states["TASK-0002"].is_blocked
    assert engine.states["TASK-0003"].is_blocked

    # Waves: Wave 0 should be T2; Wave 1 should be T3
    assert engine.waves == [["TASK-0002"], ["TASK-0003"]]


def test_diamond_dependencies_and_choke_points():
    # T1 unlocks T2 and T3. Both T2 and T3 unlock T4.
    t1 = make_dummy_task(1, status="Refined")
    t2 = make_dummy_task(2, status="Proposed", dependencies=["TASK-0001"])
    t3 = make_dummy_task(3, status="Proposed", dependencies=["TASK-0001"])
    t4 = make_dummy_task(4, status="Proposed", dependencies=["TASK-0002", "TASK-0003"])

    engine = TaskDependencyTreeEngine([t1, t2, t3, t4])

    assert engine.waves == [["TASK-0001"], ["TASK-0002", "TASK-0003"], ["TASK-0004"]]

    # T1 unlocks T2, T3, T4 (impact count = 3)
    assert engine.states["TASK-0001"].downstream_impact_count == 3
    chokes = engine.get_choke_points(1)
    assert len(chokes) == 1
    assert chokes[0].canonical_id == "TASK-0001"


def test_circular_dependency_detection():
    # T1 depends on T2, T2 depends on T1
    t1 = make_dummy_task(1, status="Proposed", dependencies=["TASK-0002"])
    t2 = make_dummy_task(2, status="Proposed", dependencies=["TASK-0001"])

    engine = TaskDependencyTreeEngine([t1, t2])
    assert len(engine.cycles) > 0
    cycle_nodes = set(engine.cycles[0])
    assert "TASK-0001" in cycle_nodes
    assert "TASK-0002" in cycle_nodes

    # Building tree should handle cycle gracefully without RecursionError
    tree = engine.build_forward_tree()
    assert isinstance(tree, Tree)


def test_task_blocked_by_unknown_question():
    t1 = make_dummy_task(1, status="Refined")
    t2 = make_dummy_task(
        2,
        dependencies=["TASK-0001"],
        blocker_question="How to handle cache invalidation?",
        spike_id="SPIKE-0001",
    )

    engine = TaskDependencyTreeEngine([t1, t2])
    assert engine.states["TASK-0002"].is_blocked_by_unknown
    assert engine.states["TASK-0002"].is_blocked
    assert not engine.states["TASK-0002"].is_ready

    # Blocked by unknown must not be placed in regular unblocked wave
    assert "TASK-0002" not in [t for wave in engine.waves for t in wave]

    # Render label contains unknown question
    label_text = engine.render_node_label("TASK-0002").plain
    assert "BLOCKED: UNKNOWN" in label_text
    assert "How to handle cache invalidation?" in label_text
    assert "SPIKE-0001" in label_text


def test_prerequisite_tree_view():
    t1 = make_dummy_task(1, status="Complete")
    t2 = make_dummy_task(2, status="Refined", dependencies=["TASK-0001"])
    t3 = make_dummy_task(3, status="Proposed", dependencies=["TASK-0002"])

    engine = TaskDependencyTreeEngine([t1, t2, t3], completed_ids={"TASK-0001"})
    tree = engine.build_prerequisite_tree(focus_id="TASK-0003")
    assert isinstance(tree, Tree)


def test_to_dict_export():
    t1 = make_dummy_task(1, status="Complete")
    t2 = make_dummy_task(2, status="Refined", dependencies=["TASK-0001"])

    engine = TaskDependencyTreeEngine([t1, t2], completed_ids={"TASK-0001"})
    data = engine.to_dict()
    assert data["completed_count"] == 1
    assert "TASK-0002" in data["tasks"]
    assert data["tasks"]["TASK-0002"]["is_ready"]


@given(
    num_tasks=st.integers(min_value=2, max_value=8),
)
def test_hypothesis_dag_wave_invariants(num_tasks: int):
    # Generates a valid linear or upper-triangular DAG (task j can only depend on task i where i < j)
    tasks = []
    for i in range(1, num_tasks + 1):
        deps = [f"TASK-{j:04d}" for j in range(1, i) if (i + j) % 2 == 0]
        tasks.append(make_dummy_task(i, status="Proposed", dependencies=deps))

    engine = TaskDependencyTreeEngine(tasks)

    # Invariant: Any task in wave W can only depend on tasks in waves < W or completed
    task_to_wave = {cid: state.wave for cid, state in engine.states.items()}
    for cid, state in engine.states.items():
        if state.wave >= 0:
            for dep in state.task.dependencies:
                dep_canon = normalize_task_id(dep)
                if dep_canon in task_to_wave:
                    dep_wave = task_to_wave[dep_canon]
                    assert dep_wave < state.wave or dep_canon in engine.completed_ids
