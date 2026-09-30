"""CLI command handler for relational graph operations, cycle detection, pathfinding, and audits."""

from __future__ import annotations

import argparse
import json
import sys

from ..config.models import SpecOpsConfig
from ..core.cache import RelationalGraphCacheEngine
from ..core.git_metadata import GitMetadataHarvester
from ..core.graph_audit import audit_bottlenecks, audit_graph_all, audit_traceability
from ..core.pathfinder import find_shortest_traceability_path, format_traceability_path, inspect_entity
from ..core.topology import (
    DirectedGraph,
    compute_blast_radius,
    compute_execution_tiers,
    detect_cycles,
)


def _load_graph(config: SpecOpsConfig) -> tuple[Any, DirectedGraph]:
    engine = RelationalGraphCacheEngine(config.root_dir)
    data, _ = engine.compile_graph(force_cold=False)
    harvester = GitMetadataHarvester(config.root_dir)
    git_commits = harvester.harvest()
    graph = DirectedGraph.from_project_data(data, harvested_git=git_commits)
    return data, graph


def handle_graph_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops graph' subcommands."""
    action = getattr(args, "graph_action", None)

    if action == "compile":
        incremental = getattr(args, "incremental", False)
        force_cold = getattr(args, "force_cold", False) or (not incremental)
        json_output = getattr(args, "json", False)

        engine = RelationalGraphCacheEngine(config.root_dir)
        p_data, stats = engine.compile_graph(force_cold=force_cold)

        if json_output:
            out = {
                "cold": stats.cold,
                "total_indexed": stats.total_indexed,
                "invalidated": stats.invalidated,
                "cache_hits": stats.cache_hits,
                "cache_misses": 0 if not stats.cold and stats.invalidated == 0 else (stats.invalidated if not stats.cold else stats.total_indexed),
                "duration_ms": round(stats.duration_ms, 2),
                "entities": {
                    "tasks": len(p_data.tasks),
                    "stories": len(p_data.stories),
                    "prds": len(p_data.prds),
                    "adrs": len(p_data.adrs),
                    "personas": len(p_data.personas),
                },
                "edges_count": len(p_data.edges),
            }
            print(json.dumps(out, indent=2))
            return 0

        if stats.cold:
            print(f"Graph compiled in cold state: {stats.total_indexed} entities indexed, cache written")
        else:
            files_word = "file" if stats.invalidated == 1 else "files"
            misses_str = "zero cache misses" if stats.invalidated == 0 else f"{stats.invalidated} cache misses"
            print(f"Incremental graph sync: {stats.invalidated} {files_word} invalidated, {stats.cache_hits} cache hits ({misses_str})")
        return 0

    if action == "cycles":
        fmt = getattr(args, "format", "text")
        is_json = fmt == "json" or getattr(args, "json", False)
        data, graph = _load_graph(config)
        cycles = detect_cycles(graph)

        if is_json:
            out = {
                "cyclic": len(cycles) > 0,
                "cycle_count": len(cycles),
                "cycles": [
                    {
                        "scc": c.scc,
                        "cycle_path": c.cycle_path,
                        "path_str": c.path_str,
                        "feedback_edge": list(c.feedback_edge),
                        "remediation": c.remediation,
                        "size": c.size,
                    }
                    for c in cycles
                ],
            }
            print(json.dumps(out, indent=2))
            return 1 if cycles else 0

        if not cycles:
            print("Traceability Invariant Met: Zero dependency cycles detected.")
            return 0

        for c in cycles:
            print(f"Cyclic Backlog Dependency Detected: Strongly Connected Component of size {c.size}")
            print(f"Directed cycle path: {c.path_str}")
            print(f"Actionable suggestion: {c.remediation}.")
        return 1

    if action in ("sort", "order"):
        etype = getattr(args, "type", None)
        data, graph = _load_graph(config)
        res = compute_execution_tiers(graph, entity_type=etype)

        if res.quarantined_cycles:
            c = res.quarantined_cycles[0]
            print(f"Cyclic Backlog Dependency Detected: Strongly Connected Component of size {c.size}")
            print(f"Directed cycle path: {c.path_str}")
            print(f"Actionable suggestion: {c.remediation}.")
            return 1

        print("Topological Execution Order:")
        print(res.formatted_sequence)
        print(f"Identifies the critical path depth as {res.critical_path_depth}.")
        return 0

    if action == "path":
        src = getattr(args, "from_node", None) or getattr(args, "from", None)
        dst = getattr(args, "to_node", None) or getattr(args, "to", None)
        if not src or not dst:
            print("Error: Both --from and --to nodes are required.", file=sys.stderr)
            return 1

        data, graph = _load_graph(config)
        path = find_shortest_traceability_path(graph, src, dst)
        if not path:
            print(f"No unbroken traceability path found between '{src}' and '{dst}'.", file=sys.stderr)
            return 1

        print(format_traceability_path(path, graph=graph))
        return 0

    if action == "blast-radius":
        target = getattr(args, "entity", None)
        if not target:
            print("Error: Entity identifier required for blast-radius calculation.", file=sys.stderr)
            return 1

        data, graph = _load_graph(config)
        blast = compute_blast_radius(graph, target)
        print(blast.formatted_summary)
        return 0

    if action == "inspect":
        target = getattr(args, "entity", None)
        if not target:
            print("Error: Entity identifier required for graph inspection.", file=sys.stderr)
            return 1

        data, graph = _load_graph(config)
        print(inspect_entity(graph, target, data=data))
        return 0

    if action == "audit":
        data, _ = _load_graph(config)
        code, msgs = audit_graph_all(data)
        for msg in msgs:
            print(msg)
        return code

    print(f"❌ Unknown graph action: {action}", file=sys.stderr)
    return 1


def handle_trace_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops trace' commands."""
    data, _ = _load_graph(config)
    code, msgs = audit_traceability(data)
    for msg in msgs:
        print(msg)
    return code


def handle_backlog_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops backlog' commands."""
    action = getattr(args, "backlog_action", None)
    if action == "bottlenecks":
        data, _ = _load_graph(config)
        forecast = getattr(args, "forecast", False)
        code, msgs = audit_bottlenecks(data, forecast=forecast)
        for msg in msgs:
            print(msg)
        return code

    print(f"❌ Unknown backlog action: {action}", file=sys.stderr)
    return 1
