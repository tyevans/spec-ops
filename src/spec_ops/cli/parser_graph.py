"""Subparser registration for graph, topology, and pathfinder CLI commands."""

from __future__ import annotations

import argparse


def register_graph_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers graph compilation, cycles, pathfinding, and inspection commands."""
    p_graph = subparsers.add_parser("graph", help="Relational graph operations and compilation")
    graph_subs = p_graph.add_subparsers(dest="graph_action", help="Graph action")
    p_g_comp = graph_subs.add_parser("compile", help="Compile repository relational knowledge graph")
    p_g_comp.add_argument("--incremental", action="store_true", help="Perform incremental compilation backed by content-addressed cache")
    p_g_comp.add_argument("--json", action="store_true", help="Output compilation result and graph statistics as JSON")
    p_g_comp.add_argument("--force-cold", action="store_true", help="Force a cold compilation rebuild regardless of cache state")

    p_g_cyc = graph_subs.add_parser("cycles", help="Deterministic cycle detection via Tarjan SCC")
    p_g_cyc.add_argument("--format", choices=["text", "json"], default="text", help="Output format (default: text)")
    p_g_cyc.add_argument("--json", action="store_true", help="Output cycles as JSON")
    p_g_cyc.add_argument("--resolve", action="store_true", help="Resolve cycles with minimal feedback edge detection")
    p_g_cyc.add_argument("--prune-chokepoints", action="store_true", help="Calculate bottleneck nodes and decoupling seams")
    p_g_cyc.add_argument("--check-edge", nargs=2, metavar=("SOURCE", "TARGET"), help="Fast cycle pre-check for proposed dependency edge")
    p_g_cyc.add_argument("--cache", action="store_true", help="Use incremental DAG topological cache")

    p_g_sort = graph_subs.add_parser("sort", help="Deterministic topological backlog execution sorting")
    p_g_sort.add_argument("--type", default="task", help="Entity type filter (default: task)")

    p_g_ord = graph_subs.add_parser("order", help="Deterministic topological backlog execution ordering")
    p_g_ord.add_argument("--type", default="task", help="Entity type filter (default: task)")

    p_g_path = graph_subs.add_parser("path", help="Reachability pathfinding and lineage tracing")
    p_g_path.add_argument("--from", dest="from_node", required=True, help="Origin entity ID (e.g. persona:taylor)")
    p_g_path.add_argument("--to", dest="to_node", required=True, help="Destination entity ID (e.g. commit:a1b2c3d)")

    p_g_reach = graph_subs.add_parser("reach", help="Verify reachability between graph entities")
    p_g_reach.add_argument("--source", required=True, help="Source entity ID (e.g. persona:Alex or TASK-0001)")
    p_g_reach.add_argument("--target", required=True, help="Target entity ID (e.g. PRD-0001 or ADR-0010)")
    p_g_reach.add_argument("--json", action="store_true", help="Output reachability result as JSON")

    p_g_blast = graph_subs.add_parser("blast-radius", help="Calculate downstream blast radius of entity")
    p_g_blast.add_argument("entity", help="Target entity ID (e.g. ADR-0003)")

    p_g_insp = graph_subs.add_parser("inspect", help="Inspect entity metadata, lineage card, and neighborhood")
    p_g_insp.add_argument("entity", help="Target entity ID (e.g. TASK-0042)")

    graph_subs.add_parser("audit", help="Full bidirectional graph traceability and orphan work item audit")
    p_g_watch = graph_subs.add_parser("watch", help="Real-time in-memory graph event bus and workspace change watcher")
    p_g_watch.add_argument("--interval", type=float, default=0.5, help="Polling interval in seconds (default: 0.5)")
    p_g_watch.add_argument("--debounce-ms", type=float, default=250.0, help="Debounce window in milliseconds (default: 250)")
    p_g_watch.add_argument("--json", action="store_true", help="Output real-time change events as structured JSON")
    p_g_watch.add_argument("--event-stream", action="store_true", help="Emit raw JSON structured event stream")
    p_g_watch.add_argument("--dir", default=".", help="Target repository directory (default: current directory)")
    p_g_watch.add_argument("--once", action="store_true", help="Run single watcher scan iteration and exit")
    p_g_watch.add_argument("--max-iterations", type=int, default=None, help="Maximum number of poll iterations before exit")

    p_g_merm = graph_subs.add_parser("mermaid", help="Export relational knowledge graph subgraph as Mermaid or Graphviz diagram")
    p_g_merm.add_argument("--root", default=None, help="Root entity identifier (e.g. TASK-0001, PRD-0001)")
    p_g_merm.add_argument("--depth", type=int, default=2, help="Traversal depth limit (default: 2)")
    p_g_merm.add_argument("--format", choices=["mermaid", "dot"], default="mermaid", help="Diagram output format")
    p_g_merm.add_argument("--direction", choices=["TD", "LR", "TB", "RL"], default="TD", help="Diagram layout direction")
    p_g_merm.add_argument("--output", "-o", default=None, help="Output file path to save diagram")

    p_g_dead = graph_subs.add_parser("deadlock", help="Detect circular task dependencies and compute minimal feedback arc cuts")
    p_g_dead.add_argument("--resolve", action="store_true", help="Apply proposed minimal dependency cuts to task files")
    p_g_dead.add_argument("--dry-run", action="store_true", default=False, help="Simulate dependency cut resolution without modifying task files")
    p_g_dead.add_argument("--json", action="store_true", help="Output deadlock analysis and cut recommendations as JSON")

    # Pathfinder alias: spec-ops pathfinder inspect / path
    p_pf = subparsers.add_parser("pathfinder", help="Reachability pathfinding and entity inspection")
    pf_subs = p_pf.add_subparsers(dest="graph_action", help="Pathfinder action")
    p_pf_insp = pf_subs.add_parser("inspect", help="Inspect entity metadata, lineage card, and neighborhood")
    p_pf_insp.add_argument("entity", help="Target entity ID (e.g. TASK-0042)")
    p_pf_path = pf_subs.add_parser("path", help="Reachability pathfinding and lineage tracing")
    p_pf_path.add_argument("--from", dest="from_node", required=True, help="Origin entity ID")
    p_pf_path.add_argument("--to", dest="to_node", required=True, help="Destination entity ID")
