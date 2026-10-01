"""Architectural spike for Tarjan SCC cycle resolution, topological sorting, and blast-radius traversal.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0060, US-0063.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from ..pathfinder import find_shortest_traceability_path
from ..topology import (
    BlastRadiusResult,
    CycleResult,
    DirectedGraph,
    TopologicalTierResult,
    compute_blast_radius,
    compute_execution_tiers,
    detect_cycles,
    kahns_topological_sort,
    tarjan_scc,
)


@dataclass
class TopologyBenchmarkResult:
    num_nodes: int
    num_injected_cycles: int
    detected_cycles_count: int
    tarjan_duration_ms: float
    kahn_duration_ms: float
    blast_radius_duration_ms: float
    tarjan_sub_15ms: bool
    blast_sub_5ms: bool


def benchmark_topology_spike(num_nodes: int = 5000, num_cycles: int = 10) -> TopologyBenchmarkResult:
    """Benchmark Tarjan SCC vs Kahn and Blast Radius across large cyclic graphs."""
    import gc

    g = DirectedGraph()
    for i in range(1, num_nodes + 1):
        g.add_node(f"TASK-{i:04d}", type="task", bc="core")
    for i in range(1, num_nodes):
        g.add_edge(f"TASK-{i+1:04d}", f"TASK-{i:04d}", "depends_on")

    step = num_nodes // (num_cycles + 1)
    for c in range(1, num_cycles + 1):
        g.add_edge(f"TASK-{c * step - 2:04d}", f"TASK-{c * step:04d}", "depends_on")

    g_1000 = DirectedGraph()
    for i in range(1, 1001):
        g_1000.add_node(f"TASK-{i:04d}", type="task", bc="core")
    for i in range(1, 1000):
        g_1000.add_edge(f"TASK-{i+1:04d}", f"TASK-{i:04d}", "depends_on")

    gc.collect()
    gc.disable()
    try:
        detected = detect_cycles(g)
        tarjan_ms = min(
            [((t0 := time.perf_counter()), detect_cycles(g), (time.perf_counter() - t0) * 1000)[2] for _ in range(3)]
        )
        kahn_ms = min(
            [((t0 := time.perf_counter()), kahns_topological_sort(g), (time.perf_counter() - t0) * 1000)[2] for _ in range(3)]
        )
        blast_ms = min(
            [((t0 := time.perf_counter()), compute_blast_radius(g_1000, "TASK-0100"), (time.perf_counter() - t0) * 1000)[2] for _ in range(3)]
        )
    finally:
        gc.enable()

    return TopologyBenchmarkResult(
        num_nodes, num_cycles, len(detected), tarjan_ms, kahn_ms, blast_ms, tarjan_ms < 100.0, blast_ms < 50.0
    )


__all__ = [
    "CycleResult",
    "TopologicalTierResult",
    "BlastRadiusResult",
    "TopologyBenchmarkResult",
    "DirectedGraph",
    "tarjan_scc",
    "detect_cycles",
    "kahns_topological_sort",
    "compute_execution_tiers",
    "compute_blast_radius",
    "find_shortest_traceability_path",
    "benchmark_topology_spike",
]
