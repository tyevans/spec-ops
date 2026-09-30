"""Core domain models, parser, and graph engine for SpecOps."""

from .ast_parser import FrontmatterDiagnosticError, parse_markdown_document
from .cache import CompileStats, RelationalGraphCacheEngine
from .git_metadata import GitMetadataHarvester
from .graph import (
    build_graph_data,
    compute_health_metrics,
    generate_traceability_edges,
    process_project_graph,
)
from .models import (
    ADR,
    PRD,
    CommitInfo,
    GraphData,
    GraphEdge,
    GraphNode,
    Persona,
    ProjectData,
    Task,
    TraceabilityEdge,
    UserStory,
)
from .parser import SpecOpsParser, extract_frontmatter

__all__ = [
    "ADR",
    "CommitInfo",
    "CompileStats",
    "FrontmatterDiagnosticError",
    "GitMetadataHarvester",
    "GraphData",
    "GraphEdge",
    "GraphNode",
    "PRD",
    "Persona",
    "ProjectData",
    "RelationalGraphCacheEngine",
    "SpecOpsParser",
    "Task",
    "TraceabilityEdge",
    "UserStory",
    "build_graph_data",
    "compute_health_metrics",
    "extract_frontmatter",
    "generate_traceability_edges",
    "parse_markdown_document",
    "process_project_graph",
    "DirectedGraph",
    "CycleResult",
    "TopologicalTierResult",
    "BlastRadiusResult",
    "tarjan_scc",
    "detect_cycles",
    "kahns_topological_sort",
    "compute_execution_tiers",
    "compute_blast_radius",
    "find_shortest_traceability_path",
    "format_traceability_path",
    "inspect_entity",
    "audit_traceability",
    "audit_bottlenecks",
    "audit_graph_all",
]

from .graph_audit import audit_bottlenecks, audit_graph_all, audit_traceability
from .pathfinder import find_shortest_traceability_path, format_traceability_path, inspect_entity
from .topology import (
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
