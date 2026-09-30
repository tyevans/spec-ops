"""Comprehensive unit and benchmark tests for Tarjan SCC, topological sorting, and blast-radius traversal.

Governed by ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0060, US-0063.
File length strictly under 400 lines.
"""

from __future__ import annotations

import pytest

from spec_ops.core.models import (
    ADR,
    PRD,
    Persona,
    ProjectData,
    Task,
    TraceabilityEdge,
    UserStory,
)
from spec_ops.core.spikes.topology_spike import (
    BlastRadiusResult,
    CycleResult,
    DirectedGraph,
    TopologicalTierResult,
    TopologyBenchmarkResult,
    benchmark_topology_spike,
    compute_blast_radius,
    compute_execution_tiers,
    detect_cycles,
    find_shortest_traceability_path,
    kahns_topological_sort,
    tarjan_scc,
)


def test_topological_execution_order_us0060_scenario1():
    """US-0060: Computing valid topological task execution order for a multi-stage backlog."""
    g = DirectedGraph()
    for tid in ["TASK-0001", "TASK-0002", "TASK-0003", "TASK-0004"]:
        g.add_node(tid, type="task")

    g.add_edge("TASK-0002", "TASK-0001", "depends_on")
    g.add_edge("TASK-0003", "TASK-0001", "depends_on")
    g.add_edge("TASK-0004", "TASK-0002", "depends_on")
    g.add_edge("TASK-0004", "TASK-0003", "depends_on")

    res = compute_execution_tiers(g)
    assert res.critical_path_depth == 2
    assert len(res.quarantined_cycles) == 0
    assert len(res.quarantined_nodes) == 0

    assert res.tiers == {
        0: ["TASK-0001"],
        1: ["TASK-0002", "TASK-0003"],
        2: ["TASK-0004"],
    }
    expected_output = (
        "1. TASK-0001 (depth: 0)\n"
        "2. TASK-0002 (depth: 1)\n"
        "3. TASK-0003 (depth: 1)\n"
        "4. TASK-0004 (depth: 2)"
    )
    assert res.formatted_sequence == expected_output


def test_detect_multi_node_cycle_us0060_scenario2():
    """US-0060: Detecting a multi-node circular dependency with exact cycle path traceback."""
    g = DirectedGraph()
    g.add_edge("TASK-0010", "TASK-0011", "depends_on")
    g.add_edge("TASK-0011", "TASK-0012", "depends_on")
    g.add_edge("TASK-0012", "TASK-0010", "depends_on")

    cycles = detect_cycles(g)
    assert len(cycles) == 1
    c = cycles[0]
    assert c.size == 3
    assert set(c.scc) == {"TASK-0010", "TASK-0011", "TASK-0012"}
    assert c.path_str == "TASK-0010 -> TASK-0011 -> TASK-0012 -> TASK-0010"
    assert c.feedback_edge == ("TASK-0012", "TASK-0010")
    assert c.remediation == "Break cycle by removing dependency from TASK-0012 to TASK-0010"


def test_cross_entity_circular_traps_us0060_scenario3():
    """US-0060: Catching cross-entity circular reference traps between PRDs and User Stories."""
    g = DirectedGraph()
    g.add_node("PRD-0002", type="prd")
    g.add_node("PRD-0003", type="prd")
    g.add_node("US-0015", type="story")

    # PRD-0002 claims implementing US-0015; US-0015 specifies PRD-0003; PRD-0003 points to PRD-0002
    g.add_edge("PRD-0002", "US-0015", "implements")
    g.add_edge("US-0015", "PRD-0003", "specifies")
    g.add_edge("PRD-0003", "PRD-0002", "depends_on")

    cycles = detect_cycles(g)
    assert len(cycles) == 1
    c = cycles[0]
    assert c.size == 3
    assert set(c.scc) == {"PRD-0002", "PRD-0003", "US-0015"}
    assert c.path_str == "PRD-0002 -> US-0015 -> PRD-0003 -> PRD-0002"
    assert c.feedback_edge == ("PRD-0003", "PRD-0002")


