"""Comprehensive unit tests for BacklogReranker and multi-criteria scoring algorithm.

Governed by ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0074.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.backlog.queue import write_task_file
from spec_ops.backlog.reranker import (
    BacklogReranker,
    PriorityInversion,
    ScoringWeights,
    calculate_priority_score,
    extract_milestone_horizon,
    extract_pin,
    extract_risk_score,
    find_priority_inversions,
    normalize_task_id,
)
from spec_ops.core.models import Task


# --- Scoring Algorithm Unit & Mutation Tests ---

def test_calculate_priority_score_baseline():
    weights = ScoringWeights(blocker_weight=10.0, milestone_weight=5.0, risk_weight=2.0)
    # 5 blockers * 10 = 50, (100 - 2) * 5 = 490, 3 risk * 2 = 6. Total = 546.0
    score = calculate_priority_score(5, 2, 3, weights)
    assert score == 546.0


def test_calculate_priority_score_default_weights():
    # default weights: blocker=10.0, milestone=5.0, risk=2.0
    score = calculate_priority_score(0, 100, 1)
    # 0 * 10 + 0 * 5 + 1 * 2 = 2.0
    assert score == 2.0


def test_calculate_priority_score_horizon_clamping():
    # milestone horizon > 100 clamps to 0
    score = calculate_priority_score(0, 150, 0)
    assert score == 0.0


def test_calculate_priority_score_blocker_weight_sensitivity():
    w = ScoringWeights(blocker_weight=20.0, milestone_weight=0.0, risk_weight=0.0)
    score = calculate_priority_score(3, 50, 2, w)
    assert score == 60.0


def test_calculate_priority_score_milestone_weight_sensitivity():
    w = ScoringWeights(blocker_weight=0.0, milestone_weight=10.0, risk_weight=0.0)
    # (100 - 5) * 10 = 950.0
    score = calculate_priority_score(0, 5, 0, w)
    assert score == 950.0


def test_calculate_priority_score_risk_weight_sensitivity():
    w = ScoringWeights(blocker_weight=0.0, milestone_weight=0.0, risk_weight=4.0)
    score = calculate_priority_score(0, 100, 3, w)
    assert score == 12.0


# --- Metadata Extraction Tests ---

def test_normalize_task_id():
    assert normalize_task_id("task-0005") == "TASK-0005"
    assert normalize_task_id("TASK-12") == "TASK-0012"
    assert normalize_task_id("0042") == "TASK-0042"
    assert normalize_task_id("7") == "TASK-0007"
    assert normalize_task_id("spike-0002") == "SPIKE-0002"
    assert normalize_task_id("CUSTOM-X") == "CUSTOM-X"


def test_extract_milestone_horizon():
    t = Task(id="0001", title="Test", status="Proposed", target_release="Milestone 3")
    assert extract_milestone_horizon(t) == 3

    t2 = Task(id="0002", title="Test", status="Proposed", target_release="")
    assert extract_milestone_horizon(t2, {"milestone": "M2"}) == 2
    assert extract_milestone_horizon(t2, {"target_milestone": 4}) == 4
    assert extract_milestone_horizon(t2, {}) == 100


def test_extract_risk_score():
    t = Task(id="0001", title="Test", status="Proposed")
    assert extract_risk_score(t, {"risk": "critical"}) == 4
    assert extract_risk_score(t, {"risk": "crit"}) == 4
    assert extract_risk_score(t, {"risk": "high"}) == 3
    assert extract_risk_score(t, {"risk": "medium"}) == 2
    assert extract_risk_score(t, {"risk": "med"}) == 2
    assert extract_risk_score(t, {"risk": "low"}) == 1
    assert extract_risk_score(t, {"impact": 5}) == 5
    assert extract_risk_score(t, {}) == 1

    t_spike = Task(id="0002", title="Spike", status="Proposed", slice_type="spike")
    assert extract_risk_score(t_spike, {}) == 2


def test_extract_pin():
    t = Task(id="0001", title="Test", status="Refined", priority_rank=4)
    assert extract_pin(t, {"priority_pin": 1}) == (True, 1)
    assert extract_pin(t, {"pinned": True}) == (True, 4)
    assert extract_pin(t, {"pinned": 2}) == (True, 2)
    assert extract_pin(t, {}) == (False, None)

    t_pinned = Task(id="0002", title="Test", status="Refined", priority_pin=3, pinned=True)
    assert extract_pin(t_pinned) == (True, 3)


# --- Priority Inversions Tests ---

def test_find_priority_inversions():
    t1 = Task(id="0001", title="T1", status="Refined", dependencies=["TASK-0002"])
    t2 = Task(id="0002", title="T2", status="Refined", dependencies=[])
    ranks = {"TASK-0001": 1, "TASK-0002": 2}
    inversions = find_priority_inversions([t1, t2], ranks)
    assert len(inversions) == 1
    inv = inversions[0]
    assert inv.dependent_id == "TASK-0001"
    assert inv.prerequisite_id == "TASK-0002"
    assert inv.dependent_rank == 1
    assert inv.prerequisite_rank == 2
    assert "Priority inversion" in str(inv)

    # Valid ordering: no inversions
    valid_ranks = {"TASK-0001": 2, "TASK-0002": 1}
    assert find_priority_inversions([t1, t2], valid_ranks) == []


# --- BacklogReranker Integration Tests ---

def test_reranker_empty_backlog(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir(parents=True)
    reranker = BacklogReranker(backlog_dir)
    res = reranker.reorder()
    assert res.is_valid
    assert res.ordered_tasks == []
    assert not res.modified


def test_reranker_cycle_detection(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    for folder in ("refined", "proposed", "complete"):
        (backlog_dir / folder).mkdir(parents=True)

    t1 = Task(id="0001", title="T1", status="Refined", dependencies=["TASK-0002"], file_path=backlog_dir / "refined" / "0001-t1.md")
    t2 = Task(id="0002", title="T2", status="Refined", dependencies=["TASK-0001"], file_path=backlog_dir / "refined" / "0002-t2.md")
    write_task_file(t1)
    write_task_file(t2)

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text("- **TASK-0001 (Refined)**: [`0001-t1`](refined/0001-t1.md)\n- **TASK-0002 (Refined)**: [`0002-t2`](refined/0002-t2.md)\n")

    reranker = BacklogReranker(backlog_dir)
    ok, msg, res = reranker.apply()
    assert not ok
    assert not res.is_valid
    assert len(res.cycles) > 0
    assert "circular dependency" in msg.lower()


def test_reranker_resolves_multi_level_inversion(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    for folder in ("refined", "proposed", "complete"):
        (backlog_dir / folder).mkdir(parents=True)

    # A -> B -> C (A depends on B, B depends on C)
    # Initially: A at pos 1, B at pos 2, C at pos 3 (2 inversions)
    tA = Task(id="0001", title="TA", status="Refined", dependencies=["TASK-0002"], file_path=backlog_dir / "refined" / "0001-ta.md")
    tB = Task(id="0002", title="TB", status="Refined", dependencies=["TASK-0003"], file_path=backlog_dir / "refined" / "0002-tb.md")
    tC = Task(id="0003", title="TC", status="Refined", dependencies=[], file_path=backlog_dir / "refined" / "0003-tc.md")
    write_task_file(tA)
    write_task_file(tB)
    write_task_file(tC)

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(
        "- **TASK-0001 (Refined)**: [`0001-ta`](refined/0001-ta.md)\n"
        "- **TASK-0002 (Refined)**: [`0002-tb`](refined/0002-tb.md)\n"
        "- **TASK-0003 (Refined)**: [`0003-tc`](refined/0003-tc.md)\n"
    )

    reranker = BacklogReranker(backlog_dir)
    ok, msg, res = reranker.apply()
    assert ok
    assert res.is_valid
    assert [t.canonical_id for t in res.ordered_tasks] == ["TASK-0003", "TASK-0002", "TASK-0001"]

    # Verify PRIORITY.md updated
    lines = [l for l in p_file.read_text().splitlines() if l.startswith("-")]
    assert "TASK-0003" in lines[0]
    assert "TASK-0002" in lines[1]
    assert "TASK-0001" in lines[2]


def test_reranker_pin_with_prerequisite(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    for folder in ("refined", "proposed", "complete"):
        (backlog_dir / folder).mkdir(parents=True)

    # Task 2 is pinned to pos 1, BUT Task 2 depends on Task 1!
    # Prerequisite Task 1 must precede Task 2 despite pin to pos 1.
    t1 = Task(id="0001", title="T1", status="Refined", dependencies=[], file_path=backlog_dir / "refined" / "0001-t1.md")
    t2 = Task(id="0002", title="T2", status="Refined", dependencies=["TASK-0001"], priority_pin=1, pinned=True, file_path=backlog_dir / "refined" / "0002-t2.md")
    t3 = Task(id="0003", title="T3", status="Refined", dependencies=[], file_path=backlog_dir / "refined" / "0003-t3.md")
    write_task_file(t1)
    write_task_file(t2)
    write_task_file(t3)

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(
        "- **TASK-0003 (Refined)**: [`0003-t3`](refined/0003-t3.md)\n"
        "- **TASK-0002 (Refined)**: [`0002-t2`](refined/0002-t2.md)\n"
        "- **TASK-0001 (Refined)**: [`0001-t1`](refined/0001-t1.md)\n"
    )

    reranker = BacklogReranker(backlog_dir)
    res = reranker.reorder()
    ordered_ids = [t.canonical_id for t in res.ordered_tasks]
    # T1 must precede T2!
    assert ordered_ids.index("TASK-0001") < ordered_ids.index("TASK-0002")


def test_reranker_dry_run_preserves_file(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    for folder in ("refined", "proposed", "complete"):
        (backlog_dir / folder).mkdir(parents=True)

    t1 = Task(id="0001", title="T1", status="Refined", dependencies=["TASK-0002"], file_path=backlog_dir / "refined" / "0001-t1.md")
    t2 = Task(id="0002", title="T2", status="Refined", dependencies=[], file_path=backlog_dir / "refined" / "0002-t2.md")
    write_task_file(t1)
    write_task_file(t2)

    initial_content = "- **TASK-0001 (Refined)**: [`0001-t1`](refined/0001-t1.md)\n- **TASK-0002 (Refined)**: [`0002-t2`](refined/0002-t2.md)\n"
    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(initial_content)

    reranker = BacklogReranker(backlog_dir)
    ok, msg, res = reranker.apply(dry_run=True)
    assert ok
    assert "Dry-run" in msg
    assert p_file.read_text() == initial_content
