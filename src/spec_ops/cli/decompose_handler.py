"""CLI handler for AST seam decomposition suggestions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..core.ast_seams import suggest_decomposition


def handle_decompose_command(args: Any) -> int:
    """Executes 'spec-ops decompose' for AST seam extraction and blueprints."""
    file_path = getattr(args, "suggest", None) or getattr(args, "path", None)
    if not file_path:
        print("❌ Error: Specify a file to analyze via 'spec-ops decompose --suggest <file>'", file=sys.stderr)
        return 1

    target = Path(file_path).resolve()
    if not target.is_file():
        print(f"❌ Error: File not found: {file_path}", file=sys.stderr)
        return 1

    blueprint = suggest_decomposition(target)
    print(blueprint.summary())
    return 0
