"""AST seam extraction and modular file decomposition blueprint generator."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AstSymbol:
    name: str
    kind: str  # "class", "function", "interface", "type"
    lineno: int
    end_lineno: int

    @property
    def line_count(self) -> int:
        return max(1, self.end_lineno - self.lineno + 1)


@dataclass
class SubmoduleBlueprint:
    name: str
    symbols: list[AstSymbol] = field(default_factory=list)

    @property
    def symbol_names(self) -> list[str]:
        return [s.name for s in self.symbols]

    @property
    def estimated_lines(self) -> int:
        return sum(s.line_count for s in self.symbols)


@dataclass
class DecompositionBlueprint:
    source_path: str
    total_lines: int
    submodules: list[SubmoduleBlueprint] = field(default_factory=list)
    barrel_code: str = ""

    def summary(self) -> str:
        lines = [f"Decomposition Blueprint for {self.source_path} ({self.total_lines} lines):"]
        for sub in self.submodules:
            lines.append(f"  Submodule '{sub.name}' (~{sub.estimated_lines} lines):")
            for sym in sub.symbols:
                lines.append(f"    - [{sym.kind}] {sym.name} (lines {sym.lineno}-{sym.end_lineno})")
        if self.barrel_code:
            lines.append("  Suggested barrel exports:")
            for b_line in self.barrel_code.splitlines():
                lines.append(f"    {b_line}")
        return "\n".join(lines)


def _tokenize_name(name: str) -> list[str]:
    """Splits identifier into lowercase words."""
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", name)
    if not words:
        words = [p.lower() for p in name.split("_") if p]
    return [w.lower() for w in words]


def _extract_python_symbols(source_code: str) -> list[AstSymbol]:
    """Extracts top-level classes and functions from Python AST."""
    symbols: list[AstSymbol] = []
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return symbols

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            symbols.append(AstSymbol(name=node.name, kind="function", lineno=node.lineno, end_lineno=end))
        elif isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            symbols.append(AstSymbol(name=node.name, kind="class", lineno=node.lineno, end_lineno=end))
    return symbols


def _extract_ts_symbols(source_code: str) -> list[AstSymbol]:
    """Extracts top-level declarations from TypeScript/JavaScript."""
    symbols: list[AstSymbol] = []
    pattern = re.compile(
        r"^(?:export\s+)?(?:default\s+)?(class|interface|type|function|const)\s+([A-Za-z0-9_]+)",
        re.MULTILINE,
    )
    lines = source_code.splitlines()
    for idx, line in enumerate(lines, start=1):
        m = pattern.match(line.strip())
        if m:
            kind, name = m.group(1), m.group(2)
            symbols.append(AstSymbol(name=name, kind=kind, lineno=idx, end_lineno=idx))
    return symbols


def _cluster_symbols(file_stem: str, symbols: list[AstSymbol], is_ts: bool) -> list[SubmoduleBlueprint]:
    """Groups symbols into cohesive submodules based on semantics and balance."""
    ext = ".ts" if is_ts else ".py"
    if not symbols:
        return [
            SubmoduleBlueprint(name=f"{file_stem}_part1{ext}", symbols=[]),
            SubmoduleBlueprint(name=f"{file_stem}_part2{ext}", symbols=[]),
        ]

    if len(symbols) == 1:
        return [SubmoduleBlueprint(name=f"{file_stem}_core{ext}", symbols=symbols)]

    # Collect token occurrences across symbols, excluding generic words and file stem words
    file_stem_tokens = set(_tokenize_name(file_stem))
    token_symbols: dict[str, list[AstSymbol]] = {}
    for sym in symbols:
        tokens = set(_tokenize_name(sym.name))
        for token in tokens:
            if (
                token in file_stem_tokens
                or token in file_stem.lower()
                or file_stem.lower().startswith(token)
                or token in ("get", "set", "is", "has", "do", "run", "handle", "test")
            ):
                continue
            token_symbols.setdefault(token, []).append(sym)

    # Find dominant themes
    sorted_tokens = sorted(
        token_symbols.keys(),
        key=lambda t: len(token_symbols[t]),
        reverse=True,
    )

    assigned: set[str] = set()
    clusters: list[tuple[str, list[AstSymbol]]] = []

    for token in sorted_tokens:
        candidate_syms = [s for s in token_symbols[token] if s.name not in assigned]
        if candidate_syms and len(candidate_syms) < len(symbols):
            clusters.append((token, candidate_syms))
            for s in candidate_syms:
                assigned.add(s.name)
            if len(clusters) >= 2:
                break

    # Gather remaining unassigned symbols
    remaining = [s for s in symbols if s.name not in assigned]
    if clusters and remaining:
        if len(clusters) == 1:
            clusters.append(("core", remaining))
        else:
            clusters[0][1].extend(remaining)
    elif not clusters:
        # Fallback: split evenly into two modules
        mid = max(1, len(symbols) // 2)
        clusters = [("part1", symbols[:mid]), ("part2", symbols[mid:])]

    submodules: list[SubmoduleBlueprint] = []
    for suffix, cluster_syms in clusters:
        sub_name = f"{file_stem}_{suffix}{ext}"
        submodules.append(SubmoduleBlueprint(name=sub_name, symbols=cluster_syms))

    return submodules


def _generate_barrel_code(submodules: list[SubmoduleBlueprint], is_ts: bool) -> str:
    """Generates suggested barrel export code (__init__.py or index.ts)."""
    if is_ts:
        barrel_lines = []
        for sub in submodules:
            stem = sub.name[:-3] if sub.name.endswith(".ts") else sub.name
            barrel_lines.append(f'export * from "./{stem}";')
        return "\n".join(barrel_lines)

    lines: list[str] = []
    all_exports: list[str] = []
    for sub in submodules:
        stem = sub.name[:-3] if sub.name.endswith(".py") else sub.name
        names = [s.name for s in sub.symbols]
        if names:
            lines.append(f"from .{stem} import {', '.join(names)}")
            all_exports.extend(names)
    if all_exports:
        lines.append("")
        quoted = ", ".join(f'"{name}"' for name in all_exports)
        lines.append(f"__all__ = [{quoted}]")
    return "\n".join(lines)


def suggest_decomposition(file_path: Path | str, source_text: str | None = None) -> DecompositionBlueprint:
    """Analyzes AST and generates cohesive decomposition blueprint for target file."""
    path = Path(file_path)
    if source_text is None:
        source_text = path.read_text(encoding="utf-8", errors="ignore")

    total_lines = len(source_text.splitlines())
    is_ts = path.suffix in (".ts", ".tsx", ".js", ".jsx")

    symbols = _extract_ts_symbols(source_text) if is_ts else _extract_python_symbols(source_text)
    submodules = _cluster_symbols(path.stem, symbols, is_ts)
    barrel = _generate_barrel_code(submodules, is_ts)

    return DecompositionBlueprint(
        source_path=str(path),
        total_lines=total_lines,
        submodules=submodules,
        barrel_code=barrel,
    )


def derive_task_slug(file_path: Path | str) -> str:
    """Derives normalized kebab-case slug from file path."""
    p = Path(file_path)
    parts = [part for part in p.with_suffix("").parts if part not in (".", "..", "src")]
    return "-".join(parts) if parts else p.stem


def generate_split_task_content(file_path: Path | str, blueprint: DecompositionBlueprint) -> str:
    """Builds markdown content for proactive split proposal task."""
    slug = derive_task_slug(file_path)
    p = Path(file_path)
    submodule_names = ", ".join(s.name for s in blueprint.submodules)

    return f"""---
