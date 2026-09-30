"""Deterministic directed graph topology, Tarjan SCC cycle resolution, and topological sorting.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0060, US-0063.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class CycleResult:
    scc: list[str]
    cycle_path: list[str]
    path_str: str
    feedback_edge: tuple[str, str]
    remediation: str
    size: int


@dataclass
class TopologicalTierResult:
    tiers: dict[int, list[str]]
    ordered_nodes: list[tuple[str, int]]
    critical_path_depth: int
    quarantined_cycles: list[CycleResult]
    quarantined_nodes: set[str]
    formatted_sequence: str


@dataclass
class BlastRadiusResult:
    entity_id: str
    downstream_nodes: set[str]
    affected_tasks: list[str]
    affected_bcs: list[str]
    affected_prs: list[str]
    total_impact: int
    impact_rating: str
    formatted_summary: str


class DirectedGraph:
    """Deterministic directed graph for dependency and traceability topology."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.adj: dict[str, list[str]] = {}
        self.rev_adj: dict[str, list[str]] = {}
        self.edge_relations: dict[tuple[str, str], str] = {}

    def add_node(self, node_id: str, **attrs: Any) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = attrs
            self.adj[node_id] = []
            self.rev_adj[node_id] = []
        else:
            self.nodes[node_id].update(attrs)

    def add_edge(self, source: str, target: str, relation: str = "depends_on") -> None:
        self.add_node(source)
        self.add_node(target)
        if target not in self.adj[source]:
            self.adj[source].append(target)
        if source not in self.rev_adj[target]:
            self.rev_adj[target].append(source)
        self.edge_relations[(source, target)] = relation

    @classmethod
    def from_project_data(cls, data: Any, harvested_git: dict[str, Any] | None = None) -> DirectedGraph:
        g = cls()
        for p in getattr(data, "personas", []):
            g.add_node(p.id, type="persona", label=p.name)
        for s in getattr(data, "stories", []):
            g.add_node(s.id, type="story", label=s.title, persona=getattr(s, "persona", ""))
        for prd in getattr(data, "prds", []):
            g.add_node(prd.id, type="prd", label=prd.title, status=getattr(prd, "status", ""))
        for t in getattr(data, "tasks", []):
            prs = list(getattr(t, "prs", []))
            g.add_node(t.canonical_id, type="task", label=t.title, status=getattr(t, "status", ""), bc=getattr(t, "target_bc", ""), prs=prs)
        for a in getattr(data, "adrs", []):
            g.add_node(a.id, type="adr", label=a.title, domain=getattr(a, "domain", ""))

        for e in getattr(data, "edges", []):
            src = getattr(e, "source_id", getattr(e, "source", None))
            tgt = getattr(e, "target_id", getattr(e, "target", None))
            if src and tgt:
                g.add_edge(src, tgt, relation=getattr(e, "relation", "relates_to"))

        # Direct story -> task implements edges if tasks have governing_stories
        for t in getattr(data, "tasks", []):
            for sid in getattr(t, "governing_stories", []):
                g.add_edge(sid, t.canonical_id, relation="implements")

        if harvested_git:
            for tid, (commits, prs) in harvested_git.items():
                for c in commits:
                    chash = getattr(c, "hash", str(c))
                    csubj = getattr(c, "subject", "")
                    g.add_node(chash, type="commit", label=csubj)
                    g.add_edge(tid, chash, relation="committed_in")

        return g


def _extract_adj(graph: DirectedGraph | dict[str, list[str]]) -> tuple[list[str], dict[str, list[str]]]:
    if isinstance(graph, DirectedGraph):
        return sorted(graph.nodes.keys()), graph.adj
    all_nodes = set(graph.keys())
    for vs in graph.values():
        all_nodes.update(vs)
    return sorted(all_nodes), {k: graph.get(k, []) for k in all_nodes}


