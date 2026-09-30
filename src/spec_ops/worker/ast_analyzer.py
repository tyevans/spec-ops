"""Targeted AST diagnostic analyzer for file length overruns and decomposition seams."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AstNodeSeam:
    """Represents a top-level code entity with line boundary metrics."""

    name: str
    kind: str  # "class" or "function"
    lineno: int
    end_lineno: int

    @property
    def line_count(self) -> int:
        if self.end_lineno < self.lineno:
            return 1
        return self.end_lineno - self.lineno + 1

    @property
    def display_kind(self) -> str:
        return "class" if self.kind == "class" else "function"


def extract_top_level_nodes(source_code: str) -> list[AstNodeSeam]:
    """Locates top-level classes and functions from Python source text.

    Safely handles syntax errors, value errors, and malformed inputs
    without throwing AST parsing exceptions.
    """
    nodes: list[AstNodeSeam] = []
    try:
        tree = ast.parse(source_code)
    except (SyntaxError, ValueError, TypeError, MemoryError):
        return nodes

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            nodes.append(AstNodeSeam(name=node.name, kind="class", lineno=node.lineno, end_lineno=end))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            nodes.append(AstNodeSeam(name=node.name, kind="function", lineno=node.lineno, end_lineno=end))
    return nodes


def find_largest_node(nodes: list[AstNodeSeam]) -> AstNodeSeam | None:
    """Identifies the largest top-level node by line count."""
    if not nodes:
        return None
    return max(nodes, key=lambda n: (n.line_count, -n.lineno))


def generate_ast_decomposition_hint(
    file_path: str | Path,
    total_lines: int,
    attempt: int = 1,
    source_code: str | None = None,
    limit: int = 500,
) -> str:
    """Generates structured AST decomposition hints for files exceeding the file length limit."""
    path_str = str(file_path).replace("\\", "/")
    if source_code is None:
        try:
            source_code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            source_code = ""

    nodes = extract_top_level_nodes(source_code)
    largest = find_largest_node(nodes)

    lines = [
        f"## AST Decomposition Hints (Attempt {attempt})",
        f"- File: {path_str} ({total_lines} lines, limit: {limit})",
    ]
    if largest is not None:
        lines.append(
            f"- Largest AST node: {largest.display_kind} {largest.name} "
            f"(lines {largest.lineno}-{largest.end_lineno}, {largest.line_count} lines)"
        )
        lines.append(f"- Suggested seam: extract {largest.name} into separate module")
    else:
        lines.append("- Suggested seam: decompose module into separate files")

    return "\n".join(lines)


def scan_worktree_file_length_violations(
    worktree_dir: Path | str,
    limit: int = 500,
) -> list[tuple[str, int, str]]:
    """Scans python source files in worktree for length violations (>limit lines)."""
    wt = Path(worktree_dir).resolve()
    violations: list[tuple[str, int, str]] = []

    for pattern in ["src/**/*.py", "spec_ops/**/*.py"]:
        for f in wt.glob(pattern):
            if not f.is_file():
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                lines = len(content.splitlines())
                if lines > limit:
                    rel = str(f.relative_to(wt)).replace("\\", "/")
                    violations.append((rel, lines, content))
            except Exception:
                continue

    return violations


def format_preflight_ast_feedback(
    preflight_log: str,
    attempt: int,
    worktree_dir: Path | str,
    limit: int = 500,
) -> str:
    """Formats preflight failure feedback with targeted AST decomposition hints."""
    wt = Path(worktree_dir).resolve()
    feedback = f"## Preflight Failure Feedback (Attempt {attempt})\n{preflight_log}\nPlease fix the preflight issues above."

    violations = scan_worktree_file_length_violations(wt, limit=limit)
    if not violations and ("File Length Violation:" in preflight_log or "lines >" in preflight_log or "limit" in preflight_log):
        import re

        for m in re.finditer(r"([^\s(]+\.py)[^\d]*(\d+)\s*lines", preflight_log):
            v_path = m.group(1).lstrip("./")
            v_lines = int(m.group(2))
            v_full = wt / v_path
            cnt = v_full.read_text(encoding="utf-8", errors="ignore") if v_full.exists() else ""
            violations.append((v_path, v_lines, cnt))

    if violations:
        hint_blocks = [
            generate_ast_decomposition_hint(v_path, v_lines, attempt=attempt, source_code=cnt, limit=limit)
            for v_path, v_lines, cnt in violations
        ]
        feedback += "\n\n" + "\n\n".join(hint_blocks)

    return feedback