id: SPLIT-{slug}
title: Proactive File Decomposition for {p.name}
status: Proposed
created: 2026-09-29
governing_adrs:
  - ADR-0002
target_bc: core
---

# TASK-SPLIT-{slug}: Proactive File Decomposition for {p.name}

## Summary
The file `{p}` has reached {blueprint.total_lines} lines, exceeding the 400-line warning threshold governed by ADR-0002.
This task decomposes the oversized file into cohesive submodules ({submodule_names}) before reaching the hard 500-line limit.

## AST Decomposition Blueprint
{blueprint.summary()}

## Suggested Submodule Boundaries
{chr(10).join(f"- `{sub.name}`: {', '.join(sub.symbol_names)}" for sub in blueprint.submodules)}

## INVEST Criteria
- **Independent**: Decoupled from parallel feature streams via public frontdoors.
- **Negotiable**: Submodule boundaries can be tailored during refinement.
- **Valuable**: Eliminates monolithic file rot and protects CI from hard limit failure.
- **Estimable**: Clear scope bounded by AST symbols and barrel re-exports.
- **Small (<500 lines)**: Resulting submodules each contain <400 lines (governed by ADR-0002).
- **Testable**: Preserves blackbox contract verified via existing public test suite.
"""


def generate_refactor_task_content(file_path: Path | str, blueprint: DecompositionBlueprint) -> str:
    """Builds markdown content for grandfathered debt refactoring task."""
    slug = derive_task_slug(file_path)
    p = Path(file_path)
    submodule_names = ", ".join(s.name for s in blueprint.submodules)

    return f"""---
