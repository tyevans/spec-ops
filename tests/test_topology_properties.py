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

from spec_ops.core.topology import (
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


@st.composite
def dag_strategy(draw: st.DrawFn) -> tuple[list[str], list[tuple[str, str]]]:
    """Generates guaranteed Directed Acyclic Graphs (DAGs) using upper-triangular edge sampling."""
    num_nodes = draw(st.integers(min_value=2, max_value=20))
    nodes = [f"TASK-{i:04d}" for i in range(1, num_nodes + 1)]
    valid_edges = [(nodes[i], nodes[j]) for i in range(num_nodes) for j in range(i + 1, num_nodes)]
    edges = draw(st.lists(st.sampled_from(valid_edges), min_size=0, max_size=len(valid_edges), unique=True)) if valid_edges else []
    return nodes, edges


@given(dag_data=dag_strategy())
@settings(max_examples=100)
def test_hypothesis_dag_topological_sort_order_invariant(
    dag_data: tuple[list[str], list[tuple[str, str]]],
):
    """Hypothesis Invariant: For any generated DAG, topological sort produces an ordering where for every directed edge (u, v), u appears before v."""
    nodes, edges = dag_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        adj[u].append(v)

    order, is_acyclic = kahns_topological_sort(adj)
    assert is_acyclic is True, f"Generated graph must be acyclic: {edges}"
    assert len(order) == len(nodes)

    index_map = {node: i for i, node in enumerate(order)}
    for u, v in edges:
        assert index_map[u] < index_map[v], (
            f"Topological sort invariant violated: edge ({u}, {v}) but {u} at index {index_map[u]} >= {v} at index {index_map[v]}"
        )


@st.composite
def cyclic_graph_strategy(draw: st.DrawFn) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    """Generates directed graphs with at least one guaranteed elementary cycle."""
    num_nodes = draw(st.integers(min_value=3, max_value=20))
    nodes = [f"TASK-{i:04d}" for i in range(1, num_nodes + 1)]

    # Draw a subset of 2 to 5 nodes to form an injected cycle
    cycle_size = draw(st.integers(min_value=2, max_value=min(5, num_nodes)))
    cycle_nodes = draw(st.lists(st.sampled_from(nodes), min_size=cycle_size, max_size=cycle_size, unique=True))

    cycle_edges = [(cycle_nodes[i], cycle_nodes[(i + 1) % cycle_size]) for i in range(cycle_size)]

    # Draw additional random background edges
    extra_edges = draw(
        st.lists(
            st.tuples(st.sampled_from(nodes), st.sampled_from(nodes)),
            min_size=0,
            max_size=num_nodes * 2,
            unique=True,
        )
    )

    all_edges = list(set(cycle_edges + extra_edges))
    return nodes, all_edges, cycle_nodes


@given(cyclic_data=cyclic_graph_strategy())
@settings(max_examples=100)
def test_hypothesis_cyclic_graph_always_reports_cycles(
    cyclic_data: tuple[list[str], list[tuple[str, str]], list[str]],
):
    """Hypothesis Invariant: For any cyclic graph, cycle detection always reports non-empty cycles."""
    nodes, edges, cycle_nodes = cyclic_data
    g = DirectedGraph()
    for n in nodes:
        g.add_node(n)
    for u, v in edges:
        g.add_edge(u, v)

    cycles = detect_cycles(g)
    assert len(cycles) > 0, f"Expected cycles but none detected! Cycle nodes: {cycle_nodes}, edges: {edges}"
    for c in cycles:
        assert c.size >= 1
        assert len(c.cycle_path) >= 2
        assert c.cycle_path[0] == c.cycle_path[-1]

