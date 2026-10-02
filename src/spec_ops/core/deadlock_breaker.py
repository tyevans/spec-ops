"""Multi-Agent Task Dependency Graph Deadlock Resolver and Cycle Auto-Break Engine."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any

import yaml


@dataclass
class DeadlockCycle:
    nodes: list[str]
    cycle_path: list[str]
    path_str: str
    recommended_cut: tuple[str, str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "cycle_path": list(self.cycle_path),
            "path_str": self.path_str,
            "recommended_cut": [self.recommended_cut[0], self.recommended_cut[1]],
            "rationale": self.rationale,
        }


@dataclass
class DeadlockReport:
    is_acyclic: bool
    cycles: list[DeadlockCycle] = field(default_factory=list)
    recommended_cuts: list[tuple[str, str]] = field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_acyclic": self.is_acyclic,
            "cycle_count": len(self.cycles),
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "recommended_cuts": [[u, v] for u, v in self.recommended_cuts],
            "cycles": [c.to_dict() for c in self.cycles],
        }

    def format_text(self) -> str:
        lines: list[str] = [
            "=== SpecOps Task Dependency Deadlock Analysis ===",
            f"Nodes Analyzed: {self.total_nodes}",
            f"Dependencies:   {self.total_edges}",
            "",
        ]
        if self.is_acyclic:
            lines.append("✅ Traceability Invariant Met: Zero dependency deadlocks or circular cycles detected.")
            lines.append("   The task dependency graph is a valid Directed Acyclic Graph (DAG).")
        else:
            lines.append(f"❌ Dependency Deadlocks Detected: {len(self.cycles)} circular cycle(s) found.")
            lines.append("")
            for idx, c in enumerate(self.cycles, 1):
                lines.append(f"  Cycle {idx}: {c.path_str}")
                lines.append(f"    Recommended Break: Remove dependency edge '{c.recommended_cut[0]} -> {c.recommended_cut[1]}'")
                lines.append(f"    Rationale:         {c.rationale}")

            lines.append("")
            lines.append(f"Recommended Minimal Cut Set ({len(self.recommended_cuts)} edge(s)):")
            for u, v in self.recommended_cuts:
                lines.append(f"  • Prune '{u}' -> '{v}'")

        return "\n".join(lines)


def tarjan_scc(graph: dict[str, list[str]]) -> list[list[str]]:
    """Partitions directed graph into strongly connected components using Tarjan's algorithm."""
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    sccs: list[list[str]] = []

    # Deterministic node iteration
    sorted_nodes = sorted(graph.keys())

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in sorted(graph.get(v, [])):
            if w not in graph:
                continue
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            sccs.append(sorted(scc))

    for node in sorted_nodes:
        if node not in indices:
            strongconnect(node)

    return sccs


def find_elementary_cycle(scc_nodes: list[str], graph: dict[str, list[str]]) -> list[str]:
    """Finds a simple directed cycle within an SCC starting at the lexicographically lowest node."""
    scc_set = set(scc_nodes)
    start = sorted(scc_nodes)[0]

    # Check for self-loop
    if start in graph.get(start, []):
        return [start, start]

    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    visited: set[str] = {start}

    while queue:
        curr, path = queue.popleft()
        for neighbor in sorted(graph.get(curr, [])):
            if neighbor not in scc_set:
                continue
            if neighbor == start and len(path) > 1:
                return path + [start]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    # Fallback if BFS from start didn't complete
    for n in scc_nodes:
        for neigh in graph.get(n, []):
            if neigh in scc_set:
                return [n, neigh, n]

    return list(scc_nodes)


