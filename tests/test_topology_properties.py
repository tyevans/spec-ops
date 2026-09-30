"""Generative Hypothesis property-based tests for Tarjan SCC, condensation DAG, and topology invariants.

Governed by ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0060, US-0063.
File length strictly under 400 lines.
"""

from __future__ import annotations

from collections import deque
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.spikes.topology_spike import (
    DirectedGraph,
    compute_execution_tiers,
    detect_cycles,
    kahns_topological_sort,
    tarjan_scc,
)


@st.composite
def directed_graph_strategy(draw: st.DrawFn) -> tuple[list[str], list[tuple[str, str]]]:
    """Generates random directed graphs with arbitrary connectivity, self-loops, and cycles."""
    num_nodes = draw(st.integers(min_value=2, max_value=25))
    nodes = [f"N{i:02d}" for i in range(num_nodes)]
    edge_pairs = draw(
        st.lists(
            st.tuples(st.sampled_from(nodes), st.sampled_from(nodes)),
            min_size=0,
            max_size=num_nodes * 3,
            unique=True,
        )
    )
    return nodes, edge_pairs


@given(graph_data=directed_graph_strategy())
@settings(max_examples=100)
def test_hypothesis_tarjan_scc_partition_invariants(graph_data: tuple[list[str], list[tuple[str, str]]]):
    """Partition invariant: Tarjan SCC partitions V into disjoint non-empty sets whose union is V."""
    nodes, edges = graph_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    sccs = tarjan_scc(adj)

    # 1. Non-empty
    assert len(sccs) > 0

    # 2. Disjoint and union equals all nodes
    seen_nodes: set[str] = set()
    for comp in sccs:
        assert len(comp) > 0
        comp_set = set(comp)
        assert len(comp_set) == len(comp), "Component contains duplicate nodes"
        assert seen_nodes.isdisjoint(comp_set), "SCCs must be mutually disjoint"
        seen_nodes.update(comp_set)

    assert seen_nodes == set(nodes), "Union of SCCs must equal total graph nodes"


@given(graph_data=directed_graph_strategy())
@settings(max_examples=100)
def test_hypothesis_condensation_graph_is_strictly_dag(graph_data: tuple[list[str], list[tuple[str, str]]]):
    """Condensation DAG invariant: The condensation of any directed graph is strictly an acyclic DAG."""
    nodes, edges = graph_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    sccs = tarjan_scc(adj)

    # Map each node to its SCC index
    node_to_scc: dict[str, int] = {}
    for idx, comp in enumerate(sccs):
        for node in comp:
            node_to_scc[node] = idx

    # Build condensation graph
    cond_adj: dict[str, list[str]] = {f"SCC_{i}": [] for i in range(len(sccs))}
    for u, v in edges:
        scc_u = node_to_scc[u]
        scc_v = node_to_scc[v]
        if scc_u != scc_v:
            target = f"SCC_{scc_v}"
            source = f"SCC_{scc_u}"
            if target not in cond_adj[source]:
                cond_adj[source].append(target)

    # Kahn's algorithm on condensation graph must find zero cycles
    order, is_acyclic = kahns_topological_sort(cond_adj)
    assert is_acyclic is True, f"Condensation graph must be strictly acyclic DAG! Order: {order}"
    assert len(order) == len(sccs)


@given(graph_data=directed_graph_strategy())
@settings(max_examples=100)
def test_hypothesis_scc_strong_connectivity_and_cycle_property(
    graph_data: tuple[list[str], list[tuple[str, str]]],
):
    """Strong connectivity invariant: in every SCC of size > 1, all nodes are mutually reachable."""
    nodes, edges = graph_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    sccs = tarjan_scc(adj)

    for comp in sccs:
        if len(comp) > 1:
            comp_set = set(comp)
            # Check mutual reachability within component
            for root in comp:
                visited: set[str] = set()
                queue: deque[str] = deque([root])
                while queue:
                    curr = queue.popleft()
                    for nxt in adj.get(curr, []):
                        if nxt in comp_set and nxt not in visited:
                            visited.add(nxt)
                            queue.append(nxt)
                # Since size > 1, every other node in SCC must be reachable from root
                reachable_in_comp = (visited | {root}) & comp_set
                assert reachable_in_comp == comp_set, f"Node {root} cannot reach all members of SCC {comp}"


@given(graph_data=directed_graph_strategy())
@settings(max_examples=100)
def test_hypothesis_cycle_detection_and_feedback_edge_integrity(
    graph_data: tuple[list[str], list[tuple[str, str]]],
):
    """Cycle traceback invariant: detected cycles are valid closed paths with executable feedback edges."""
    nodes, edges = graph_data
    g = DirectedGraph()
    for n in nodes:
        g.add_node(n)
    for u, v in edges:
        g.add_edge(u, v)

    cycles = detect_cycles(g)

    for c in cycles:
        assert c.size >= 1
        path = c.cycle_path
        assert len(path) >= 2
        assert path[0] == path[-1], f"Cycle path must close on itself: {c.path_str}"

        # Verify each hop in path is a real edge in the graph
        for i in range(len(path) - 1):
            src, tgt = path[i], path[i + 1]
            assert tgt in g.adj.get(src, []), f"Edge {src} -> {tgt} not in graph adjacency!"

        # Verify feedback edge is the closing edge
        fb_src, fb_tgt = c.feedback_edge
        assert fb_src == path[-2]
        assert fb_tgt == path[-1]
        assert f"{fb_src} to {fb_tgt}" in c.remediation


@given(graph_data=directed_graph_strategy())
@settings(max_examples=100)
def test_hypothesis_topological_execution_tiering_invariant(
    graph_data: tuple[list[str], list[tuple[str, str]]],
):
    """Execution tier invariant: acyclic components have strictly monotonic dependency depths."""
    nodes, edges = graph_data
    g = DirectedGraph()
    for n in nodes:
        g.add_node(n)
    for u, v in edges:
        # In dependency graph: u depends on v
        g.add_edge(u, v, "depends_on")

    tier_res = compute_execution_tiers(g)

    # 1. Total nodes accounted for
    all_acyclic = {node for t in tier_res.tiers.values() for node in t}
    assert all_acyclic.isdisjoint(tier_res.quarantined_nodes)
    assert all_acyclic | tier_res.quarantined_nodes == set(nodes)

    # 2. Depth monotonicity: if u depends on v and both are acyclic, depth[u] > depth[v]
    depth_map: dict[str, int] = {}
    for d, tier_nodes in tier_res.tiers.items():
        for n in tier_nodes:
            depth_map[n] = d

    for u, v in edges:
        if u in depth_map and v in depth_map:
            assert depth_map[u] > depth_map[v], (
                f"Dependency depth violation: {u} (depth {depth_map[u]}) depends on {v} (depth {depth_map[v]})"
            )

    # 3. Critical path depth matches maximum tier
    if depth_map:
        assert tier_res.critical_path_depth == max(depth_map.values())
    else:
        assert tier_res.critical_path_depth == 0
