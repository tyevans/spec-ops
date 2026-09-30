"""Hypothesis property tests for Living Architectural Review Radar (ADR-0009).

Invariant: Radar partitions all bounded context relationships into acyclic layers
without false positives on standard library imports.
"""

from __future__ import annotations

import string
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.visualizer.radar_script import (
    is_stdlib_module,
    partition_acyclic_layers,
    detect_boundary_violations,
    BoundaryViolation,
)

STDLIB_SAMPLES = ["os", "sys", "json", "pathlib", "math", "typing", "collections", "subprocess"]
CUSTOM_BCS = ["core", "visualizer", "reporting", "worker", "health", "billing", "auth", "shipping"]


@st.composite
def arbitrary_dependency_graph(draw):
    """Generates an arbitrary directed graph with mixed custom BCs and stdlib modules."""
    nodes = draw(st.lists(st.sampled_from(CUSTOM_BCS), min_size=1, max_size=8, unique=True))
    all_targets = CUSTOM_BCS + STDLIB_SAMPLES

    graph: dict[str, set[str]] = {}
    for node in nodes:
        targets = draw(st.lists(st.sampled_from(all_targets), max_size=5, unique=True))
        graph[node] = set(targets)

    # Occasionally include stdlib as top-level keys to test resilience
    if draw(st.booleans()):
        std_key = draw(st.sampled_from(STDLIB_SAMPLES))
        graph[std_key] = set(draw(st.lists(st.sampled_from(CUSTOM_BCS), max_size=3, unique=True)))

    return graph


@settings(max_examples=50, deadline=None)
@given(graph=arbitrary_dependency_graph())
def test_property_radar_partition_acyclic_layers_no_stdlib_and_unique(graph):
    """Property Invariant: Standard library modules are never partitioned into bounded context layers."""
    layers = partition_acyclic_layers(graph)

    # Invariant 1: No standard library modules in any layer
    for layer_idx, layer in enumerate(layers):
        assert isinstance(layer, list)
        for node in layer:
            assert not is_stdlib_module(node), f"Stdlib module '{node}' leaked into layer {layer_idx}"

    # Invariant 2: No duplicate nodes across layers
    all_nodes = [node for layer in layers for node in layer]
    assert len(all_nodes) == len(set(all_nodes)), f"Duplicate nodes across layers: {all_nodes}"

    # Invariant 3: Layers are sorted alphabetically within each level
    for layer in layers:
        assert layer == sorted(layer), f"Layer nodes not deterministically sorted: {layer}"


@settings(max_examples=50, deadline=None)
@given(
    bcs=st.lists(st.sampled_from(CUSTOM_BCS), min_size=2, max_size=6, unique=True),
)
def test_property_pure_dag_layer_ordering(bcs):
    """Property Invariant: For any strictly acyclic DAG, layer(u) > layer(v) whenever u depends on v."""
    # Build a strictly acyclic DAG by only allowing edges from higher index to lower index
    dag: dict[str, set[str]] = {bc: set() for bc in bcs}
    for i in range(1, len(bcs)):
        u = bcs[i]
        # u can depend on any preceding bcs[0..i-1]
        for j in range(i):
            v = bcs[j]
            dag[u].add(v)

    layers = partition_acyclic_layers(dag)

    node_to_layer = {}
    for l_idx, layer in enumerate(layers):
        for node in layer:
            node_to_layer[node] = l_idx

    # All nodes must be present in layers
    for bc in bcs:
        assert bc in node_to_layer, f"BC {bc} missing from layer mapping"

    # Topological ordering property: dependencies must be in lower layers
    for u, targets in dag.items():
        for v in targets:
            assert node_to_layer[u] > node_to_layer[v], (
                f"Topological violation: {u} (layer {node_to_layer[u]}) depends on {v} (layer {node_to_layer[v]})"
            )


@settings(max_examples=50, deadline=None)
@given(graph=arbitrary_dependency_graph())
def test_property_detect_boundary_violations_ignores_stdlib(graph):
    """Property Invariant: detect_boundary_violations never flags stdlib modules as illegal violations."""
    layers = partition_acyclic_layers(graph)
    violations = detect_boundary_violations(
        graph,
        layers=layers,
        forbidden_rules={"core": ["reporting", "shipping"]},
    )

    for v in violations:
        assert isinstance(v, BoundaryViolation)
        assert not is_stdlib_module(v.source), f"Violation source cannot be stdlib: {v.source}"
        assert not is_stdlib_module(v.target), f"Violation target cannot be stdlib: {v.target}"
        assert v.source != v.target, f"Self-dependency violation should be skipped: {v.source}"