id: REFACTOR-{slug}
title: Refactor and Decompose Legacy File {p.name}
status: Proposed
created: 2026-09-29
governing_adrs:
  - ADR-0002
target_bc: core
---

# TASK-REFACTOR-{slug}: Refactor Legacy File {p.name}

## Summary
The grandfathered debt file `{p}` contains {blueprint.total_lines} lines and violates the hard file length invariant governed by ADR-0002 (<500 lines).
This task plans the incremental extraction of cohesive submodules ({submodule_names}) and establishes a public barrel export facade.

## Target Submodule Decomposition Path
Target decomposition destination: `{p.parent / p.stem}/` with submodules:
{chr(10).join(f"- `{sub.name}`: {', '.join(sub.symbol_names)}" for sub in blueprint.submodules)}

## AST Decomposition Blueprint
{blueprint.summary()}

## INVEST Criteria
- **Independent**: Executed in isolated task branch without modifying shared backlog on branch.
- **Negotiable**: Concrete boundaries derived from AST seams.
- **Valuable**: Retires grandfathered technical debt from `.specops/grandfathered_debt.json`.
- **Estimable**: Symbol-level decomposition blueprint provided.
- **Small (<500 lines)**: Target submodules each strictly under 400 lines.
- **Testable**: Validated via blackbox frontdoor tests (ADR-0003).
"""


def emit_split_task(backlog_dir: Path, file_path: Path | str, blueprint: DecompositionBlueprint) -> Path:
    """Writes TASK-SPLIT-<slug>.md to docs/project/backlog/proposed/."""
    slug = derive_task_slug(file_path)
    target_dir = backlog_dir / "proposed"
    target_dir.mkdir(parents=True, exist_ok=True)
    task_file = target_dir / f"TASK-SPLIT-{slug}.md"
    content = generate_split_task_content(file_path, blueprint)
    task_file.write_text(content.strip() + "\n", encoding="utf-8")
    return task_file


def emit_refactor_task(backlog_dir: Path, file_path: Path | str, blueprint: DecompositionBlueprint) -> Path:
    """Writes TASK-REFACTOR-<slug>.md to docs/project/backlog/proposed/."""
    slug = derive_task_slug(file_path)
    target_dir = backlog_dir / "proposed"
    target_dir.mkdir(parents=True, exist_ok=True)
    task_file = target_dir / f"TASK-REFACTOR-{slug}.md"
    content = generate_refactor_task_content(file_path, blueprint)
    task_file.write_text(content.strip() + "\n", encoding="utf-8")
    return task_file
