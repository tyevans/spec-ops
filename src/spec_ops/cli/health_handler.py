"""CLI handlers for specialized health checks: architecture, split suggestions, and refactor tasks."""

from __future__ import annotations

import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.arch_checker import ArchitectureChecker
from ..core.ast_seams import emit_refactor_task, emit_split_task, suggest_decomposition
from ..core.debt_baseline import EXCLUDE_DIRS, SOURCE_EXTENSIONS, load_grandfathered_debt


def handle_health_architecture(config: SpecOpsConfig) -> int:
    """Runs bounded context boundary and dependency direction checks."""
    checker = ArchitectureChecker(config.root_dir)
    report = checker.check()
    output = report.format_output()
    if report.is_valid:
        print(f"✅ {output}")
        return 0

    print(f"❌ {output}", file=sys.stderr)
    return 1


def handle_health_suggest_splits(config: SpecOpsConfig, emit_task: bool = False) -> int:
    """Analyzes files in warning threshold and prints decomposition suggestions."""
    root = config.root_dir
    threshold = config.architecture.file_warning_threshold
    limit = config.architecture.file_length_limit

    candidate_files: list[tuple[Path, int]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.suffix not in SOURCE_EXTENSIONS:
            continue
        try:
            lines = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
            if lines >= threshold:
                candidate_files.append((p, lines))
        except OSError:
            continue

    if not candidate_files:
        print("✅ 0 proactive warnings; codebase modularity optimal")
        return 0

    candidate_files.sort(key=lambda x: x[1], reverse=True)
    print(f"⚠️ Found {len(candidate_files)} file(s) in warning threshold (>={threshold} lines):")
    for file_path, line_count in candidate_files:
        rel_path = file_path.relative_to(root)
        print(f"\n--- Proactive anti-rot warning ({line_count} lines >= {threshold} lines threshold): {rel_path} ---")
        blueprint = suggest_decomposition(file_path)
        print(blueprint.summary())

        if emit_task:
            task_path = emit_split_task(config.backlog_dir, rel_path, blueprint)
            print(f"✨ Emitted refactoring task to {task_path.relative_to(root)}")

    return 0


def handle_health_generate_refactor_tasks(config: SpecOpsConfig) -> int:
    """Generates proposed backlog refactoring tasks for all grandfathered debt files."""
    root = config.root_dir
    debt_map = load_grandfathered_debt(root)
    if not debt_map:
        print("ℹ️ Zero grandfathered files registered in debt baseline.")
        return 0

    print(f"🔨 Generating refactoring tasks for {len(debt_map)} grandfathered file(s)...")
    for rel_str in sorted(debt_map.keys()):
        full_path = root / rel_str
        blueprint = suggest_decomposition(full_path)
        task_path = emit_refactor_task(config.backlog_dir, rel_str, blueprint)
        print(f"  ✨ Emitted {task_path.name}")

    print(f"✅ Generated {len(debt_map)} proposed refactoring task(s) in docs/project/backlog/proposed/")
    return 0
