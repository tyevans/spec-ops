"""Property-based generative tests for backlog slicing and inference curation invariants."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.inference_curator import InferenceCurator
from spec_ops.backlog.reconciler import ArchitecturalReconciler
from spec_ops.backlog.slicer import AutonomousTaskSlicer
from spec_ops.config.models import ArchitectureSettings, SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project


# Strategy for generating synthetic checkable outcomes
outcomes_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        min_size=10,
        max_size=60,
    ).map(lambda s: f"Verify {s.strip()}"),
    min_size=1,
    max_size=12,
    unique=True,
)


@given(
    outcomes=outcomes_strategy,
    base_id=st.integers(min_value=1, max_value=9000),
    include_spike=st.booleans(),
)
@settings(max_examples=40)
def test_invariant_1_decomposition_completeness(
    outcomes: list[str], base_id: int, include_spike: bool
):
    """Invariant 1: Slicing an oversized task preserves 100% of checkable outcomes without dropped scope."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        init_project(tmp_path, name="CompletenessTest")
        config = SpecOpsConfig(root_dir=tmp_path)
        slicer = AutonomousTaskSlicer(config)

        body = (
            "## Summary\nOversized task with multiple outcomes.\n\n"
            "## Checkable Outcomes\n"
            + "\n".join(f"- {o}" for o in outcomes)
            + "\n\nestimated_lines: 600\n"
        )
        task = Task(
            id=f"{base_id:04d}",
            title=f"Monolithic Task {base_id}",
            status="Proposed",
            target_bc="backlog, worker",
            body=body,
            file_path=tmp_path / f"{base_id:04d}-monolith.md",
        )

        slice_res = slicer.slice_task(
            task, include_spike=include_spike, next_task_num=base_id
        )

        # Collect all outcomes preserved across child slices
        preserved_outcomes: set[str] = set()
        for child in slice_res.child_slices:
            for outcome in outcomes:
                if outcome in child.body:
                    preserved_outcomes.add(outcome)

        # Invariant: 100% of checkable outcomes are accounted for across child slices
        assert set(outcomes) == preserved_outcomes


@given(
    outcomes=outcomes_strategy,
    base_id=st.integers(min_value=1, max_value=9000),
    include_spike=st.booleans(),
)
@settings(max_examples=40)
def test_invariant_2_sequential_dependency_and_ids(
    outcomes: list[str], base_id: int, include_spike: bool
):
    """Invariant 2: Synthesized child slice IDs are strictly unique, sequential, and non-colliding; prerequisite spike strictly precedes slices."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        init_project(tmp_path, name="SeqIdTest")
        config = SpecOpsConfig(root_dir=tmp_path)
        slicer = AutonomousTaskSlicer(config)

        body = (
            "## Summary\nOversized task.\n\n## Checkable Outcomes\n"
            + "\n".join(f"- {o}" for o in outcomes)
            + "\n\nestimated_lines: 550\n"
        )
        task = Task(
            id=f"{base_id:04d}",
            title=f"Sequential Monolith {base_id}",
            status="Proposed",
            target_bc="core",
            body=body,
            file_path=tmp_path / f"{base_id:04d}-monolith.md",
        )

        slice_res = slicer.slice_task(
            task, include_spike=include_spike, next_task_num=base_id
        )

        all_children = (
            ([slice_res.spike_task] if slice_res.spike_task else [])
            + slice_res.child_slices
        )
        child_ids = [c.canonical_id for c in all_children]

        # 1. Strictly unique IDs
        assert len(child_ids) == len(set(child_ids))

        # 2. Strictly monotonically increasing sequential numbers
        numeric_ids = [int(c.id) for c in all_children]
        for i in range(len(numeric_ids) - 1):
            assert numeric_ids[i + 1] == numeric_ids[i] + 1
            assert numeric_ids[i] > base_id

        # 3. If spike present, it is first and slices depend sequentially
        if slice_res.spike_task:
            spike_id = slice_res.spike_task.canonical_id
            assert all_children[0].canonical_id == spike_id
            assert "Architectural Spike:" in all_children[0].title
            if slice_res.child_slices:
                # First slice depends on spike
                assert spike_id in slice_res.child_slices[0].dependencies

        # 4. Sequential dependencies between slices
        for i in range(len(slice_res.child_slices) - 1):
            curr_id = slice_res.child_slices[i].canonical_id
            next_deps = slice_res.child_slices[i + 1].dependencies
            assert curr_id in next_deps


@given(
    outcomes=outcomes_strategy,
    base_id=st.integers(min_value=1, max_value=9000),
    include_spike=st.booleans(),
)
@settings(max_examples=40)
def test_invariant_3_size_invariant(
    outcomes: list[str], base_id: int, include_spike: bool
):
    """Invariant 3: Decomposed child slices restrict estimated scope strictly beneath modular boundaries (<400 lines)."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        init_project(tmp_path, name="SizeTest")
        config = SpecOpsConfig(root_dir=tmp_path)
        slicer = AutonomousTaskSlicer(config)

        body = (
            "## Summary\nOversized task exceeding 500 lines.\n\n## Checkable Outcomes\n"
            + "\n".join(f"- {o}" for o in outcomes)
            + "\n\nestimated_lines: 700\n"
        )
        task = Task(
            id=f"{base_id:04d}",
            title=f"Size Invariant Task {base_id}",
            status="Proposed",
            target_bc="core",
            body=body,
            file_path=tmp_path / f"{base_id:04d}-task.md",
        )

        slice_res = slicer.slice_task(
            task, include_spike=include_spike, next_task_num=base_id
        )

        all_children = (
            ([slice_res.spike_task] if slice_res.spike_task else [])
            + slice_res.child_slices
        )

        for child in all_children:
            est_lines = slicer.estimate_task_lines(child)
            # Size invariant: strictly beneath modular boundaries (<400 lines)
            assert est_lines < 400
            # Also not flagged as needing slicing
            assert not slicer.needs_slicing(child)