def tarjan_scc(graph: DirectedGraph | dict[str, list[str]]) -> list[list[str]]:
    """Compute Strongly Connected Components using Tarjan's iterative O(V + E) algorithm."""
    nodes, adj = _extract_adj(graph)
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {u: False for u in nodes}
    stack: list[str] = []
    sccs: list[list[str]] = []
    idx = 0

    for root in nodes:
        if root in index:
            continue
        call_stack: list[tuple[str, int, list[str]]] = [(root, 0, adj.get(root, []))]
        index[root] = lowlink[root] = idx
        idx += 1
        stack.append(root)
        on_stack[root] = True

        while call_stack:
            u, next_idx, children = call_stack[-1]
            if next_idx < len(children):
                v = children[next_idx]
                call_stack[-1] = (u, next_idx + 1, children)
                if v not in index:
                    index[v] = lowlink[v] = idx
                    idx += 1
                    stack.append(v)
                    on_stack[v] = True
                    call_stack.append((v, 0, adj.get(v, [])))
                elif on_stack[v]:
                    lowlink[u] = min(lowlink[u], index[v])
            else:
                call_stack.pop()
                if call_stack:
                    parent = call_stack[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[u])
                if lowlink[u] == index[u]:
                    comp: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        comp.append(w)
                        if w == u:
                            break
                    comp.sort()
                    sccs.append(comp)

    sccs.sort(key=lambda c: (len(c), c[0] if c else ""))
    return sccs


def _find_cycle_path(start: str, comp_set: set[str], adj: dict[str, list[str]]) -> list[str]:
    """Find shortest elementary cycle path within an SCC starting and ending at `start`."""
    if start in adj.get(start, []):
        return [start, start]
    queue: deque[tuple[str, list[str]]] = deque()
    visited: set[str] = set()
    for nxt in sorted(adj.get(start, [])):
        if nxt in comp_set:
            if nxt == start:
                return [start, start]
            queue.append((nxt, [start, nxt]))
            visited.add(nxt)
    while queue:
        curr, path = queue.popleft()
        for nxt in sorted(adj.get(curr, [])):
            if nxt not in comp_set:
                continue
            if nxt == start:
                return path + [start]
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    return [start, start]


def detect_cycles(graph: DirectedGraph | dict[str, list[str]]) -> list[CycleResult]:
    """Detect cycles via Tarjan SCC and return deterministic path tracebacks and remediations."""
    _, adj = _extract_adj(graph)
    sccs = tarjan_scc(graph)
    results: list[CycleResult] = []
    for comp in sccs:
        is_cycle = len(comp) > 1 or (len(comp) == 1 and comp[0] in adj.get(comp[0], []))
        if is_cycle:
            path = _find_cycle_path(min(comp), set(comp), adj)
            results.append(
                CycleResult(
                    scc=comp,
                    cycle_path=path,
                    path_str=" -> ".join(path),
                    feedback_edge=(path[-2], path[-1]),
                    remediation=f"Break cycle by removing dependency from {path[-2]} to {path[-1]}",
                    size=len(comp),
                )
            )
    results.sort(key=lambda r: (r.size, r.scc[0]))
    return results


def kahns_topological_sort(graph: DirectedGraph | dict[str, list[str]]) -> tuple[list[str], bool]:
    """Kahn's algorithm (indegree-based) comparison baseline."""
    nodes, adj = _extract_adj(graph)
    indegree: dict[str, int] = {u: 0 for u in nodes}
    for children in adj.values():
        for v in children:
            if v in indegree:
                indegree[v] += 1
    queue = deque(sorted([u for u in nodes if indegree[u] == 0]))
    order: list[str] = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj.get(u, []):
            if v in indegree:
                indegree[v] -= 1
                if indegree[v] == 0:
                    queue.append(v)
    return order, len(order) == len(nodes)


