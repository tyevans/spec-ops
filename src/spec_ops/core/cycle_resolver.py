"""Deterministic DAG cycle resolution and choke point pruning engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0017; PRD-0005; US-0060.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .topology import DirectedGraph, _extract_adj, _find_cycle_path, tarjan_scc


@dataclass
class CycleResolution:
    """Cycle resolution outcome for a strongly connected component."""

    scc: list[str]
    cycle_path: list[str]
    path_str: str
    feedback_edge: tuple[str, str]
    feedback_edges: list[tuple[str, str]]
    remediation: str
    remediations: list[str]
    size: int


@dataclass
class ChokePoint:
    """Choke point bottleneck node and decoupling recommendations."""

    node_id: str
    downstream_impact: int
    critical_path_delay: int
    in_degree: int
    out_degree: int
    decoupling_seams: list[str] = field(default_factory=list)


def suggest_decoupling_seams(
    node_id: str,
    downstream_impact: int,
    critical_path_delay: int,
    in_degree: int,
    out_degree: int,
    is_cyclic: bool = False,
) -> list[str]:
    """Generates actionable architectural decoupling seams for a choke point."""
    seams: list[str] = []
    if is_cyclic:
        seams.append(
            f"Sever cyclic feedback dependency involving {node_id} to unblock transitive execution flow."
        )
    if in_degree > 1:
        seams.append(
            f"Extract shared interface / facade contract for {node_id} to unblock {in_degree} direct dependents in parallel."
        )
    if downstream_impact >= 3 or critical_path_delay >= 2:
        seams.append(
            f"Decompose {node_id} into modular vertical slices to reduce downstream serialization delay ({downstream_impact} nodes blocked, delay {critical_path_delay})."
        )
    if out_degree > 2:
        seams.append(
            f"Prune outbound dependencies of {node_id} via domain event pub/sub or asynchronous decoupling."
        )
    if not seams:
        seams.append(
            f"Isolate {node_id} behind an abstraction boundary or decouple direct prerequisite links."
        )
    return seams


def find_minimal_feedback_arc_set(
    graph: DirectedGraph | dict[str, list[str]],
    comp: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Deterministically identifies a minimal feedback arc set to break all cycles."""
    nodes, full_adj = _extract_adj(graph)
    if comp is not None:
        comp_set = set(comp)
        active_nodes = sorted(comp_set)
        adj: dict[str, list[str]] = {
            u: [v for v in full_adj.get(u, []) if v in comp_set] for u in active_nodes
        }
    else:
        active_nodes = nodes
        adj = {u: list(vs) for u, vs in full_adj.items()}

    sccs = [c for c in tarjan_scc(adj) if len(c) > 1 or (len(c) == 1 and c[0] in adj.get(c[0], []))]
    if not sccs:
        return []

    removed_edges: list[tuple[str, str]] = []

    while True:
        cyclic_sccs = [
            c for c in tarjan_scc(adj) if len(c) > 1 or (len(c) == 1 and c[0] in adj.get(c[0], []))
        ]
        if not cyclic_sccs:
            break

        cyclic_sccs.sort(key=lambda c: (len(c), c[0]))
        curr_scc = cyclic_sccs[0]
        scc_set = set(curr_scc)

        start_node = min(curr_scc)
        path = _find_cycle_path(start_node, scc_set, adj)

        if len(path) >= 2:
            src, tgt = path[-2], path[-1]
        else:
            src, tgt = start_node, start_node

        if tgt in adj.get(src, []):
            adj[src].remove(tgt)
            if (src, tgt) not in removed_edges:
                removed_edges.append((src, tgt))
        else:
            found = False
            for u in sorted(curr_scc):
                for v in sorted(adj.get(u, [])):
                    if v in scc_set:
                        adj[u].remove(v)
                        if (u, v) not in removed_edges:
                            removed_edges.append((u, v))
                        found = True
                        break
                if found:
                    break
            if not found:
                break

    # Minimality pass: test each removed edge; prune redundant ones
    current_removed = set(removed_edges)
    for edge in list(removed_edges):
        test_removed = current_removed - {edge}
        test_adj: dict[str, list[str]] = {}
        for u in active_nodes:
            targets = full_adj.get(u, [])
            if comp is not None:
                targets = [v for v in targets if v in comp_set]
            test_adj[u] = [v for v in targets if (u, v) not in test_removed]

        test_sccs = [
            c for c in tarjan_scc(test_adj) if len(c) > 1 or (len(c) == 1 and c[0] in test_adj.get(c[0], []))
        ]
        if not test_sccs:
            current_removed = test_removed

    return sorted(current_removed)


