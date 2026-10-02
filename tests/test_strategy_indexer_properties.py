"""Hypothesis generative property tests for Strategy Indexer determinism and ranking."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.rescue.strategy_indexer import (
    HealingPlaybook,
    StrategyIndexer,
    export_playbook,
)
from spec_ops.scaffold.init import init_project


@st.composite
def failure_entries_strategy(draw: st.DrawFn) -> list[dict[str, str]]:
    num_entries = draw(st.integers(min_value=1, max_value=8))
    invs = ["ADR-0002", "ADR-0003", "ADR-0005", "ADR-0007", "ADR-0009", "ADR-0016", "ADR-0018"]
    entries = []
    for i in range(num_entries):
        inv = draw(st.sampled_from(invs))
        entries.append(
            {
                "task_id": f"TASK-{1000 + i}",
                "reason": f"Failure reason involving {inv} and violation details {i}",
                "failed_invariants": [inv],
            }
        )
    return entries


@given(entries=failure_entries_strategy())
@settings(max_examples=30)
def test_strategy_indexing_determinism_property(tmp_path_factory: pytest.TempPathFactory, entries: list[dict[str, str]]) -> None:
    """Property: Indexing arbitrary failure logs produces deterministic rankings with zero duplicate strategy IDs."""
    repo = tmp_path_factory.mktemp("prop_repo")
    init_project(name="PropRepo", target_dir=repo)
    failures_dir = repo / ".specops" / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    (failures_dir / "failures.json").write_text(json.dumps(entries), encoding="utf-8")

    indexer = StrategyIndexer(repo)
    pb1 = indexer.compile_playbook()
    pb2 = indexer.compile_playbook()

    # Determinism: exact same ordering and scores
    assert [s.strategy_id for s in pb1.strategies] == [s.strategy_id for s in pb2.strategies]
    assert [s.ranking_score for s in pb1.strategies] == [s.ranking_score for s in pb2.strategies]

    # No duplicate strategy IDs
    ids = [s.strategy_id for s in pb1.strategies]
    assert len(ids) == len(set(ids))

    # Valid export
    md_p = repo / "playbook.md"
    export_playbook(pb1, md_p)
    assert md_p.is_file()
    text = md_p.read_text(encoding="utf-8")
    assert "# SpecOps Autonomous Failure Healing Playbook" in text
    assert len(text) > 100
