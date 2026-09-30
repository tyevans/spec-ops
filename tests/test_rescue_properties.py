"""Generative property-based tests for rescue pruning invariants using Hypothesis (ADR-0009)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from hypothesis import given, strategies as st

from spec_ops.rescue.prune import is_prune_candidate, scan_worktree_candidates, PruneCandidate


@given(
    is_dirty=st.booleans(),
    task_status=st.one_of(
        st.none(),
        st.sampled_from(["Complete", "complete", "COMPLETE", "Refined", "refined", "Proposed", "proposed", "Active", "Inprogress", "Blocked"]),
        st.text(min_size=1, max_size=20),
    ),
)
def test_prune_candidate_invariant_property(is_dirty: bool, task_status: Optional[str]):
    """Property: rescue prune never selects a worktree containing uncommitted human modifications

    or assigned to an active uncompleted task.
    """
    eligible = is_prune_candidate(is_dirty=is_dirty, task_status=task_status)

    if is_dirty:
        assert not eligible, "Dirty worktrees must NEVER be eligible for pruning"

    if task_status is not None:
        normalized = task_status.strip().capitalize()
        if normalized in ("Refined", "Proposed", "Active", "Inprogress", "In-progress"):
            assert not eligible, f"Active uncompleted task ({task_status}) must NEVER be eligible for pruning"
        elif normalized == "Complete":
            if not is_dirty:
                assert eligible, "Clean completed tasks must be eligible for pruning"
        else:
            assert not eligible, f"Unknown non-complete task status ({task_status}) must not be eligible for pruning"
    else:
        # Orphaned worktree without task in backlog
        if not is_dirty:
            assert eligible, "Clean orphaned worktrees must be eligible for pruning"


@given(
    worktrees=st.lists(
        st.fixed_dictionaries({
            "is_dirty": st.booleans(),
            "status": st.one_of(st.none(), st.sampled_from(["Complete", "Refined", "Proposed", "Active"])),
            "size": st.integers(min_value=0, max_value=10_000_000),
        }),
        min_size=1,
        max_size=20,
    )
)
def test_generative_worktree_selection_safety(worktrees: list[dict]):
    """Invariant: Evaluates candidate filtering across arbitrary synthetic worktree fleets."""
    candidates: list[PruneCandidate] = []
    for i, wt in enumerate(worktrees):
        eligible = is_prune_candidate(is_dirty=wt["is_dirty"], task_status=wt["status"])
        cand = PruneCandidate(
            task_id=f"TASK-{i:04d}",
            worktree_dir=Path(f"/tmp/worktrees/task-{i:04d}"),
            branch=f"feat/TASK-{i:04d}",
            size_bytes=wt["size"],
            is_dirty=wt["is_dirty"],
            task_status=wt["status"],
            is_eligible=eligible,
        )
        candidates.append(cand)

    selected = [c for c in candidates if c.is_eligible]

    for s in selected:
        assert not s.is_dirty, f"Selected candidate {s.task_id} is dirty with uncommitted changes"
        assert s.task_status not in ("Refined", "Proposed", "Active", "Inprogress"), (
            f"Selected candidate {s.task_id} is assigned to active uncompleted task {s.task_status}"
        )