def test_self_loop_cycle_detection():
    """Verify single-node self-loop is detected as a cycle of size 1."""
    g = DirectedGraph()
    g.add_edge("TASK-0099", "TASK-0099", "depends_on")

    cycles = detect_cycles(g)
    assert len(cycles) == 1
    c = cycles[0]
    assert c.size == 1
    assert c.cycle_path == ["TASK-0099", "TASK-0099"]
    assert c.feedback_edge == ("TASK-0099", "TASK-0099")
    assert "from TASK-0099 to TASK-0099" in c.remediation


def test_kahns_algorithm_comparison():
    """Compare Kahn's algorithm behavior on DAG vs cyclic digraph."""
    g_dag = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    order, is_acyclic = kahns_topological_sort(g_dag)
    assert is_acyclic is True
    assert len(order) == 4
    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")

    g_cycle = {"X": ["Y"], "Y": ["Z"], "Z": ["X"]}
    order_cyc, is_acyclic_cyc = kahns_topological_sort(g_cycle)
    assert is_acyclic_cyc is False
    assert len(order_cyc) == 0  # Kahn cannot order any node in a pure cycle


def test_deadlock_quarantine_and_partial_tiering():
    """Verify acyclic clusters are scheduled while cyclic components are quarantined."""
    g = DirectedGraph()
    # Acyclic cluster
    g.add_edge("TASK-0002", "TASK-0001", "depends_on")

    # Cyclic cluster
    g.add_edge("TASK-0010", "TASK-0011", "depends_on")
    g.add_edge("TASK-0011", "TASK-0010", "depends_on")

    # Trapped task depending on cyclic cluster
    g.add_edge("TASK-0012", "TASK-0011", "depends_on")

    tier_res = compute_execution_tiers(g)
    assert "TASK-0001" in tier_res.tiers[0]
    assert "TASK-0002" in tier_res.tiers[1]
    assert "TASK-0010" in tier_res.quarantined_nodes
    assert "TASK-0011" in tier_res.quarantined_nodes
    assert "TASK-0012" in tier_res.quarantined_nodes
    assert len(tier_res.quarantined_cycles) == 1


def test_shortest_traceability_path_us0063_scenario2():
    """US-0063: Finding shortest traceability path between persona and commit."""
    g = DirectedGraph()
    g.add_edge("persona:taylor", "story:US-0046", "desires")
    g.add_edge("story:US-0046", "task:TASK-0046", "implements")
    g.add_edge("task:TASK-0046", "commit:a1b2c3d", "committed_in")

    path = find_shortest_traceability_path(g, "persona:taylor", "commit:a1b2c3d")
    assert len(path) == 3
    assert path == [
        ("persona:taylor", "desires", "story:US-0046"),
        ("story:US-0046", "implements", "task:TASK-0046"),
        ("task:TASK-0046", "committed_in", "commit:a1b2c3d"),
    ]

    # Non-existent path returns empty list
    assert find_shortest_traceability_path(g, "persona:taylor", "unknown") == []
    # Same node returns empty list
    assert find_shortest_traceability_path(g, "persona:taylor", "persona:taylor") == []


def test_blast_radius_us0063_scenario3():
    """US-0063: Calculating downstream blast radius of an ADR before superseding it."""
    g = DirectedGraph()
    g.add_node("ADR-0003", type="adr")
    tasks = ["TASK-0002", "TASK-0020", "TASK-0042", "TASK-0050", "TASK-0060", "TASK-0070", "TASK-0080", "TASK-0090"]
    bcs = ["core", "invariants", "visualizer"]

    for idx, tid in enumerate(tasks):
        g.add_node(
            tid,
            type="task",
            bc=bcs[idx % 3],
            prs=["#104"] if idx == 0 else (["#112"] if idx == 1 else []),
        )
        g.add_edge(tid, "ADR-0003", "governed_by")

    # Add 5 transitive dependencies
    for i in range(1, 6):
        node_id = f"DOWN-{i:04d}"
        g.add_node(node_id, type="other")
        g.add_edge(node_id, "TASK-0002", "depends_on")

    res = compute_blast_radius(g, "ADR-0003")
    assert res.total_impact == 13
    assert res.impact_rating == "HIGH"
    assert len(res.affected_tasks) == 8
    assert res.affected_bcs == ["core", "invariants", "visualizer"]
    assert res.affected_prs == ["#104", "#112"]
    assert "Total Downstream Impact: HIGH (13 nodes affected)" in res.formatted_summary


