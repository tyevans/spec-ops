"""CLI command handlers for markdown parsing and cache-enabled stats."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.graph import process_project_graph
from ..core.parser import SpecOpsParser
from ..core.spikes.cache_spike import (
    FrontmatterDiagnosticError,
    RelationalGraphCacheEngine,
    parse_markdown_document,
)


def handle_parse_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Parses a markdown specification file with resilient AST and precision frontmatter diagnostics."""
    file_path = getattr(args, "path", None)
    if not file_path:
        print("❌ Missing required file path to parse.", file=sys.stderr)
        return 1

    path = Path(file_path)
    if not path.is_file():
        path = config.root_dir / file_path
    if not path.is_file():
        print(f"❌ File not found: {file_path}", file=sys.stderr)
        return 1

    content = path.read_text(encoding="utf-8")
    try:
        meta, body = parse_markdown_document(content, file_path=file_path)
        title = meta.get("title", path.stem)
        print(f"✅ Successfully parsed entity '{title}' ({file_path})")
        return 0
    except FrontmatterDiagnosticError as err:
        msg = err.format_error()
        print(msg)
        print(msg, file=sys.stderr)
        return 1


def handle_stats_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Inspects entity counts, graph metrics, and buffer state with optional cache acceleration."""
    use_cache = getattr(args, "cache", False)
    if use_cache:
        engine = RelationalGraphCacheEngine(config.root_dir)
        p_data, stats = engine.compile_graph()
        if stats.cold:
            print(f"Graph compiled in cold state: {stats.total_indexed} entities indexed, cache written")
        else:
            files_word = "file" if stats.invalidated == 1 else "files"
            print(f"Incremental graph sync: {stats.invalidated} {files_word} invalidated, {stats.cache_hits} cache hits")
    else:
        p_data = SpecOpsParser(config.project_docs_dir).parse_all()
        process_project_graph(p_data, target_buffer=config.architecture.buffer_target)

    m = p_data.health_metrics
    print(f"=== SpecOps Project Statistics ({config.project.name}) ===")
    print(f"Total Tasks: {m['total_tasks']} ({m['complete_tasks']} Complete, {m['refined_tasks']} Refined, {m['proposed_tasks']} Proposed)")
    print(f"User Stories: {m['total_stories']} | PRDs: {m['total_prds']} | ADRs: {m['total_adrs']} | Personas: {m['total_personas']}")
    print(f"Traceability Edges: {m['total_edges']} | Ready Buffer Health: {m['ready_buffer_health']}")
    return 0