def compute_minimum_feedback_arc_set(graph: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Heuristic computation of minimal edge removal set that breaks all cycles to restore a DAG."""
    # Work on a copy of the graph
    adj: dict[str, list[str]] = {u: list(neighbors) for u, neighbors in graph.items()}
    feedback_arcs: list[tuple[str, str]] = []

    while True:
        sccs = tarjan_scc(adj)
        cyclic_sccs = [scc for scc in sccs if len(scc) > 1 or (len(scc) == 1 and scc[0] in adj.get(scc[0], []))]
        if not cyclic_sccs:
            break

        # For the first cyclic SCC, find a cycle
        scc = cyclic_sccs[0]
        cycle = find_elementary_cycle(scc, adj)

        # Candidate edge to cut: choose edge with highest out-degree in cycle or lexicographical tie-break
        best_edge: tuple[str, str] | None = None
        for i in range(len(cycle) - 1):
            edge = (cycle[i], cycle[i + 1])
            if best_edge is None or len(adj.get(edge[0], [])) > len(adj.get(best_edge[0], [])):
                best_edge = edge

        if not best_edge:
            break

        feedback_arcs.append(best_edge)
        adj[best_edge[0]] = [v for v in adj[best_edge[0]] if v != best_edge[1]]

    return feedback_arcs


class TaskDeadlockResolver:
    """Detects and resolves circular task dependency deadlocks."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path.cwd()

    def build_task_graph(self) -> dict[str, list[str]]:
        """Constructs task dependency digraph from backlog markdown frontmatter."""
        graph: dict[str, list[str]] = {}
        backlog_dir = self.root_dir / "docs" / "project" / "backlog"
        if not backlog_dir.is_dir():
            return graph

        for path in backlog_dir.glob("**/*.md"):
            if path.name in ("PRIORITY.md", "ROADMAP.md", "INDEX.md"):
                continue
            try:
                content = path.read_text(encoding="utf-8")
                fm_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
                if not fm_match:
                    continue
                data = yaml.safe_load(fm_match.group(1)) or {}
                raw_id = str(data.get("id", "")).strip()
                if not raw_id:
                    continue
                task_id = raw_id if raw_id.startswith("TASK-") else f"TASK-{raw_id.zfill(4)}"

                deps_raw = data.get("dependencies", []) or []
                deps: list[str] = []
                for d in deps_raw:
                    d_clean = str(d).strip()
                    if d_clean:
                        dep_id = d_clean if d_clean.startswith("TASK-") else f"TASK-{d_clean.zfill(4)}"
                        deps.append(dep_id)

                graph[task_id] = sorted(deps)
            except Exception:
                continue

        return graph

    def analyze(self, graph_override: dict[str, list[str]] | None = None) -> DeadlockReport:
        """Analyzes task dependencies, extracts cycles, and proposes minimal cut set."""
        graph = graph_override if graph_override is not None else self.build_task_graph()
        total_nodes = len(graph)
        total_edges = sum(len(deps) for deps in graph.values())

        sccs = tarjan_scc(graph)
        cyclic_sccs = [scc for scc in sccs if len(scc) > 1 or (len(scc) == 1 and scc[0] in graph.get(scc[0], []))]

        if not cyclic_sccs:
            return DeadlockReport(
                is_acyclic=True,
                cycles=[],
                recommended_cuts=[],
                total_nodes=total_nodes,
                total_edges=total_edges,
            )

        cycles: list[DeadlockCycle] = []
        for scc in cyclic_sccs:
            cycle_path = find_elementary_cycle(scc, graph)
            path_str = " -> ".join(cycle_path)
            rec_cut = (cycle_path[0], cycle_path[1]) if len(cycle_path) > 1 else (cycle_path[0], cycle_path[0])
            rationale = f"Breaking '{rec_cut[0]}' -> '{rec_cut[1]}' resolves circular wait in component {scc}."
            cycles.append(
                DeadlockCycle(
                    nodes=scc,
                    cycle_path=cycle_path,
                    path_str=path_str,
                    recommended_cut=rec_cut,
                    rationale=rationale,
                )
            )

        recommended_cuts = compute_minimum_feedback_arc_set(graph)

        return DeadlockReport(
            is_acyclic=False,
            cycles=cycles,
            recommended_cuts=recommended_cuts,
            total_nodes=total_nodes,
            total_edges=total_edges,
        )

    def resolve_deadlocks(self, report: DeadlockReport, dry_run: bool = True) -> list[str]:
        """Prunes cyclic dependency edges from task frontmatter files on disk."""
        actions: list[str] = []
        if report.is_acyclic or not report.recommended_cuts:
            return ["No cyclic dependencies to resolve."]

        backlog_dir = self.root_dir / "docs" / "project" / "backlog"
        cuts_by_source: dict[str, set[str]] = {}
        for src, target in report.recommended_cuts:
            cuts_by_source.setdefault(src, set()).add(target)

        for path in backlog_dir.glob("**/*.md"):
            if path.name in ("PRIORITY.md", "ROADMAP.md", "INDEX.md"):
                continue
            try:
                content = path.read_text(encoding="utf-8")
                fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
                if not fm_match:
                    continue
                data = yaml.safe_load(fm_match.group(1)) or {}
                raw_id = str(data.get("id", "")).strip()
                task_id = raw_id if raw_id.startswith("TASK-") else f"TASK-{raw_id.zfill(4)}"

                if task_id in cuts_by_source:
                    targets_to_prune = cuts_by_source[task_id]
                    existing_deps = data.get("dependencies", []) or []
                    new_deps = [d for d in existing_deps if d not in targets_to_prune and f"TASK-{str(d).zfill(4)}" not in targets_to_prune]

                    if len(new_deps) != len(existing_deps):
                        msg = f"Pruned edge(s) from {task_id}: {targets_to_prune}"
                        actions.append(msg)
                        if not dry_run:
                            data["dependencies"] = new_deps
                            new_fm = yaml.dump(data, sort_keys=False).strip()
                            new_content = f"---\n{new_fm}\n---\n{fm_match.group(2)}"
                            path.write_text(new_content, encoding="utf-8")
            except Exception:
                continue

        return actions
