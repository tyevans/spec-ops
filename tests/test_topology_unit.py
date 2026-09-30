"""Comprehensive unit tests for topology, pathfinding, and graph audit engines.

Governed by ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0060, US-0063.
File length strictly under 400 lines.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.core.graph_audit import audit_bottlenecks, audit_graph_all, audit_traceability
from spec_ops.core.models import ADR, PRD, CommitInfo, Persona, ProjectData, Task, TraceabilityEdge, UserStory
from spec_ops.core.pathfinder import find_shortest_traceability_path, format_traceability_path, inspect_entity, resolve_node_id
from spec_ops.core.topology import (
    DirectedGraph,
    _extract_adj,
    _find_cycle_path,
    compute_blast_radius,
    compute_execution_tiers,
    detect_cycles,
    kahns_topological_sort,
    tarjan_scc,
)


def test_directed_graph_operations():
    g = DirectedGraph()
    g.add_node("A", type="task", label="Task A")
    g.add_node("A", status="Complete")
    assert g.nodes["A"]["status"] == "Complete"
    assert g.nodes["A"]["label"] == "Task A"

    g.add_edge("A", "B", "depends_on")
    # Duplicate edge should not duplicate in adj or rev_adj
    g.add_edge("A", "B", "depends_on")
    assert g.adj["A"] == ["B"]
    assert g.rev_adj["B"] == ["A"]
    assert g.edge_relations[("A", "B")] == "depends_on"


def test_extract_adj_formats():
    g = DirectedGraph()
    g.add_edge("X", "Y")
    nodes_g, adj_g = _extract_adj(g)
    assert nodes_g == ["X", "Y"]
    assert adj_g["X"] == ["Y"]

    dict_graph = {"A": ["B"], "B": ["C"]}
    nodes_d, adj_d = _extract_adj(dict_graph)
    assert nodes_d == ["A", "B", "C"]
    assert adj_d["A"] == ["B"]
    assert adj_d["C"] == []


def test_tarjan_scc_and_detect_cycles_variations():
    # Empty
    assert tarjan_scc({}) == []
    assert detect_cycles({}) == []

    # Single isolated node
    assert tarjan_scc({"A": []}) == [["A"]]
    assert detect_cycles({"A": []}) == []

    # Self-loop
    g_self = {"A": ["A"]}
    assert tarjan_scc(g_self) == [["A"]]
    cyc_self = detect_cycles(g_self)
    assert len(cyc_self) == 1
    assert cyc_self[0].size == 1
    assert cyc_self[0].cycle_path == ["A", "A"]
    assert cyc_self[0].feedback_edge == ("A", "A")

    # 2-node cycle
    g_two = {"A": ["B"], "B": ["A"]}
    cyc_two = detect_cycles(g_two)
    assert len(cyc_two) == 1
    assert cyc_two[0].size == 2
    assert cyc_two[0].cycle_path == ["A", "B", "A"]
    assert cyc_two[0].feedback_edge == ("B", "A")

    # Cycle with dead ends in component for _find_cycle_path
    adj_branched = {"A": ["B", "C"], "B": ["A"], "C": ["A"]}
    path = _find_cycle_path("A", {"A", "B", "C"}, adj_branched)
    assert path[0] == "A"
    assert path[-1] == "A"
    assert len(path) == 3


def test_kahns_topological_sort_acyclic_and_cyclic():
    dag = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    order, ok = kahns_topological_sort(dag)
    assert ok is True
    assert len(order) == 4
    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")

    cyc = {"A": ["B"], "B": ["A"], "C": ["A"]}
    order_c, ok_c = kahns_topological_sort(cyc)
    assert ok_c is False


def test_compute_execution_tiers_with_type_filter():
    g = DirectedGraph()
    g.add_node("TASK-0001", type="task")
    g.add_node("TASK-0002", type="task")
    g.add_node("ADR-0001", type="adr")
    g.add_edge("TASK-0002", "TASK-0001", "depends_on")
    g.add_edge("TASK-0001", "ADR-0001", "governed_by")

    res = compute_execution_tiers(g, entity_type="task")
    assert res.critical_path_depth == 1
    assert res.tiers == {0: ["TASK-0001"], 1: ["TASK-0002"]}
    assert "ADR-0001" not in res.tiers[0]


def test_compute_blast_radius_ratings():
    g = DirectedGraph()
    g.add_node("ROOT", type="adr")

    # Rating LOW: <= 4
    for i in range(2):
        g.add_node(f"TASK-000{i}", type="task", bc="core", prs=[f"#{i}"])
        g.add_edge(f"TASK-000{i}", "ROOT", "governed_by")
    res_low = compute_blast_radius(g, "ROOT")
    assert res_low.total_impact == 2
    assert res_low.impact_rating == "LOW"
    assert len(res_low.affected_tasks) == 2
    assert res_low.affected_bcs == ["core"]

    # Rating MEDIUM: 5 to 10
    for i in range(2, 7):
        g.add_node(f"TASK-000{i}", type="task", bc="visualizer")
        g.add_edge(f"TASK-000{i}", "ROOT", "governed_by")
    res_med = compute_blast_radius(g, "ROOT")
    assert res_med.total_impact == 7
    assert res_med.impact_rating == "MEDIUM"

    # Rating HIGH: > 10
    for i in range(7, 12):
        g.add_node(f"TASK-00{i}", type="task", bc="backlog")
        g.add_edge(f"TASK-00{i}", "ROOT", "governed_by")
    res_high = compute_blast_radius(g, "ROOT")
    assert res_high.total_impact == 12
    assert res_high.impact_rating == "HIGH"


def test_pathfinder_resolution_and_formatting():
    g = DirectedGraph()
    g.add_node("p1", type="persona", label="Taylor")
    g.add_node("US-0001", type="story", label="Story 1")
    g.add_node("TASK-0001", type="task", label="Task 1")
    g.add_node("c123456", type="commit", label="Commit 1")

    assert resolve_node_id(g, "persona:p1") == "p1"
    assert resolve_node_id(g, "Taylor") == "p1"
    assert resolve_node_id(g, "task:TASK-0001") == "TASK-0001"
    assert resolve_node_id(g, "UNKNOWN") is None

    g.add_edge("p1", "US-0001", "desires")
    g.add_edge("US-0001", "TASK-0001", "implements")
    g.add_edge("TASK-0001", "c123456", "committed_in")

    path = find_shortest_traceability_path(g, "Taylor", "c123456")
    assert len(path) == 3

    assert find_shortest_traceability_path(g, "Taylor", "Taylor") == []
    assert find_shortest_traceability_path(g, "NONEXISTENT", "c123456") == []
    assert find_shortest_traceability_path(g, "Taylor", "NONEXISTENT") == []

    fmt = format_traceability_path(path, graph=g)
    assert "persona:p1" in fmt
    assert "story:US-0001" in fmt
    assert "task:TASK-0001" in fmt
    assert "commit:c123456" in fmt
    assert "Path length: 3 hops." in fmt

    assert format_traceability_path([]) == "No unbroken traceability path found."
    single_hop = [("A", "desires", "B")]
    assert "Path length: 1 hop." in format_traceability_path(single_hop)


def test_inspect_entity_formatting():
    g = DirectedGraph()
    g.add_node("TASK-0042", type="task", status="Refined", bc="invariants")
    g.add_node("ADR-0003", type="adr")
    g.add_node("US-0020", type="story")
    g.add_edge("TASK-0042", "ADR-0003", "governed_by")
    g.add_edge("US-0020", "TASK-0042", "implements")

    card = inspect_entity(g, "TASK-0042")
    assert "TASK-0042" in card
    assert "Task (Refined)" in card
    assert "invariants" in card
    assert "ADR-0003" in card
    assert "US-0020" in card
    assert "Upstream Dependencies (1st-degree):" in card
    assert "Downstream Dependents (1st-degree):" in card


def test_graph_audit_traceability_clean_and_errors():
    # Clean project
    clean_data = ProjectData(
        personas=[Persona(id="alex", name="Alex")],
        stories=[UserStory(id="US-0001", title="S1", persona="Alex", governing_prd="PRD-0001")],
        prds=[PRD(id="PRD-0001", title="P1", target_persona="Alex", linked_stories=["US-0001"])],
        tasks=[Task(id="TASK-0001", title="T1", governing_stories=["US-0001"])],
        edges=[
            TraceabilityEdge("persona", "alex", "story", "US-0001", "desires"),
            TraceabilityEdge("story", "US-0001", "prd", "PRD-0001", "specifies"),
            TraceabilityEdge("prd", "PRD-0001", "task", "TASK-0001", "implements"),
        ],
    )
    code, msgs = audit_traceability(clean_data)
    assert code == 0
    assert any("100% graph connectivity" in m for m in msgs)

    # Inconsistent boundary: PRD claims story that specifies another PRD
    bad_boundary = ProjectData(
        personas=[Persona(id="alex", name="Alex")],
        stories=[UserStory(id="US-0015", title="S15", persona="Alex", governing_prd="PRD-0003")],
        prds=[
            PRD(id="PRD-0002", title="P2", target_persona="Alex", linked_stories=["US-0015"]),
            PRD(id="PRD-0003", title="P3", target_persona="Alex", linked_stories=["US-0015"]),
        ],
        tasks=[],
    )
    code_b, msgs_b = audit_traceability(bad_boundary)
    assert code_b == 1
    assert any("Inconsistent Traceability Boundary: US-0015 is claimed by PRD-0002 but specifies PRD-0003" in m for m in msgs_b)

    # Missing story error
    bad_task = ProjectData(
        personas=[],
        stories=[],
        prds=[],
        tasks=[Task(id="TASK-0030", title="T30", file_path=Path("0030-orphan-feature.md"), raw_markdown="story: US-9999")],
    )
    code_t, msgs_t = audit_traceability(bad_task)
    assert code_t == 1
    assert any("Task 0030-orphan-feature references missing story 'US-9999'" in m for m in msgs_t)

    # Missing PRD error
    bad_story = ProjectData(
        personas=[],
        stories=[UserStory(id="US-0001", title="S1", governing_prd="PRD-9999")],
        prds=[],
        tasks=[],
    )
    code_s, msgs_s = audit_traceability(bad_story)
    assert code_s == 1
    assert any("Story US-0001 references missing PRD 'PRD-9999'" in m for m in msgs_s)


def test_graph_audit_bottlenecks_and_forecast():
    # Circular deadlock
    cyc_data = ProjectData(
        tasks=[
            Task(id="TASK-0021", title="T21", dependencies=["TASK-0022"]),
            Task(id="TASK-0022", title="T22", dependencies=["TASK-0021"]),
        ]
    )
    code_c, msgs_c = audit_bottlenecks(cyc_data)
    assert code_c == 1
    assert any("Cyclic Backlog Dependency Detected" in m for m in msgs_c)
    assert any("TASK-0021 -> TASK-0022 -> TASK-0021" in m for m in msgs_c)

    # Forecast starvation
    starve_data = ProjectData(
        tasks=[
            Task(id="TASK-0001", title="T1", status="Refined"),
            Task(id="TASK-0002", title="T2", status="Proposed", dependencies=["TASK-0001"]),
        ]
    )
    code_f, msgs_f = audit_bottlenecks(starve_data, forecast=True)
    assert code_f == 0
    assert any("Buffer Starvation Imminent" in m for m in msgs_f)

    # High fanout choke point
    choke_data = ProjectData(
        tasks=[
            Task(id="TASK-0013", title="Choke", status="Proposed"),
            Task(id="TASK-0020", title="T20", status="Proposed", dependencies=["TASK-0013"]),
            Task(id="TASK-0021", title="T21", status="Proposed", dependencies=["TASK-0013"]),
        ]
    )
    code_cp, msgs_cp = audit_bottlenecks(choke_data)
    assert code_cp == 0
    assert any("TASK-0013" in m for m in msgs_cp)
    assert any("pulsing alert aura" in m for m in msgs_cp)

    # Audit all
    code_all, msgs_all = audit_graph_all(clean_data := ProjectData())
    assert isinstance(code_all, int)
    assert len(msgs_all) > 0
