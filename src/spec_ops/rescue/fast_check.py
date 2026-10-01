"""Sub-second incremental invariant diagnostics for editor and IDE feedback (US-0091, TASK-0055).

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0008, ADR-0009.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig

FILE_WARN_THRESHOLD = 400
FILE_LIMIT = 500
SHARED_CONTEXTS = {"core", "config"}
KNOWN_CONTEXTS = {
    "adrs", "backlog", "cli", "docs", "graph", "prd", "profiles",
    "rescue", "scaffold", "security", "spike", "tui", "visualizer", "worker",
}


@dataclass
class DiagnosticViolation:
    """Individual invariant violation or warning."""

    rule_id: str
    rule_name: str
    severity: str
    file_path: str
    line: int
    column: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule_id, "rule_name": self.rule_name,
            "severity": self.severity, "file": self.file_path,
            "line": self.line, "column": self.column, "message": self.message,
        }


@dataclass
class FastCheckResult:
    """Aggregate result of single-file fast check."""

    file_path: str
    lines: int
    status: str
    threshold: int = FILE_WARN_THRESHOLD
    limit: int = FILE_LIMIT
    message: str = ""
    violations: list[DiagnosticViolation] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "error" else 0

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "file": self.file_path, "lines": self.lines, "status": self.status,
            "threshold": self.threshold, "limit": self.limit, "message": self.message,
        }
        non_line = [v for v in self.violations if v.rule_id != "ADR-0002"]
        if non_line:
            payload["violations"] = [v.to_dict() for v in non_line]
        return json.dumps(payload, indent=2)

    def to_sarif(self) -> str:
        results = [
            {
                "ruleId": v.rule_id, "level": v.severity,
                "message": {"text": v.message},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": v.file_path},
                        "region": {"startLine": v.line, "startColumn": v.column},
                    }
                }],
            }
            for v in self.violations
        ]
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "spec-ops",
                        "rules": [
                            {"id": "ADR-0002", "name": "FileLengthLimit", "shortDescription": {"text": "File length limit"}},
                            {"id": "ADR-0007", "name": "BoundedContextBoundary", "shortDescription": {"text": "Bounded context isolation"}},
                        ],
                    }
                },
                "results": results,
            }],
        }
        return json.dumps(sarif, indent=2)

    def to_text(self) -> str:
        if self.status == "clean" and not self.violations:
            return f"✅ Clean: {self.file_path} ({self.lines} lines) - All invariants satisfied."
        lines: list[str] = [f"{v.file_path}:{v.line}:{v.column}: {v.severity}: {v.message}" for v in self.violations]
        if not lines and self.message:
            lines.append(self.message)
        return "\n".join(lines)


def determine_file_context(file_path: str | Path, root_dir: str | Path | None = None) -> str | None:
    """Extracts bounded context from target file path."""
    parts = Path(file_path).parts
    valid_contexts = KNOWN_CONTEXTS | SHARED_CONTEXTS
    if "src" in parts:
        rem = parts[parts.index("src") + 1 :]
        if len(rem) >= 2 and rem[0] in ("spec_ops", "specops", "app"):
            if rem[1] in valid_contexts or (root_dir and (Path(root_dir) / "src" / rem[0] / rem[1]).is_dir()):
                return rem[1]
        elif len(rem) >= 1 and (rem[0] in valid_contexts or (root_dir and (Path(root_dir) / "src" / rem[0]).is_dir())):
            return rem[0]
    for part in reversed(parts[:-1]):
        if part in valid_contexts:
            return part
    return None


def _check_import_module(
    module: str, alias_name: str, line: int, col: int,
    file_path: str, file_ctx: str, violations: list[DiagnosticViolation],
    root_dir: str | Path | None = None,
) -> None:
    """Evaluates whether an imported module violates bounded context boundary rules."""
    mod = module.strip()
    for pfx in ("src.", "spec_ops.", "specops."):
        if mod.startswith(pfx):
            mod = mod[len(pfx):]
    parts = mod.split(".") if mod else []
    if not parts:
        return

    target_bc = parts[0]
    if target_bc in SHARED_CONTEXTS or target_bc == file_ctx or target_bc not in KNOWN_CONTEXTS:
        return

    internal_mod: str | None = None
    if len(parts) >= 2:
        internal_mod = ".".join(parts)
    elif alias_name:
        is_sub = alias_name.islower() and not alias_name.startswith("_")
        if root_dir:
            r = Path(root_dir)
            t_py = r / "src" / "spec_ops" / target_bc / f"{alias_name}.py"
            t_pkg = r / "src" / "spec_ops" / target_bc / alias_name / "__init__.py"
            f_py = r / "src" / target_bc / f"{alias_name}.py"
            if t_py.is_file() or t_pkg.is_file() or f_py.is_file():
                is_sub = True
        if is_sub:
            internal_mod = f"{target_bc}.{alias_name}"

    if internal_mod:
        msg = f"Bounded Context Violation: '{file_ctx}' cannot directly import internal module '{internal_mod}' (governed by ADR-0007)."
        if any(v.line == line and v.column == col and v.message == msg for v in violations):
            return
        violations.append(DiagnosticViolation("ADR-0007", "BoundedContextBoundary", "error", file_path, line, col, msg))


def check_ast_imports(
    code: str, file_path: str, file_ctx: str, root_dir: str | Path | None = None,
) -> list[DiagnosticViolation]:
    """Inspects AST imports for cross-bounded-context internal module boundary violations."""
    violations: list[DiagnosticViolation] = []
    try:
        tree = ast.parse(code, filename=file_path)
    except SyntaxError as exc:
        violations.append(DiagnosticViolation("SYNTAX", "SyntaxError", "error", file_path, exc.lineno or 1, (exc.offset or 0) + 1, f"SyntaxError: {exc.msg}"))
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import_module(alias.name, "", node.lineno, (node.col_offset or 0) + 1, file_path, file_ctx, violations, root_dir)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level > 0:
                parts = [p for p in Path(file_path).with_suffix("").parts if p not in ("src", "spec_ops", "specops")]
                base = parts[:-node.level] if len(parts) >= node.level else []
                resolved_mod = ".".join(base + ([mod] if mod else []))
            else:
                resolved_mod = mod
            for alias in node.names:
                _check_import_module(resolved_mod, alias.name, node.lineno, (node.col_offset or 0) + 1, file_path, file_ctx, violations, root_dir)

    return violations


def run_fast_check(
    file_path: str | Path,
    output_format: str = "text",
    root_dir: str | Path | None = None,
    threshold: int = FILE_WARN_THRESHOLD,
    limit: int = FILE_LIMIT,
) -> FastCheckResult:
    """Executes sub-50ms single-file invariant diagnostic checks."""
    t0 = time.perf_counter()
    path = Path(file_path)

    if not path.is_file():
        return FastCheckResult(
            str(file_path).replace("\\", "/"), 0, "error", threshold, limit,
            f"Error: Target file not found: {file_path}", duration_ms=(time.perf_counter() - t0) * 1000,
        )

    rel_path = str(file_path).replace("\\", "/")
    if root_dir:
        try:
            rel_path = str(path.resolve().relative_to(Path(root_dir).resolve())).replace("\\", "/")
        except ValueError:
            pass

    try:
        code = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as err:
        return FastCheckResult(rel_path, 0, "error", threshold, limit, f"Error reading file: {err}", duration_ms=(time.perf_counter() - t0) * 1000)

    line_count = len(code.splitlines())
    violations: list[DiagnosticViolation] = []

    if line_count >= limit:
        line_no = 501 if line_count >= 501 else line_count
        violations.append(DiagnosticViolation("ADR-0002", "FileLengthLimit", "error", rel_path, line_no, 1, f"Hard Invariant Violation: File exceeds {limit} lines ({line_count} lines). Commit will be rejected."))
    elif line_count >= threshold:
        line_no = threshold + 1 if line_count > threshold else line_count
        violations.append(DiagnosticViolation("ADR-0002", "FileLengthLimit", "warning", rel_path, line_no, 1, f"Approaching file length limit ({line_count}/{limit} lines). Consider decomposing into submodules."))

    if path.suffix == ".py":
        file_ctx = determine_file_context(path, root_dir)
        if file_ctx:
            violations.extend(check_ast_imports(code, rel_path, file_ctx, root_dir))

    has_error = any(v.severity == "error" for v in violations) or line_count >= limit
    has_warning = any(v.severity == "warning" for v in violations) or line_count >= threshold

    if has_error:
        status = "error"
        errors = [v for v in violations if v.severity == "error"]
        if line_count >= limit:
            message = f"Hard Invariant Violation: File exceeds {limit} lines ({line_count} lines). Commit will be rejected."
        elif errors:
            message = errors[0].message
        else:
            message = f"Invariant violation detected in {rel_path}."
    elif has_warning:
        status = "warning"
        message = f"Approaching file length limit ({line_count}/{limit} lines). Consider decomposing into submodules."
    else:
        status = "clean"
        message = f"File is compliant ({line_count}/{limit} lines). No invariant violations detected."

    return FastCheckResult(rel_path, line_count, status, threshold, limit, message, violations, duration_ms=(time.perf_counter() - t0) * 1000)


def handle_fast_check_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """CLI handler for 'spec-ops check --fast --file <path> [--format text|json|sarif]'."""
    target_file = getattr(args, "file", None) or getattr(args, "positional_file", None)
    if not target_file:
        print("❌ Error: Target file required. Specify --file <path>.", file=sys.stderr)
        return 1

    fmt = getattr(args, "format", "text") or "text"
    result = run_fast_check(file_path=target_file, output_format=fmt, root_dir=config.root_dir)

    if fmt == "json":
        print(result.to_json())
    elif fmt == "sarif":
        print(result.to_sarif())
    else:
        print(result.to_text())

    return result.exit_code
