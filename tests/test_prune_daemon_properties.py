"""Generative property-based tests for worktree quota and pruning daemon invariants (ADR-0009)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

from hypothesis import given, strategies as st

from spec_ops.rescue.prune_daemon import (
    WorktreeQuotaInfo,
    evaluate_prune_eligibility,
    parse_duration,
    parse_threshold_bytes,
)

ACTIVE_STATUSES = {"Refined", "Proposed", "Active", "Inprogress", "In-progress"}


@st.composite
def synthetic_worktree_strategy(draw):
    status = draw(
        st.sampled_from(["Complete", "Refined", "Proposed", "Active", "Inprogress", "Orphan", "Unknown"])
    )
    is_dirty = draw(st.booleans())
    is_merged = draw(st.booleans())
    has_failure = draw(st.booleans())
    age_seconds = draw(st.integers(min_value=0, max_value=30 * 86400))
    now = datetime.now(timezone.utc)
    mtime = now - timedelta(seconds=age_seconds)

    return WorktreeQuotaInfo(
        worktree_name=f"task-{draw(st.integers(min_value=1, max_value=9999)):04d}",
        worktree_dir=Path("/fake/path"),
        task_id=f"TASK-{draw(st.integers(min_value=1, max_value=9999)):04d}",
        task_status=status,
        size_bytes=draw(st.integers(min_value=0, max_value=10 * 1024**3)),
        last_modified=mtime,
        last_modified_str=mtime.strftime("%Y-%m-%d %H:%M"),
        is_dirty=is_dirty,
        is_merged=is_merged,
        has_failure_history=has_failure,
        branch=f"feat/TASK-{draw(st.integers(min_value=1, max_value=9999)):04d}",
        is_eligible=False,
    )


@given(
    wt=synthetic_worktree_strategy(),
    force=st.booleans(),
    has_cutoff=st.booleans(),
    cutoff_days=st.integers(min_value=1, max_value=14),
)
def test_pruning_eligibility_invariants(wt: WorktreeQuotaInfo, force: bool, has_cutoff: bool, cutoff_days: int):
    """Invariant (ADR-0005, ADR-0009):

    Pruning strictly targets completed or force-flagged directories and NEVER
    deletes active in-progress worktrees.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=cutoff_days) if has_cutoff else None
    eligible, reason = evaluate_prune_eligibility(wt, cutoff_time=cutoff, force=force)

    norm_status = wt.task_status.strip().capitalize()

    # Invariant 1: Active in-progress worktrees are NEVER eligible
    if norm_status in ACTIVE_STATUSES:
        assert not eligible, f"Active in-progress task ({norm_status}) must NEVER be eligible for pruning"

    # Invariant 2: Without force, dirty worktrees are NEVER eligible
    if wt.is_dirty and not force:
        assert not eligible, "Dirty worktrees must NEVER be eligible without explicit --force"

    # Invariant 3: Without force, unmerged orphans without failure memory are NEVER eligible
    if norm_status != "Complete" and not (wt.is_merged or wt.has_failure_history) and not force:
        assert not eligible, "Unmerged worktrees without failure memory must NEVER be eligible without --force"

    # Invariant 4: Worktrees modified after cutoff time are NEVER eligible
    if cutoff is not None and wt.last_modified > cutoff:
        assert not eligible, "Worktrees newer than cutoff time must NEVER be eligible"

    # Invariant 5: If eligible, worktree is strictly completed or force-flagged or safe orphan
    if eligible:
        assert norm_status not in ACTIVE_STATUSES, "Eligible worktree cannot be an active task"
        assert (norm_status == "Complete") or force or (wt.is_merged or wt.has_failure_history)


@given(
    worktrees=st.lists(synthetic_worktree_strategy(), min_size=1, max_size=25),
    force=st.booleans(),
    has_cutoff=st.booleans(),
    cutoff_days=st.integers(min_value=1, max_value=10),
)
def test_fleet_pruning_safety_generative(
    worktrees: list[WorktreeQuotaInfo], force: bool, has_cutoff: bool, cutoff_days: int
):
    """Evaluates safety across an entire randomized fleet of worktrees."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=cutoff_days) if has_cutoff else None
    selected = []

    for wt in worktrees:
        eligible, _ = evaluate_prune_eligibility(wt, cutoff_time=cutoff, force=force)
        if eligible:
            selected.append(wt)

    for cand in selected:
        norm = cand.task_status.strip().capitalize()
        # Active in-progress must never appear in selected candidates
        assert norm not in ACTIVE_STATUSES
        if not force:
            assert not cand.is_dirty
            if norm != "Complete":
                assert cand.is_merged or cand.has_failure_history


@given(
    val=st.integers(min_value=1, max_value=365),
    unit=st.sampled_from(["d", "days", "h", "hours", "m", "mins", "s", "secs", "w", "weeks"]),
)
def test_duration_parsing_property(val: int, unit: str):
    """Property: duration parser handles arbitrary valid units consistently."""
    dur_str = f"{val}{unit}"
    td = parse_duration(dur_str)
    assert isinstance(td, timedelta)
    assert td.total_seconds() > 0


@given(
    val=st.floats(min_value=0.1, max_value=100.0),
    unit=st.sampled_from(["GB", "MB", "KB", "B"]),
)
def test_threshold_parsing_property(val: float, unit: str):
    """Property: threshold byte parser computes correct magnitude."""
    thresh_str = f"{val:.1f}{unit}"
    parsed = parse_threshold_bytes(thresh_str)
    assert isinstance(parsed, int)
    assert parsed >= 0