def compute_execution_tiers(
    graph: DirectedGraph | dict[str, list[str]],
    entity_type: str | None = None,
) -> TopologicalTierResult:
    """Compute deterministic topological execution tiers for acyclic components, isolating cycles."""
    nodes, adj = _extract_adj(graph)
    if entity_type and isinstance(graph, DirectedGraph):
        allowed = {u for u in nodes if graph.nodes.get(u, {}).get("type") == entity_type or u.lower().startswith(f"{entity_type.lower()}-")}
        nodes = sorted(allowed)
        adj = {u: [v for v in adj.get(u, []) if v in allowed] for u in nodes}

    cycles = detect_cycles(graph)
    quarantined: set[str] = {node for c in cycles for node in c.scc if node in nodes}

    rev_adj: dict[str, list[str]] = {u: [] for u in nodes}
    for u, children in adj.items():
        for v in children:
            rev_adj.setdefault(v, []).append(u)

    spread = deque(sorted(quarantined))
    while spread:
        curr = spread.popleft()
        for dep in rev_adj.get(curr, []):
            if dep not in quarantined:
                quarantined.add(dep)
                spread.append(dep)

    acyclic = [u for u in nodes if u not in quarantined]
    indegree = {u: sum(1 for v in adj.get(u, []) if v in acyclic) for u in acyclic}
    depth: dict[str, int] = {}
    queue = deque(sorted([u for u in acyclic if indegree[u] == 0]))
    for root in queue:
        depth[root] = 0

    while queue:
        v = queue.popleft()
        for u in rev_adj.get(v, []):
            if u in indegree:
                depth[u] = max(depth.get(u, 0), depth[v] + 1)
                indegree[u] -= 1
                if indegree[u] == 0:
                    queue.append(u)

    tiers: dict[int, list[str]] = {}
    for u in acyclic:
        tiers.setdefault(depth.get(u, 0), []).append(u)
    for d in tiers:
        tiers[d].sort()

    ordered = [(u, d) for d in sorted(tiers) for u in tiers[d]]
    lines = [f"{i + 1}. {u} (depth: {d})" for i, (u, d) in enumerate(ordered)]

    return TopologicalTierResult(
        tiers=tiers,
        ordered_nodes=ordered,
        critical_path_depth=max(depth.values()) if depth else 0,
        quarantined_cycles=cycles,
        quarantined_nodes=quarantined,
        formatted_sequence="\n".join(lines),
    )


def compute_blast_radius(graph: DirectedGraph, entity_id: str) -> BlastRadiusResult:
    """Compute complete transitive downstream dependent set and impact rating in <5ms."""
    visited: set[str] = set()
    queue = deque([entity_id])
    while queue:
        curr = queue.popleft()
        for dep in graph.rev_adj.get(curr, []):
            if dep not in visited:
                visited.add(dep)
                queue.append(dep)

    tasks: list[str] = []
    bcs_set: set[str] = set()
    prs_set: set[str] = set()
    for n in visited:
        attrs = graph.nodes.get(n) or {}
        if attrs.get("type") == "task" or n.startswith("TASK-"):
            tasks.append(n)
        if bc := attrs.get("bc"):
            bcs_set.add(bc)
        for pr in attrs.get("prs", []):
            prs_set.add(pr)

    tasks.sort()
    bcs, prs = sorted(bcs_set), sorted(prs_set)
    total = len(visited)
    rating = "LOW" if total <= 4 else ("MEDIUM" if total <= 10 else "HIGH")
    tasks_disp = f"[{', '.join(tasks[:3])}{', ...' if len(tasks) > 3 else ''}]"

    summary = (
        f"Blast Radius for {entity_id}:\n"
        f"- {len(tasks)} governing tasks: {tasks_disp}\n"
        f"- {len(bcs)} affected bounded contexts: [{', '.join(bcs)}]\n"
        f"- {len(prs)} active pull requests: [{', '.join(prs)}]\n"
        f"Total Downstream Impact: {rating} ({total} nodes affected)"
    )
    return BlastRadiusResult(entity_id, visited, tasks, bcs, prs, total, rating, summary)
