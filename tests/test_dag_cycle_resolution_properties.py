"""Generative Hypothesis property-based tests for deterministic DAG cycle resolution and choke points.

Governed by ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0017; PRD-0005; US-0060.
File length strictly under 400 lines.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.cycle_resolver import (
    calculate_choke_points,
    find_minimal_feedback_arc_set,
    resolve_cyclic_components,
)
from spec_ops.core.topology import (
    DirectedGraph,
    detect_cycles,
    tarjan_scc,
)


@st.composite
def random_digraph_strategy(draw: st.DrawFn) -> tuple[list[str], list[tuple[str, str]]]:
    """Generates random directed graphs with arbitrary edges, self-loops, and cycles."""
    num_nodes = draw(st.integers(min_value=2, max_value=20))
    nodes = [f"T{i:02d}" for i in range(num_nodes)]
    edges = draw(
        st.lists(
            st.tuples(st.sampled_from(nodes), st.sampled_from(nodes)),
            min_size=0,
            max_size=num_nodes * 3,
            unique=True,
        )
    )
    return nodes, edges


@st.composite
def guaranteed_cyclic_graph_strategy(draw: st.DrawFn) -> tuple[list[str], list[tuple[str, str]]]:
    """Generates directed graphs with at least one guaranteed cycle."""
    num_nodes = draw(st.integers(min_value=3, max_value=15))
    nodes = [f"T{i:02d}" for i in range(num_nodes)]

    cycle_len = draw(st.integers(min_value=2, max_value=min(num_nodes, 8)))
    cycle_nodes = draw(st.lists(st.sampled_from(nodes), min_size=cycle_len, max_size=cycle_len, unique=True))

    cycle_edges = [(cycle_nodes[i], cycle_nodes[(i + 1) % cycle_len]) for i in range(cycle_len)]
    extra_edges = draw(
        st.lists(
            st.tuples(st.sampled_from(nodes), st.sampled_from(nodes)),
            min_size=0,
            max_size=num_nodes * 2,
            unique=True,
        )
    )
    all_edges = list(set(cycle_edges + extra_edges))
    return nodes, all_edges


@given(graph_data=random_digraph_strategy())
@settings(max_examples=100)
def test_hypothesis_breaking_feedback_edges_strictly_renders_graph_acyclic(
    graph_data: tuple[list[str], list[tuple[str, str]]],
):
    """Core Invariant: Removing minimal feedback arc set strictly renders any digraph acyclic."""
    nodes, edges = graph_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    feedback_edges = find_minimal_feedback_arc_set(adj)

    # 1. Every feedback edge must have been present in the original graph
    for u, v in feedback_edges:
        assert (u, v) in edges, f"Feedback edge {(u, v)} was not in original edges"

    # 2. Construct remaining graph by removing feedback edges
    fb_set = set(feedback_edges)
    remaining_adj: dict[str, list[str]] = {
        u: [v for v in targets if (u, v) not in fb_set] for u, targets in adj.items()
    }

    # 3. Remaining graph must be strictly acyclic (zero cycles)
    remaining_sccs = tarjan_scc(remaining_adj)
    for comp in remaining_sccs:
        assert len(comp) == 1, f"Found remaining cyclic SCC of size {len(comp)}: {comp}"
        single = comp[0]
        assert single not in remaining_adj.get(single, []), f"Self-loop remained on {single}"

    remaining_cycles = detect_cycles(remaining_adj)
    assert len(remaining_cycles) == 0, f"Remaining graph has cycles: {remaining_cycles}"


@given(graph_data=guaranteed_cyclic_graph_strategy())
@settings(max_examples=100)
def test_hypothesis_cycle_resolution_minimality_and_remediation(
    graph_data: tuple[list[str], list[tuple[str, str]]],
):
    """Minimality Invariant: Every identified feedback edge is strictly necessary to break cycles."""
    nodes, edges = graph_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    resolutions = resolve_cyclic_components(adj)
    assert len(resolutions) > 0, "Guaranteed cyclic graph must yield at least one cycle resolution"

    all_fb_edges: list[tuple[str, str]] = []
    for r in resolutions:
        assert r.size >= 1
        assert len(r.feedback_edges) >= 1
        assert len(r.remediations) == len(r.feedback_edges)
        for rem in r.remediations:
            assert "Break cycle by removing dependency from" in rem
        all_fb_edges.extend(r.feedback_edges)

    fb_set = set(all_fb_edges)

    # Minimality verification: For each feedback edge e, if we re-add e, a cycle must appear
    for u, v in all_fb_edges:
        test_fb = fb_set - {(u, v)}
        test_adj = {
            n: [t for t in targets if (n, t) not in test_fb] for n, targets in adj.items()
        }
        test_cycles = detect_cycles(test_adj)
        assert len(test_cycles) > 0, f"Feedback edge {(u, v)} was redundant!"


@given(graph_data=random_digraph_strategy())
@settings(max_examples=50)
def test_hypothesis_feedback_arc_set_determinism(
    graph_data: tuple[list[str], list[tuple[str, str]]],
):
    """Determinism Invariant: Running cycle resolution repeatedly produces identical results."""
    nodes, edges = graph_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    run_1 = find_minimal_feedback_arc_set(adj)
    run_2 = find_minimal_feedback_arc_set(adj)
    assert run_1 == run_2, "Cycle resolution must be strictly deterministic across invocations"


@given(graph_data=random_digraph_strategy())
@settings(max_examples=50)
def test_hypothesis_choke_point_invariants(
    graph_data: tuple[list[str], list[tuple[str, str]]],
):
    """Choke point Invariant: Downstream impact and critical delays are bounded and monotonic."""
    nodes, edges = graph_data
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    choke_points = calculate_choke_points(adj, min_impact=1)
    prev_impact = float("inf")
    for cp in choke_points:
        assert 1 <= cp.downstream_impact <= len(nodes)
        assert 0 <= cp.critical_path_delay <= len(nodes)
        assert cp.in_degree >= 0
        assert cp.out_degree >= 0
        assert len(cp.decoupling_seams) > 0
        assert cp.downstream_impact <= prev_impact
        prev_impact = cp.downstream_impact
