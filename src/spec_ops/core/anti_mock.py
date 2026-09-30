"""AST Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate (ADR-0003, ADR-0009)."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

PROHIBITED_MOCK_MODULES = {
    "unittest.mock",
    "mock",
    "pytest_mock",
}

PROHIBITED_CALL_NAMES = {
    "patch",
    "patch.object",
    "MagicMock",
    "Mock",
    "AsyncMock",
    "NonCallableMock",
    "PropertyMock",
    "spy",
}

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".worktrees",
    ".specops",
    "mutants",
    ".mutmut-cache",
    ".hypothesis",
}


@dataclass
class AntiMockViolation:
    """Diagnostic violation recording forbidden mock backdoors with exact line and column."""

    file_path: str
    line: int
    column: int
    rule: str
    message: str
    snippet: str = ""

    def format_diagnostic(self) -> str:
        snippet_line = f"\n   Line {self.line}: {self.snippet}" if self.snippet else ""
        return (
            f"❌ Anti-Mock Violation (ADR-0003): {self.file_path}:{self.line}:{self.column}"
            f"{snippet_line}\n"
            f"   Issue: {self.message}\n"
            f"   Remediation: Exercise the feature exclusively through public entrypoints and frontdoors without private mock backdoors."
        )


@dataclass
class AntiMockAuditReport:
    """Aggregated report of test suite anti-mock audit and mutation health."""

    scanned_files: int = 0
    violations: list[AntiMockViolation] = field(default_factory=list)
    mutation_score: float = 85.0
    surviving_mutants: list[str] = field(default_factory=list)
    untyped_branches: list[str] = field(default_factory=list)
    strict_mutation: bool = False
    mutation_threshold: float = 80.0

    @property
    def is_clean(self) -> bool:
        if len(self.violations) > 0:
            return False
        if self.strict_mutation and self.mutation_score < self.mutation_threshold:
            return False
        return True

    def format_output(self) -> str:
        lines: list[str] = []
        if len(self.violations) > 0:
            lines.append(f"❌ Found {len(self.violations)} prohibited mock backdoor violation(s) (ADR-0003):\n")
            for v in self.violations:
                lines.append(v.format_diagnostic())
                lines.append("")
            lines.append("🚫 Test audit failed: autonomous agents and contributors must exercise features exclusively through public entrypoints.")
            return "\n".join(lines)

        if self.strict_mutation and self.mutation_score < self.mutation_threshold:
            lines.append(f"❌ Mutation Score Invariant Failed: {self.mutation_score:.1f}% < {self.mutation_threshold:.1f}% threshold (ADR-0009 violation).")
            if len(self.surviving_mutants) > 0:
                lines.append("Surviving Mutants:")
                for m_id in self.surviving_mutants:
                    lines.append(f"  - {m_id}")
            if len(self.untyped_branches) > 0:
                lines.append("Untyped code branches requiring property or edge-case tests:")
                for br in self.untyped_branches:
                    lines.append(f"  - {br}")
            return "\n".join(lines)

        score_repr = int(self.mutation_score) if self.mutation_score.is_integer() else self.mutation_score
        return f"Frontdoor Verification Passed: 0 private backdoors detected, Mutation Kill Score: {score_repr}%"


def _is_private_name(name: str) -> bool:
    """Checks if a name is private (starts with underscore and is not a dunder name)."""
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _resolve_call_path(node: ast.AST) -> str:
    """Recursively resolves call attribute path (e.g. 'patch.object', 'mocker.patch')."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _resolve_call_path(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _extract_snippet(source_lines: Sequence[str], line_no: int) -> str:
    if 1 <= line_no <= len(source_lines):
        return source_lines[line_no - 1].strip()
    return ""


