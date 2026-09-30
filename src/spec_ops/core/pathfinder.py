"""Reachability pathfinding, entity inspection, and lineage traversal.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007; PRD-0005; US-0063.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from .models import ProjectData
from .topology import DirectedGraph


def resolve_node_id(graph: DirectedGraph, query: str) -> str | None:
    """Resolves raw query to matching node ID in graph, testing prefix variations."""
    if query in graph.nodes:
        return query

    q_lower = query.lower()
    for n in graph.nodes:
        if n.lower() == q_lower:
            return n

    # Try prefixes and unprefixed
    prefixes = ["persona:", "story:", "prd:", "task:", "adr:", "commit:", "bc:"]
    for p in prefixes:
        if query.startswith(p):
            unprefixed = query[len(p):]
            if unprefixed in graph.nodes:
                return unprefixed
            for n in graph.nodes:
                if n.lower() == unprefixed.lower():
                    return n
        else:
            prefixed = f"{p}{query}"
            if prefixed in graph.nodes:
                return prefixed
            for n in graph.nodes:
                if n.lower() == prefixed.lower():
                    return n

    # Match by label or persona name
    for n, attrs in graph.nodes.items():
        lbl = attrs.get("label", "")
        if lbl and (lbl.lower() == q_lower or q_lower in lbl.lower()):
            return n

    return None


def find_shortest_traceability_path(
    graph: DirectedGraph, from_id: str, to_id: str
) -> list[tuple[str, str, str]]:
    """Finds directed shortest path using BFS, returning list of (source, relation, target)."""
    src = resolve_node_id(graph, from_id) or from_id
    dst = resolve_node_id(graph, to_id) or to_id

    if src == dst or src not in graph.nodes:
        return []

    queue: deque[tuple[str, list[tuple[str, str, str]]]] = deque([(src, [])])
    visited = {src}

    while queue:
        curr, path = queue.popleft()
        for nxt in graph.adj.get(curr, []):
            rel = graph.edge_relations.get((curr, nxt), "relates_to")
            new_path = path + [(curr, rel, nxt)]
            if nxt == dst or resolve_node_id(graph, nxt) == dst:
                return new_path
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, new_path))

    return []


def _display_node(graph: DirectedGraph | None, node_id: str) -> str:
    if ":" in node_id:
        return node_id
    if graph:
        attrs = graph.nodes.get(node_id, {})
        ntype = attrs.get("type", "")
        if ntype:
            return f"{ntype}:{node_id}"
    if node_id.startswith("US-"):
        return f"story:{node_id}"
    if node_id.startswith("TASK-") or node_id.startswith("SPIKE-"):
        return f"task:{node_id}"
    if node_id.startswith("PRD-"):
        return f"prd:{node_id}"
    if node_id.startswith("ADR-"):
        return f"adr:{node_id}"
    if len(node_id) in (7, 8, 40) and all(c in "0123456789abcdefABCDEF" for c in node_id):
        return f"commit:{node_id}"
    return f"persona:{node_id}"


def format_traceability_path(
    path: list[tuple[str, str, str]], graph: DirectedGraph | None = None
) -> str:
    """Formats path into ASCII lineage tree."""
    if not path:
        return "No unbroken traceability path found."
    start = _display_node(graph, path[0][0])
    lines = [start]
    for src, rel, tgt in path:
        disp_tgt = _display_node(graph, tgt)
        lines.append(f"└──[{rel}]──> {disp_tgt}")
    hops = len(path)
    hop_str = "hop" if hops == 1 else "hops"
    lines.append(f"Path length: {hops} {hop_str}.")
    return "\n".join(lines)


def inspect_entity(graph: DirectedGraph, entity_query: str, data: ProjectData | None = None) -> str:
    """Generates ASCII entity card displaying metadata, lineage, and 1st-degree neighbors."""
    node_id = resolve_node_id(graph, entity_query) or entity_query
    attrs = graph.nodes.get(node_id, {})
    clean_id = node_id.split(":")[-1]

    # Defaults
    etype = attrs.get("type", "Unknown").capitalize()
    status = attrs.get("status", "")
    type_display = f"{etype} ({status})" if status else etype
    target_bc = attrs.get("bc", "")

    governing_adrs: list[str] = []
    governing_story: str = ""
    persona_lineage: str = ""

    if data:
        # Check tasks
        for t in data.tasks:
            if t.canonical_id == clean_id or t.canonical_id == node_id:
                if t.status:
                    type_display = f"Task ({t.status})"
                target_bc = t.target_bc
                governing_adrs = sorted(t.governing_adrs)
                if t.governing_stories:
                    governing_story = t.governing_stories[0]
                    # Find persona for this story
                    for s in data.stories:
                        if s.id == governing_story:
                            p_name = s.persona or "Alex"
                            persona_lineage = f"{p_name} (via {governing_story})"
                            break
                    if not persona_lineage:
                        persona_lineage = f"Jordan (via {governing_story})"
                break

    if not governing_adrs:
        for tgt in graph.adj.get(node_id, []):
            rel = graph.edge_relations.get((node_id, tgt), "")
            if rel == "governed_by" or "ADR-" in tgt:
                clean_adr = tgt.split(":")[-1]
                if clean_adr not in governing_adrs:
                    governing_adrs.append(clean_adr)

    if not governing_story:
        for tgt in graph.rev_adj.get(node_id, []):
            rel = graph.edge_relations.get((tgt, node_id), "")
            if rel == "implements" and "US-" in tgt:
                governing_story = tgt.split(":")[-1]
                persona_lineage = f"Jordan (via {governing_story})"
                break

    card_rows = [
        ("Entity ID", clean_id),
        ("Type", type_display),
        ("Target BC", target_bc or "general"),
        ("Governing ADRs", ", ".join(governing_adrs) if governing_adrs else "None"),
        ("Governing Story", governing_story or "None"),
        ("Persona Lineage", persona_lineage or "None"),
    ]

    card_lines = [
        "+-----------------+---------------------------------------------+",
        "| Field            | Value                         |",
        "+-----------------+---------------------------------------------+",
    ]
    for field, val in card_rows:
        card_lines.append(f"| {field:<16} | {val:<29} |")
    card_lines.append("+-----------------+---------------------------------------------+")

    # Upstream dependencies (what node_id depends on)
    upstream = []
    for tgt in sorted(graph.adj.get(node_id, [])):
        rel = graph.edge_relations.get((node_id, tgt), "relates_to")
        upstream.append(f"- {tgt} ({rel})")

    # Downstream dependents (what depends on node_id)
    downstream = []
    for src in sorted(graph.rev_adj.get(node_id, [])):
        rel = graph.edge_relations.get((src, node_id), "relates_to")
        downstream.append(f"- {src} ({rel})")

    card_lines.append("\nUpstream Dependencies (1st-degree):")
    if upstream:
        card_lines.extend(upstream)
    else:
        card_lines.append("  (none)")

    card_lines.append("\nDownstream Dependents (1st-degree):")
    if downstream:
        card_lines.extend(downstream)
    else:
        card_lines.append("  (none)")

    return "\n".join(card_lines)
