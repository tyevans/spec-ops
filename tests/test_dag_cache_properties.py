"""Generative Hypothesis property-based tests for Incremental DAG Cache and Tarjan Cycle Pre-Check.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0017; PRD-0005; US-0058.
File length strictly under 400 lines.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.dag_cache import (
    DAGCachePayload,
    can_add_dependency,
    compute_reachability,
    format_cycle_path,
)
from spec_ops.core.topology import detect_cycles, tarjan_scc


@st.composite
def arbitrary_dag_strategy(draw: st.DrawFn) -> tuple[list[str], dict[str, list[str]], dict[str, set[str]]]:
    """Generates an arbitrary acyclic directed graph (DAG) with computed reachability."""
    num_nodes = draw(st.integers(min_value=3, max_value=20))
    node_names = [f"TASK-{i:04d}" for i in range(1, num_nodes + 1)]

    # Invariant: edges i -> j where i > j guarantees DAG acyclicity
    possible_edges = [(node_names[i], node_names[j]) for i in range(num_nodes) for j in range(i)]
    chosen_edges = draw(
        st.lists(
            st.sampled_from(possible_edges) if possible_edges else st.nothing(),
            min_size=0,
            max_size=len(possible_edges),
            unique=True,
        )
    )

    adj: dict[str, list[str]] = {n: [] for n in node_names}
    for u, v in chosen_edges:
        adj[u].append(v)
    for n in node_names:
        adj[n].sort()

    reach = compute_reachability(adj, node_names)
    return node_names, adj, reach


@given(dag_data=arbitrary_dag_strategy())
@settings(max_examples=80)
def test_hypothesis_dag_cycle_precheck_allows_valid_edges(
    dag_data: tuple[list[str], dict[str, list[str]], dict[str, set[str]]],
):
    """Property: For any DAG, adding edge u -> v is allowed iff v cannot reach u."""
    node_names, adj, reach = dag_data
    payload = DAGCachePayload(
        adj=adj,
        reachability={k: sorted(v) for k, v in reach.items()},
    )

    for u in node_names:
        for v in node_names:
            if u == v:
                continue
            is_backwards = u in reach.get(v, set())
            res = can_add_dependency(payload, u, v)

            if not is_backwards:
                assert res.allowed is True, f"Expected edge {u} -> {v} to be allowed"
                assert res.cycle_path == []
                assert res.path_str == ""

                # Verify actual graph with this edge remains acyclic
                augmented = {k: list(targets) for k, targets in adj.items()}
                if v not in augmented[u]:
                    augmented[u].append(v)
                cycles = detect_cycles(augmented)
                assert len(cycles) == 0, f"Graph unexpectedly became cyclic after adding {u} -> {v}"


@given(dag_data=arbitrary_dag_strategy())
@settings(max_examples=80)
def test_hypothesis_dag_cycle_precheck_rejects_cyclic_edges(
    dag_data: tuple[list[str], dict[str, list[str]], dict[str, set[str]]],
):
    """Property: For any DAG, adding edge u -> v is rejected if v can reach u."""
    node_names, adj, reach = dag_data
    payload = DAGCachePayload(
        adj=adj,
        reachability={k: sorted(v) for k, v in reach.items()},
    )

    for u in node_names:
        for v in node_names:
            if u == v:
                res = can_add_dependency(payload, u, v)
                assert res.allowed is False
                assert res.cycle_path == [u, u]
                assert res.path_str == f"{u} -> {u}"
                continue

            v_reaches_u = u in reach.get(v, set())
            if v_reaches_u:
                res = can_add_dependency(payload, u, v)
                assert res.allowed is False, f"Expected edge {u} -> {v} to be rejected"
                assert len(res.cycle_path) >= 3, f"Invalid cycle path length: {res.cycle_path}"
                assert res.cycle_path[0] == res.cycle_path[-1]
                assert res.path_str == " -> ".join(res.cycle_path)

                # Min-node rotation verification (ADR-0017)
                unique_nodes = res.cycle_path[:-1]
                assert res.cycle_path[0] == min(unique_nodes)

                # Verify that each consecutive edge in the cycle exists
                for i in range(len(res.cycle_path) - 1):
                    src_node = res.cycle_path[i]
                    tgt_node = res.cycle_path[i + 1]
                    is_original_edge = tgt_node in adj.get(src_node, [])
                    is_added_edge = (src_node == u and tgt_node == v)
                    assert is_original_edge or is_added_edge, (
                        f"Edge {src_node} -> {tgt_node} not in graph or added candidate"
                    )


@given(dag_data=arbitrary_dag_strategy())
@settings(max_examples=50)
def test_hypothesis_precheck_determinism_and_performance(
    dag_data: tuple[list[str], dict[str, list[str]], dict[str, set[str]]],
):
    """Property: can_add_dependency is idempotent and executes in < 5ms."""
    node_names, adj, reach = dag_data
    payload = DAGCachePayload(
        adj=adj,
        reachability={k: sorted(v) for k, v in reach.items()},
    )

    for u in node_names[:5]:
        for v in node_names[:5]:
            res1 = can_add_dependency(payload, u, v)
            res2 = can_add_dependency(payload, u, v)

            assert res1.allowed == res2.allowed
            assert res1.cycle_path == res2.cycle_path
            assert res1.path_str == res2.path_str
            assert res1.duration_ms < 5.0, f"Duration {res1.duration_ms}ms >= 5.0ms"
