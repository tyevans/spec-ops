"""Hypothesis generative property tests for failure clustering and prompt anti-loop synthesizer (ADR-0009)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

from spec_ops.rescue.failure_clustering import (
    ARCHETYPES,
    GENERIC_ARCHETYPE,
    ClusteredFailureEntry,
    FailureArchetype,
    FailureCluster,
    classify_failure_entry,
    cluster_failure_entries,
    synthesize_fleet_negative_constraints,
)

safe_text_chars = st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), blacklist_characters=("\r", "\n", "\0"))
safe_text = st.text(alphabet=safe_text_chars, min_size=1, max_size=80).filter(lambda s: bool(s.strip()))

known_invariants = st.sampled_from(["ADR-0003", "ADR-0002", "ADR-0019", "ADR-0018", "ADR-0017", "ADR-0001", "ADR-0005"])
any_invariant = st.one_of(
    known_invariants,
    st.integers(min_value=1, max_value=99).map(lambda n: f"ADR-{n:04d}"),
    st.text(min_size=1, max_size=10),
)

entry_strategy = st.builds(
    ClusteredFailureEntry,
    task_id=st.integers(min_value=1, max_value=9999).map(lambda n: f"TASK-{n:04d}"),
    reason=safe_text,
    attempt_date=st.sampled_from(["2026-09-28", "2026-09-29", "2026-09-30", ""]),
    timestamp=st.sampled_from(["2026-09-29T12:00:00Z", ""]),
    worker_id=st.sampled_from(["worker-1", "worker-2", ""]),
    failed_invariants=st.lists(any_invariant, max_size=3),
    source=safe_text,
)


@given(entries=st.lists(entry_strategy, min_size=0, max_size=30))
@settings(max_examples=50)
def test_clustering_conservation_no_dropped_entries(entries: list[ClusteredFailureEntry]):
    """Property: Clustering operates deterministically and conserves all entries without dropping any."""
    clusters = cluster_failure_entries(entries, include_empty=False)
    total_clustered = sum(c.count for c in clusters)
    assert total_clustered == len(entries), f"Expected {len(entries)} entries clustered, got {total_clustered}"

    clustered_entries = [e for c in clusters for e in c.entries]
    assert len(clustered_entries) == len(entries)

    # With include_empty=True, total entries is still identical
    all_clusters = cluster_failure_entries(entries, include_empty=True)
    assert sum(c.count for c in all_clusters) == len(entries)
    assert len(all_clusters) == len(ARCHETYPES) + 1


@given(entries=st.lists(entry_strategy, min_size=1, max_size=20))
@settings(max_examples=40)
def test_clustering_determinism(entries: list[ClusteredFailureEntry]):
    """Property: Repeated clustering runs on identical inputs yield identical outputs in identical order."""
    run1 = cluster_failure_entries(entries, include_empty=True)
    run2 = cluster_failure_entries(entries, include_empty=True)

    assert len(run1) == len(run2)
    for c1, c2 in zip(run1, run2):
        assert c1.archetype_id == c2.archetype_id
        assert c1.invariant_id == c2.invariant_id
        assert c1.count == c2.count
        assert [e.to_dict() for e in c1.entries] == [e.to_dict() for e in c2.entries]


@given(entries=st.lists(entry_strategy, min_size=1, max_size=25))
@settings(max_examples=40)
def test_clustering_disjoint_partition(entries: list[ClusteredFailureEntry]):
    """Property: Every input failure record belongs to exactly one cluster (strictly disjoint partition)."""
    clusters = cluster_failure_entries(entries, include_empty=False)
    seen_entry_ids: set[int] = set()

    for cluster in clusters:
        for entry in cluster.entries:
            entry_ptr = id(entry)
            assert entry_ptr not in seen_entry_ids, f"Entry {entry} found in multiple clusters"
            seen_entry_ids.add(entry_ptr)

    assert len(seen_entry_ids) == len(entries)


@given(
    inv_id=st.sampled_from(["ADR-0003", "ADR-0002", "ADR-0019", "ADR-0018", "ADR-0017"]),
    reason=safe_text,
    noise_invs=st.lists(st.sampled_from(["ADR-0001", "ADR-0005", "ADR-0009"]), max_size=2),
)
def test_archetype_mapping_invariants(inv_id: str, reason: str, noise_invs: list[str]):
    """Property: Entries citing governing invariant IDs always map to their designated archetype."""
    entry = ClusteredFailureEntry(
        task_id="TASK-0100",
        reason=reason,
        failed_invariants=[inv_id] + noise_invs,
    )
    arch = classify_failure_entry(entry)
    expected_arch = next(a for a in ARCHETYPES if a.invariant_id == inv_id)
    assert arch.archetype_id == expected_arch.archetype_id
    assert arch.invariant_id == inv_id


@given(entries=st.lists(entry_strategy, min_size=1, max_size=15))
@settings(max_examples=30)
def test_synthesize_fleet_negative_constraints_property(entries: list[ClusteredFailureEntry]):
    """Property: Fleet negative constraint synthesis generates valid markdown containing all active archetypes."""
    clusters = cluster_failure_entries(entries, include_empty=False)
    markdown = synthesize_fleet_negative_constraints(clusters)

    assert "## Prior Fleet Failures & Prohibitions" in markdown
    for cluster in clusters:
        assert cluster.name in markdown
        assert cluster.invariant_id in markdown
        assert cluster.mandate in markdown
