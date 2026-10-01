"""Unit tests for deterministic DAG cycle resolution and choke point pruning.

Governed by ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0017; PRD-0005; US-0060.
File length strictly under 400 lines.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import pytest

from spec_ops.cli.graph_handler import handle_graph_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.cycle_resolver import (
    ChokePoint,
    CycleResolution,
    calculate_choke_points,
    find_minimal_feedback_arc_set,
    format_choke_points,
    format_cycle_resolutions,
    resolve_cyclic_components,
    suggest_decoupling_seams,
)
from spec_ops.core.topology import DirectedGraph, detect_cycles, tarjan_scc
from spec_ops.scaffold.init import init_project


def test_self_loop_cycle_resolution():
    """Single-node self loop A -> A is resolved with feedback edge (A, A)."""
    adj = {"A": ["A"]}
    resolutions = resolve_cyclic_components(adj)
    assert len(resolutions) == 1
    res = resolutions[0]
    assert res.scc == ["A"]
    assert res.cycle_path == ["A", "A"]
    assert res.feedback_edges == [("A", "A")]
    assert "Break cycle by removing dependency from A to A" in res.remediations[0]

    # Verify removing feedback edge renders acyclic
    fb = set(res.feedback_edges)
    rem_adj = {u: [v for v in vs if (u, v) not in fb] for u, vs in adj.items()}
    assert len(detect_cycles(rem_adj)) == 0


def test_two_node_mutual_cycle():
    """Two-node cycle A -> B -> A is resolved with feedback edge (B, A)."""
    adj = {"A": ["B"], "B": ["A"]}
    resolutions = resolve_cyclic_components(adj)
    assert len(resolutions) == 1
    res = resolutions[0]
    assert res.scc == ["A", "B"]
    assert res.cycle_path == ["A", "B", "A"]
    assert ("B", "A") in res.feedback_edges

    fb = set(res.feedback_edges)
    rem_adj = {u: [v for v in vs if (u, v) not in fb] for u, vs in adj.items()}
    assert len(detect_cycles(rem_adj)) == 0


def test_three_node_cycle():
    """Three-node cycle A -> B -> C -> A is resolved with feedback edge (C, A)."""
    adj = {"A": ["B"], "B": ["C"], "C": ["A"]}
    resolutions = resolve_cyclic_components(adj)
    assert len(resolutions) == 1
    res = resolutions[0]
    assert res.scc == ["A", "B", "C"]
    assert res.cycle_path == ["A", "B", "C", "A"]
    assert res.feedback_edge == ("C", "A")
    assert ("C", "A") in res.feedback_edges

    fb = set(res.feedback_edges)
    rem_adj = {u: [v for v in vs if (u, v) not in fb] for u, vs in adj.items()}
    assert len(detect_cycles(rem_adj)) == 0


def test_figure_eight_intersecting_cycles():
    """Figure-8 cycle (A->B->C->A and C->D->E->C) requires 2 feedback edges."""
    adj = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A", "D"],
        "D": ["E"],
        "E": ["C"],
    }
    resolutions = resolve_cyclic_components(adj)
    assert len(resolutions) == 1
    res = resolutions[0]
    assert set(res.scc) == {"A", "B", "C", "D", "E"}
    assert len(res.feedback_edges) == 2

    fb = set(res.feedback_edges)
    rem_adj = {u: [v for v in vs if (u, v) not in fb] for u, vs in adj.items()}
    assert len(detect_cycles(rem_adj)) == 0


def test_complete_graph_k3():
    """Complete graph K3 with 6 directed edges is resolved into an acyclic DAG."""
    adj = {
        "A": ["B", "C"],
        "B": ["A", "C"],
        "C": ["A", "B"],
    }
    fb_edges = find_minimal_feedback_arc_set(adj)
    assert len(fb_edges) == 3

    fb = set(fb_edges)
    rem_adj = {u: [v for v in vs if (u, v) not in fb] for u, vs in adj.items()}
    assert len(detect_cycles(rem_adj)) == 0


def test_acyclic_graph_resolution():
    """Acyclic DAG returns zero cycle resolutions and zero feedback edges."""
    adj = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    resolutions = resolve_cyclic_components(adj)
    assert len(resolutions) == 0
    assert find_minimal_feedback_arc_set(adj) == []


def test_choke_point_calculation_and_seams():
    """High-fanout choke point calculation with transitive reachability and decoupling seams."""
    g = DirectedGraph()
    # TASK-1 is a bottleneck: TASK-2 and TASK-3 depend on TASK-1
    # TASK-4 depends on TASK-2, TASK-5 depends on TASK-3
    g.add_edge("TASK-2", "TASK-1")
    g.add_edge("TASK-3", "TASK-1")
    g.add_edge("TASK-4", "TASK-2")
    g.add_edge("TASK-5", "TASK-3")

    choke_points = calculate_choke_points(g)
    assert len(choke_points) >= 1
    top = choke_points[0]
    assert top.node_id == "TASK-1"
    assert top.downstream_impact == 4
    assert top.critical_path_delay == 2
    assert top.in_degree == 2  # TASK-2 and TASK-3 depend on it
    assert len(top.decoupling_seams) >= 2
    assert any("Extract shared interface / facade" in s for s in top.decoupling_seams)
    assert any("Decompose TASK-1 into modular" in s for s in top.decoupling_seams)


def test_format_helpers():
    """Text formatting helpers render clean, actionable strings."""
    res = CycleResolution(
        scc=["A", "B"],
        cycle_path=["A", "B", "A"],
        path_str="A -> B -> A",
        feedback_edge=("B", "A"),
        feedback_edges=[("B", "A"), ("A", "B")],
        remediation="Break cycle by removing dependency from B to A",
        remediations=[
            "Break cycle by removing dependency from B to A",
            "Break cycle by removing dependency from A to B",
        ],
        size=2,
    )
    lines = format_cycle_resolutions([res])
    assert any("A -> B -> A" in l for l in lines)
    assert any("Minimal Feedback Edge(s) to Resolve:" in l for l in lines)

    cp = ChokePoint(
        node_id="TASK-0001",
        downstream_impact=3,
        critical_path_delay=2,
        in_degree=2,
        out_degree=0,
        decoupling_seams=["Extract facade", "Decompose into slices"],
    )
    cp_lines = format_choke_points([cp])
    assert any("Choke Point: TASK-0001" in l for l in cp_lines)
    assert any("Extract facade" in l for l in cp_lines)


def test_cli_cycles_resolve_and_prune_chokepoints(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """CLI handler test for 'spec-ops graph cycles --resolve --prune-chokepoints'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="TestRepo")
    config = SpecOpsConfig(root_dir=repo)

    # 1. Test clean acyclic repo
    args = argparse.Namespace(
        graph_action="cycles",
        format="text",
        json=False,
        resolve=True,
        prune_chokepoints=True,
    )
    code = handle_graph_command(args, config)
    assert code == 0
    captured = capsys.readouterr()
    assert "Traceability Invariant Met: Zero dependency cycles detected." in captured.out

    # 2. Add cyclic tasks: TASK-0010 -> TASK-0011 -> TASK-0010
    backlog = repo / "docs" / "project" / "backlog" / "proposed"
    (backlog / "0010-task-10.md").write_text(
        "---\nid: '0010'\ntitle: Task 10\nstatus: Refined\ndependencies:\n  - TASK-0011\ngoverning_stories: [US-0001]\n---\n# TASK-0010\n",
        encoding="utf-8",
    )
    (backlog / "0011-task-11.md").write_text(
        "---\nid: '0011'\ntitle: Task 11\nstatus: Refined\ndependencies:\n  - TASK-0010\ngoverning_stories: [US-0001]\n---\n# TASK-0011\n",
        encoding="utf-8",
    )

    # Text mode with --resolve
    args_resolve = argparse.Namespace(
        graph_action="cycles",
        format="text",
        json=False,
        resolve=True,
        prune_chokepoints=False,
    )
    code = handle_graph_command(args_resolve, config)
    assert code == 1
    captured = capsys.readouterr()
    assert "Cyclic Backlog Dependency Detected" in captured.out
    assert "Minimal feedback edge:" in captured.out
    assert "Actionable suggestion:" in captured.out

    # JSON mode with --resolve and --prune-chokepoints
    args_json = argparse.Namespace(
        graph_action="cycles",
        format="json",
        json=True,
        resolve=True,
        prune_chokepoints=True,
    )
    code = handle_graph_command(args_json, config)
    assert code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["cyclic"] is True
    assert "resolution" in data
    assert len(data["resolution"]["all_feedback_edges"]) > 0
    assert "choke_points" in data
