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
from ..core.cycle_resolver import (
    calculate_choke_points,
    format_choke_points,
    resolve_cyclic_components,
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
        resolve = getattr(args, "resolve", False)
        prune_chokepoints = getattr(args, "prune_chokepoints", False)
        check_edge = getattr(args, "check_edge", None)
        use_cache = getattr(args, "cache", False)

        if check_edge:
            src, tgt = check_edge
            from ..core.dag_cache import DAGCacheEngine, can_add_dependency

            engine = DAGCacheEngine(config.root_dir)
            cache_payload = engine.build_cache(force=not use_cache)
            res = can_add_dependency(cache_payload, src, tgt)

            if is_json:
                out = {
                    "allowed": res.allowed,
                    "cycle_path": res.cycle_path,
                    "path_str": res.path_str,
                    "error": res.error,
                    "duration_ms": round(res.duration_ms, 3),
                }
                print(json.dumps(out, indent=2))
                return 0 if res.allowed else 1

            if res.allowed:
                print(f"Zero dependency cycles detected: adding edge '{src} -> {tgt}' preserves DAG acyclicity.")
                return 0
            else:
                print(f"Cyclic dependency detected: {res.path_str}")
                print(f"Actionable suggestion: Break cycle by removing dependency from {src} to {tgt}.")
                return 1

        data, graph = _load_graph(config)
        cycles = detect_cycles(graph)
        resolutions = resolve_cyclic_components(graph) if resolve else []
        choke_points = calculate_choke_points(graph) if prune_chokepoints else []

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
            if resolve:
                out["resolution"] = {
                    "all_feedback_edges": [
                        list(e) for r in resolutions for e in r.feedback_edges
                    ],
                    "all_remediations": [
                        rem for r in resolutions for rem in r.remediations
                    ],
                    "resolved_acyclic": True,
                    "resolutions": [
                        {
                            "scc": r.scc,
                            "cycle_path": r.cycle_path,
                            "feedback_edges": [list(e) for e in r.feedback_edges],
                            "remediations": r.remediations,
                        }
                        for r in resolutions
                    ],
                }
            if prune_chokepoints:
                out["choke_points"] = [
                    {
                        "node_id": cp.node_id,
                        "downstream_impact": cp.downstream_impact,
                        "critical_path_delay": cp.critical_path_delay,
                        "in_degree": cp.in_degree,
                        "out_degree": cp.out_degree,
                        "decoupling_seams": cp.decoupling_seams,
                    }
                    for cp in choke_points
                ]
            print(json.dumps(out, indent=2))
            return 1 if cycles else 0

        if not cycles:
            print("Traceability Invariant Met: Zero dependency cycles detected.")
            if prune_chokepoints:
                for line in format_choke_points(choke_points):
                    print(line)
            return 0

        if resolve:
            for r in resolutions:
                print(f"Cyclic Backlog Dependency Detected: Strongly Connected Component of size {r.size}")
                print(f"Directed cycle path: {r.path_str}")
                print(f"Minimal feedback edge: ({r.feedback_edge[0]}, {r.feedback_edge[1]})")
                print(f"Actionable suggestion: {r.remediation}.")
                if len(r.feedback_edges) > 1:
                    print("Additional feedback edges to break SCC:")
                    for edge in r.feedback_edges[1:]:
                        print(f"  - ({edge[0]}, {edge[1]}): Break cycle by removing dependency from {edge[0]} to {edge[1]}")
        else:
            for c in cycles:
                print(f"Cyclic Backlog Dependency Detected: Strongly Connected Component of size {c.size}")
                print(f"Directed cycle path: {c.path_str}")
                print(f"Actionable suggestion: {c.remediation}.")

        if prune_chokepoints:
            for line in format_choke_points(choke_points):
                print(line)

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

    if action == "reach":
        src = getattr(args, "source", None)
        dst = getattr(args, "target", None)
        if not src or not dst:
            print("Error: Both --source and --target are required.", file=sys.stderr)
            return 1

        is_json = getattr(args, "json", False)
        from ..graph.redstring_bridge import RedstringBridge

        bridge = RedstringBridge(config.root_dir)
        bridge.compile_sync()
        reachable, path = bridge.reach_sync(src, dst)

        if is_json:
            print(json.dumps({
                "source": src,
                "target": dst,
                "reachable": reachable,
                "path": path,
            }, indent=2))
            return 0 if reachable else 1

        if reachable:
            print(f"Traceability Reachable: '{src}' reaches '{dst}' via {' -> '.join(path)}")
            return 0
        else:
            print(f"Traceability Unreachable: No path found between '{src}' and '{dst}'.")
            return 1

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

    if action == "watch":
        return handle_graph_watch_command(args, config)

    print(f"❌ Unknown graph action: {action}", file=sys.stderr)
    return 1


def handle_graph_watch_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops graph watch' command using incremental graph invalidator."""
    from pathlib import Path
    from ..graph.workspace_watcher import WorkspaceGraphWatcher

    target_dir = Path(getattr(args, "dir", "."))
    if str(target_dir) == ".":
        target_dir = config.root_dir
    else:
        target_dir = target_dir.resolve()

    interval = getattr(args, "interval", 0.5)
    debounce_ms = getattr(args, "debounce_ms", 250.0)
    json_output = getattr(args, "json", False) or getattr(args, "event_stream", False)
    once = getattr(args, "once", False)
    max_iters = 1 if once else getattr(args, "max_iterations", None)

    watcher = WorkspaceGraphWatcher(
        root_dir=target_dir,
        interval=interval,
        debounce_ms=debounce_ms,
        json_output=json_output,
    )
    return watcher.run(max_iterations=max_iters)


def handle_watch_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops watch' command."""
    from pathlib import Path
    from ..core.watcher import WorkspaceWatcher

    target_dir = Path(getattr(args, "dir", "."))
    if str(target_dir) == ".":
        target_dir = config.root_dir
    else:
        target_dir = target_dir.resolve()

    debounce_ms = getattr(args, "debounce_ms", 250.0)
    event_stream = getattr(args, "event_stream", False)
    once = getattr(args, "once", False)
    max_iters = 1 if once else getattr(args, "max_iterations", None)

    watcher = WorkspaceWatcher(
        root_dir=target_dir,
        debounce_ms=debounce_ms,
        event_stream=event_stream,
    )
    return watcher.run(max_iterations=max_iters)



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
