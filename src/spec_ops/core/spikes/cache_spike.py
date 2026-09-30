"""Compatibility shim for cache and AST parsing spike (graduated in TASK-0058)."""

from __future__ import annotations

from ..ast_parser import FrontmatterDiagnosticError, parse_markdown_document
from ..cache import (
    BenchmarkResult,
    CompileStats,
    RelationalGraphCacheEngine,
    _build_cache_entry,
    _deserialize_entity,
    _serialize_entity,
    benchmark_graph_compilation,
    compute_cache_checksum,
    compute_content_sha256,
)

__all__ = [
    "FrontmatterDiagnosticError",
    "parse_markdown_document",
    "CompileStats",
    "BenchmarkResult",
    "RelationalGraphCacheEngine",
    "_serialize_entity",
    "_deserialize_entity",
    "_build_cache_entry",
    "benchmark_graph_compilation",
    "compute_cache_checksum",
    "compute_content_sha256",
]