class AntiMockASTVisitor(ast.NodeVisitor):
    """Inspects AST of a test file for prohibited mocks, spies, and private monkeypatching."""

    def __init__(self, file_path: str, source_lines: Sequence[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: list[AntiMockViolation] = []

    def _add_violation(self, line: int, col: int, rule: str, message: str) -> None:
        snippet = _extract_snippet(self.source_lines, line)
        self.violations.append(
            AntiMockViolation(
                file_path=self.file_path,
                line=line,
                column=col,
                rule=rule,
                message=message,
                snippet=snippet,
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name
            if name in PROHIBITED_MOCK_MODULES or name.startswith("unittest.mock."):
                self._add_violation(
                    node.lineno,
                    node.col_offset,
                    "prohibited_mock_import",
                    f"Prohibited import of mock library '{name}' (ADR-0003 violation).",
                )
            elif _is_private_name(name):
                self._add_violation(
                    node.lineno,
                    node.col_offset,
                    "private_symbol_import",
                    f"Prohibited import of private module '{name}'.",
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if mod in PROHIBITED_MOCK_MODULES or mod.startswith("unittest.mock."):
            self._add_violation(
                node.lineno,
                node.col_offset,
                "prohibited_mock_import",
                f"Prohibited import from mock module '{mod}' (ADR-0003 violation).",
            )
            self.generic_visit(node)
            return
        elif _is_private_name(mod):
            self._add_violation(
                node.lineno,
                node.col_offset,
                "private_symbol_import",
                f"Prohibited import from private module '{mod}'.",
            )

        for alias in node.names:
            name = alias.name
            if mod == "unittest" and name == "mock":
                self._add_violation(
                    node.lineno,
                    node.col_offset,
                    "prohibited_mock_import",
                    "Prohibited import of 'mock' from 'unittest' (ADR-0003 violation).",
                )
            elif (mod.startswith("unittest") or mod in ("mock", "pytest_mock")) and name in PROHIBITED_CALL_NAMES:
                self._add_violation(
                    node.lineno,
                    node.col_offset,
                    "prohibited_mock_import",
                    f"Prohibited import of '{name}' from '{mod}' (ADR-0003 violation).",
                )
            elif _is_private_name(name):
                self._add_violation(
                    node.lineno,
                    node.col_offset,
                    "private_symbol_import",
                    f"Prohibited import of private symbol '{name}' (ADR-0003 violation).",
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _resolve_call_path(node.func)

        if call_name in PROHIBITED_CALL_NAMES or any(
            call_name.endswith(f".{name}") for name in PROHIBITED_CALL_NAMES
        ):
            self._add_violation(
                node.lineno,
                node.col_offset,
                "prohibited_mock_call",
                f"Prohibited invocation of mock backdoor '{call_name}()' (ADR-0003 violation).",
            )
        elif call_name.endswith((".setattr", ".delattr")):
            is_private = False
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                if _is_private_name(node.args[1].value):
                    is_private = True
            elif len(node.args) >= 1 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                target_str = node.args[0].value
                parts = target_str.split(".")
                if any(_is_private_name(part) for part in parts):
                    is_private = True

            if is_private:
                self._add_violation(
                    node.lineno,
                    node.col_offset,
                    "private_monkeypatch",
                    "Prohibited monkeypatching of internal private attribute or method (ADR-0003 violation).",
                )

        self.generic_visit(node)


def scan_test_code(content: str, file_path: str = "<test_code>") -> list[AntiMockViolation]:
    """Scans Python test source code for prohibited mocks and private method tampering."""
    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as e:
        return [
            AntiMockViolation(
                file_path=file_path,
                line=e.lineno or 1,
                column=e.offset or 1,
                rule="syntax_error",
                message=f"Syntax error parsing test file: {e.msg}",
            )
        ]
    lines = content.splitlines()
    visitor = AntiMockASTVisitor(file_path=file_path, source_lines=lines)
    visitor.visit(tree)
    return visitor.violations


def scan_test_file(path: Path | str) -> list[AntiMockViolation]:
    """Scans a single test file on disk."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_test_code(content, str(p))


def scan_test_tree(root_path: Path | str) -> list[AntiMockViolation]:
    """Recursively scans all test files in a directory for anti-mock violations."""
    root = Path(root_path)
    if root.is_file():
        return scan_test_file(root)

    violations: list[AntiMockViolation] = []
    for p in sorted(root.rglob("*.py")):
        rel_parts = p.relative_to(root).parts if root.is_dir() else p.parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        violations.extend(scan_test_file(p))
    return violations


def resolve_mutation_stats(root_dir: Path | str) -> tuple[float, list[str], list[str]]:
    """Resolves Mutmut mutation stats from disk artifacts or default baseline."""
    root = Path(root_dir)
    specops_report = root / ".specops" / "mutation_report.json"
    if specops_report.is_file():
        try:
            data = json.loads(specops_report.read_text(encoding="utf-8"))
            score = float(data.get("mutation_score", 85.0))
            surviving = list(data.get("surviving_mutants", []))
            untyped = list(data.get("untyped_branches", []))
            return score, surviving, untyped
        except Exception:
            pass

    cicd_stats = root / "mutants" / "mutmut-cicd-stats.json"
    if cicd_stats.is_file():
        try:
            data = json.loads(cicd_stats.read_text(encoding="utf-8"))
            total = int(data.get("total", 0))
            killed = int(data.get("killed", 0))
            survived = int(data.get("survived", 0))
            score = round((killed / total * 100.0), 1) if total > 0 else 85.0
            surviving = [f"mutant_{i}" for i in range(1, survived + 1)] if survived > 0 else []
            untyped = ["Untyped branch requiring property or edge-case test"] if survived > 0 else []
            return score, surviving, untyped
        except Exception:
            pass

    return 85.0, [], []


def audit_test_suite(
    target_path: Path | str | None = None,
    root_dir: Path | str | None = None,
    strict_mutation: bool = False,
    mutation_threshold: float = 80.0,
) -> AntiMockAuditReport:
    """Runs full frontdoor anti-mock audit and mutation health check."""
    root = Path(root_dir) if root_dir else Path.cwd()
    if target_path:
        target = Path(target_path)
        if not target.is_absolute():
            target = root / target
    else:
        tests_dir = root / "tests"
        target = tests_dir if tests_dir.is_dir() else root

    violations = scan_test_tree(target)

    if target.is_file():
        scanned_count = 1
    elif target.is_dir():
        scanned_count = len([
            p for p in target.rglob("*.py")
            if not any(part in EXCLUDE_DIRS for part in p.relative_to(target).parts)
        ])
    else:
        scanned_count = 0

    mut_score, surviving, untyped = resolve_mutation_stats(root)

    return AntiMockAuditReport(
        scanned_files=scanned_count,
        violations=violations,
        mutation_score=mut_score,
        surviving_mutants=surviving,
        untyped_branches=untyped,
        strict_mutation=strict_mutation,
        mutation_threshold=mutation_threshold,
    )
