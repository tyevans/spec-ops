"""CLI command handler for relational graph operations and compilation."""

from __future__ import annotations

import argparse
import json
import sys

from ..config.models import SpecOpsConfig
from ..core.cache import RelationalGraphCacheEngine


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

    print(f"❌ Unknown graph action: {action}", file=sys.stderr)
    return 1
