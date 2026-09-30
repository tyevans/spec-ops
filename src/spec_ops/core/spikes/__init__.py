"""Spike prototypes for SpecOps core architecture."""

from .topology_spike import (
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

__all__ = [
    "BlastRadiusResult",
    "CycleResult",
    "DirectedGraph",
    "TopologicalTierResult",
    "TopologyBenchmarkResult",
    "benchmark_topology_spike",
    "compute_blast_radius",
    "compute_execution_tiers",
    "detect_cycles",
    "find_shortest_traceability_path",
    "kahns_topological_sort",
    "tarjan_scc",
]
