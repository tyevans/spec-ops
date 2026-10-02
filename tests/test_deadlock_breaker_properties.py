"""Hypothesis property-based tests for Task Dependency Deadlock Resolver."""

from __future__ import annotations

from hypothesis import given, strategies as st

from spec_ops.core.deadlock_breaker import (
    compute_minimum_feedback_arc_set,
    tarjan_scc,
)


@st.composite
def random_directed_graphs(draw: st.DrawFn) -> dict[str, list[str]]:
    """Generates random directed graphs with possible cycles and self-loops."""
    num_nodes = draw(st.integers(min_value=1, max_value=12))
    node_names = [f"TASK-{str(i).zfill(4)}" for i in range(1, num_nodes + 1)]
    graph: dict[str, list[str]] = {n: [] for n in node_names}

    for u in node_names:
        targets = draw(st.lists(st.sampled_from(node_names), max_size=4, unique=True))
        graph[u] = targets

    return graph


@given(graph=random_directed_graphs())
def test_property_feedback_arc_set_restores_dag_acyclicity(graph: dict[str, list[str]]) -> None:
    """Invariant: For any arbitrary directed graph, applying the computed edge cut guarantees an acyclic DAG."""
    cuts = compute_minimum_feedback_arc_set(graph)
    assert isinstance(cuts, list)
    cut_set = set(cuts)

    # Prune edges in cut_set
    pruned_graph: dict[str, list[str]] = {
        u: [v for v in neighbors if (u, v) not in cut_set]
        for u, neighbors in graph.items()
    }

    # Verify pruned graph is strictly acyclic
    sccs = tarjan_scc(pruned_graph)
    for scc in sccs:
        # No component has > 1 node
        assert len(scc) <= 1
        # No 1-node self-loops exist
        if len(scc) == 1:
            assert scc[0] not in pruned_graph.get(scc[0], [])