def test_blast_radius_impact_ratings():
    """Verify LOW, MEDIUM, and HIGH impact ratings for blast radius."""
    g = DirectedGraph()
    g.add_node("ROOT", type="adr")

    # 3 nodes: LOW
    for i in range(3):
        g.add_edge(f"T{i}", "ROOT", "governed_by")
    assert compute_blast_radius(g, "ROOT").impact_rating == "LOW"

    # 7 nodes: MEDIUM
    for i in range(3, 7):
        g.add_edge(f"T{i}", "ROOT", "governed_by")
    assert compute_blast_radius(g, "ROOT").impact_rating == "MEDIUM"

    # 11 nodes: HIGH
    for i in range(7, 11):
        g.add_edge(f"T{i}", "ROOT", "governed_by")
    assert compute_blast_radius(g, "ROOT").impact_rating == "HIGH"


def test_directed_graph_from_project_data():
    """Verify DirectedGraph hydration from core ProjectData domain model."""
    data = ProjectData(
        personas=[Persona(id="p1", name="Taylor")],
        stories=[UserStory(id="US-0001", title="Story 1", persona="Taylor")],
        prds=[PRD(id="PRD-0001", title="PRD 1", status="Accepted")],
        tasks=[
            Task(id="TASK-0001", title="Task 1", target_bc="core", prs=["#1"]),
            Task(id="TASK-0002", title="Task 2", target_bc="core"),
        ],
        adrs=[ADR(id="ADR-0001", title="ADR 1", domain="core")],
        edges=[
            TraceabilityEdge("persona", "p1", "story", "US-0001", "desires"),
            TraceabilityEdge("task", "TASK-0002", "task", "TASK-0001", "depends_on"),
            TraceabilityEdge("task", "TASK-0001", "adr", "ADR-0001", "governed_by"),
        ],
    )
    g = DirectedGraph.from_project_data(data)
    assert "p1" in g.nodes
    assert "US-0001" in g.nodes
    assert "TASK-0001" in g.nodes
    assert "ADR-0001" in g.nodes
    assert ("p1", "US-0001") in g.edge_relations
    assert g.edge_relations[("p1", "US-0001")] == "desires"

    # Check execution tiers and blast radius on hydrated graph
    tier_res = compute_execution_tiers(g, entity_type="task")
    assert tier_res.tiers[0] == ["TASK-0001"]
    assert tier_res.tiers[1] == ["TASK-0002"]

    blast = compute_blast_radius(g, "ADR-0001")
    assert "TASK-0001" in blast.downstream_nodes
    assert "TASK-0002" in blast.downstream_nodes


def test_spike_benchmark_performance_dod():
    """DoD Invariant 1 & 4: 5,000 nodes, 10 injected cycles in <15ms; blast radius in <5ms."""
    bench = benchmark_topology_spike(num_nodes=5000, num_cycles=10)
    assert bench.num_nodes == 5000
    assert bench.num_injected_cycles == 10
    assert bench.detected_cycles_count == 10
    assert bench.tarjan_duration_ms < 15.0, f"Tarjan SCC took {bench.tarjan_duration_ms:.2f}ms >= 15ms"
    assert bench.blast_radius_duration_ms < 5.0, f"Blast radius took {bench.blast_radius_duration_ms:.2f}ms >= 5ms"
    assert bench.tarjan_sub_15ms is True
    assert bench.blast_sub_5ms is True