def resolve_cyclic_components(
    graph: DirectedGraph | dict[str, list[str]],
) -> list[CycleResolution]:
    """Resolves all cyclic SCCs, returning minimal feedback edges and remediations."""
    _, full_adj = _extract_adj(graph)
    sccs = tarjan_scc(graph)
    resolutions: list[CycleResolution] = []

    for comp in sccs:
        is_cycle = len(comp) > 1 or (len(comp) == 1 and comp[0] in full_adj.get(comp[0], []))
        if not is_cycle:
            continue

        comp_set = set(comp)
        path = _find_cycle_path(min(comp), comp_set, full_adj)
        primary_edge = (path[-2], path[-1]) if len(path) >= 2 else (comp[0], comp[0])

        feedback_edges = find_minimal_feedback_arc_set(graph, comp=comp)
        if primary_edge in feedback_edges:
            feedback_edges = [primary_edge] + [e for e in feedback_edges if e != primary_edge]
        elif not feedback_edges:
            feedback_edges = [primary_edge]

        remediations = [
            f"Break cycle by removing dependency from {src} to {tgt}"
            for src, tgt in feedback_edges
        ]

        resolutions.append(
            CycleResolution(
                scc=comp,
                cycle_path=path,
                path_str=" -> ".join(path),
                feedback_edge=primary_edge,
                feedback_edges=feedback_edges,
                remediation=remediations[0],
                remediations=remediations,
                size=len(comp),
            )
        )

    resolutions.sort(key=lambda r: (r.size, r.scc[0]))
    return resolutions


def calculate_choke_points(
    graph: DirectedGraph | dict[str, list[str]],
    top_n: int | None = None,
    min_impact: int = 1,
) -> list[ChokePoint]:
    """Calculates transitive bottleneck nodes (choke points) and generates decoupling seams."""
    nodes, adj = _extract_adj(graph)
    rev_adj: dict[str, list[str]] = {u: [] for u in nodes}
    for u, targets in adj.items():
        for v in targets:
            if v in rev_adj:
                rev_adj[v].append(u)
            else:
                rev_adj[v] = [u]

    sccs = tarjan_scc(adj)
    cyclic_nodes: set[str] = set()
    for comp in sccs:
        if len(comp) > 1 or (len(comp) == 1 and comp[0] in adj.get(comp[0], [])):
            cyclic_nodes.update(comp)

    choke_points: list[ChokePoint] = []
    for u in nodes:
        visited: set[str] = set()
        depth_map: dict[str, int] = {u: 0}
        queue = deque([u])
        while queue:
            curr = queue.popleft()
            d = depth_map[curr]
            for dep in rev_adj.get(curr, []):
                if dep not in visited:
                    visited.add(dep)
                    depth_map[dep] = d + 1
                    queue.append(dep)

        downstream_impact = len(visited)
        if downstream_impact < min_impact:
            continue

        critical_path_delay = max(depth_map.values()) if visited else 0
        in_deg = len(rev_adj.get(u, []))
        out_deg = len(adj.get(u, []))
        is_cyclic = u in cyclic_nodes

        seams = suggest_decoupling_seams(
            node_id=u,
            downstream_impact=downstream_impact,
            critical_path_delay=critical_path_delay,
            in_degree=in_deg,
            out_degree=out_deg,
            is_cyclic=is_cyclic,
        )

        choke_points.append(
            ChokePoint(
                node_id=u,
                downstream_impact=downstream_impact,
                critical_path_delay=critical_path_delay,
                in_degree=in_deg,
                out_degree=out_deg,
                decoupling_seams=seams,
            )
        )

    choke_points.sort(key=lambda cp: (-cp.downstream_impact, -cp.critical_path_delay, cp.node_id))
    if top_n is not None:
        return choke_points[:top_n]
    return choke_points


def format_cycle_resolutions(resolutions: list[CycleResolution]) -> list[str]:
    """Formats cycle resolutions into human-readable CLI strings."""
    lines: list[str] = []
    for c in resolutions:
        lines.append(f"Cyclic Backlog Dependency Detected: Strongly Connected Component of size {c.size}")
        lines.append(f"Directed cycle path: {c.path_str}")
        lines.append(f"Actionable suggestion: {c.remediation}.")
        if len(c.feedback_edges) > 1:
            lines.append("Minimal Feedback Edge(s) to Resolve:")
            for edge in c.feedback_edges:
                lines.append(f"  - Remove dependency from {edge[0]} to {edge[1]}")
    return lines


def format_choke_points(choke_points: list[ChokePoint]) -> list[str]:
    """Formats choke points into human-readable CLI strings."""
    if not choke_points:
        return ["No high-fanout choke points detected."]
    lines: list[str] = ["Choke Point Bottleneck Analysis & Decoupling Seams:"]
    for cp in choke_points:
        lines.append(
            f"- Choke Point: {cp.node_id} (downstream impact: {cp.downstream_impact} nodes, critical path delay: {cp.critical_path_delay})"
        )
        lines.append("  Decoupling Seams:")
        for seam in cp.decoupling_seams:
            lines.append(f"  * {seam}")
    return lines
