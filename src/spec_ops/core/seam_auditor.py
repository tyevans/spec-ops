"""Autonomous Bounded Context Seam Auditor and Cross-Context Coupling Heatmap (ADR-0007, PRD-0005, US-0106)."""

from __future__ import annotations

import ast
import fnmatch
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "site", "__pycache__",
    ".pytest_cache", ".worktrees", ".specops",
}

DEFAULT_FORBIDDEN_RULES: dict[str, list[str]] = {
    "domain": ["presentation", "infrastructure", "cli", "visualizer"],
}


@dataclass
class SeamViolation:
    """Represents an unauthorized or illegal cross-context dependency import."""

    source_file: str
    source_context: str
    imported_module: str
    target_context: str
    reason: str
    line: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_message(self) -> str:
        return (
            f"❌ [{self.source_context} -> {self.target_context}] {self.source_file}:{self.line}\n"
            f"   Illegal import '{self.imported_module}': {self.reason}"
        )


@dataclass
class ContextMetrics:
    """Coupling and stability metrics for a single bounded context."""

    context: str
    afferent_coupling: int = 0  # Ca: incoming dependent contexts
    efferent_coupling: int = 0  # Ce: outgoing dependency contexts
    instability: float = 0.0     # I = Ce / (Ca + Ce)
    incoming_contexts: list[str] = field(default_factory=list)
    outgoing_contexts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": self.context,
            "afferent_coupling": self.afferent_coupling,
            "efferent_coupling": self.efferent_coupling,
            "instability": round(self.instability, 3),
            "incoming_contexts": sorted(self.incoming_contexts),
            "outgoing_contexts": sorted(self.outgoing_contexts),
        }


@dataclass
class SeamAuditReport:
    """Complete audit results across all detected bounded contexts."""

    contexts: list[str] = field(default_factory=list)
    metrics: dict[str, ContextMetrics] = field(default_factory=dict)
    coupling_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    violations: list[SeamViolation] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "contexts": self.contexts,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "coupling_matrix": self.coupling_matrix,
            "violations_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
        }

    def format_text(self) -> str:
        lines: list[str] = [
            "=== Bounded Context Seam & Coupling Audit ===",
            f"Discovered Contexts: {', '.join(self.contexts) if self.contexts else 'None'}\n",
        ]
        if self.metrics:
            lines.append(f"{'Bounded Context':<20} | {'Ca (In)':<8} | {'Ce (Out)':<8} | {'Instability (I)'}")
            lines.append("-" * 56)
            for ctx in self.contexts:
                m = self.metrics.get(ctx, ContextMetrics(context=ctx))
                lines.append(f"{ctx:<20} | {m.afferent_coupling:<8} | {m.efferent_coupling:<8} | {m.instability:.3f}")
            lines.append("")

        if self.violations:
            lines.append(f"⚠️ Detected {len(self.violations)} illegal cross-context dependency leak(s):")
            for v in self.violations:
                lines.append(v.format_message())
        else:
            lines.append("✅ All cross-context dependencies comply with Domain-Driven Design seams.")

        return "\n".join(lines)


def calculate_instability(ca: int, ce: int) -> float:
    """Calculates bounded instability index I = Ce / (Ca + Ce) strictly within [0.0, 1.0]."""
    if ca < 0 or ce < 0:
        return 0.0
    total = ca + ce
    if total <= 0:
        return 0.0
    res = float(ce) / float(total)
    return max(0.0, min(1.0, res))


def extract_python_imports_with_lines(source: str, file_module: str = "") -> list[tuple[str, int]]:
    """Extracts imported modules with their line numbers from Python source."""
    imports: list[tuple[str, int]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            line_no = node.lineno
            if node.level > 0:
                parts = file_module.split(".") if file_module else []
                base = parts[:-node.level] if len(parts) >= node.level else []
                full = ".".join(base + ([mod] if mod else []))
                imports.append((full, line_no))
            else:
                imports.append((mod, line_no))
    return imports


class SeamAuditor:
    """Performs static analysis on source packages to audit bounded context seams and coupling."""

    def __init__(self, root_dir: Path | str, toml_data: dict[str, Any] | None = None):
        self.root_dir = Path(root_dir).resolve()
        self.toml_data = toml_data or self._load_toml()
        self.src_dir = self._find_source_dir()
        self.contexts = self._discover_contexts()
        self.forbidden_rules = self._extract_forbidden_rules()

    def _load_toml(self) -> dict[str, Any]:
        p = self.root_dir / "specops.toml"
        if not p.is_file():
            return {}
        try:
            with p.open("rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    def _find_source_dir(self) -> Path:
        s1 = self.root_dir / "src" / "spec_ops"
        if s1.is_dir():
            return s1
        s2 = self.root_dir / "src"
        if s2.is_dir():
            return s2
        return self.root_dir

    def _discover_contexts(self) -> list[str]:
        found: set[str] = set()
        arch = self.toml_data.get("architecture", {})
        bcs = arch.get("bounded_contexts", {})
        if isinstance(bcs, dict):
            found.update(bcs.keys())
        elif isinstance(bcs, list):
            for item in bcs:
                if isinstance(item, dict) and "id" in item:
                    found.add(item["id"])

        if self.src_dir.is_dir():
            for child in self.src_dir.iterdir():
                if child.is_dir() and not child.name.startswith(".") and child.name not in EXCLUDE_DIRS:
                    found.add(child.name)
        return sorted(found)

    def _extract_forbidden_rules(self) -> dict[str, list[str]]:
        rules = {k: list(v) for k, v in DEFAULT_FORBIDDEN_RULES.items()}
        arch = self.toml_data.get("architecture", {})
        custom = arch.get("boundary_rules", arch.get("rules", {}))
        if isinstance(custom, dict):
            for k, val in custom.items():
                items = [val] if isinstance(val, str) else list(val)
                clean_k = k.replace(".*", "")
                rules.setdefault(clean_k, []).extend(items)
        return rules

    def _resolve_context(self, mod_or_path: str) -> str | None:
        clean = mod_or_path.replace("\\", "/").replace(".", "/")
        for ctx in self.contexts:
            if f"/{ctx}/" in f"/{clean}/" or clean.startswith(f"{ctx}/") or clean == ctx:
                return ctx
        return None

    def audit(self) -> SeamAuditReport:
        matrix: dict[str, dict[str, int]] = {c: {o: 0 for o in self.contexts} for c in self.contexts}
        violations: list[SeamViolation] = []

        # Find all python files
        py_files = [
            f for f in self.src_dir.rglob("*.py")
            if not any(part in EXCLUDE_DIRS or part.startswith(".") for part in f.relative_to(self.src_dir).parts)
        ]

        for pf in py_files:
            rel = pf.relative_to(self.root_dir)
            src_ctx = self._resolve_context(str(rel))
            if not src_ctx:
                continue

            try:
                rel_src = pf.relative_to(self.root_dir / "src")
                file_mod = ".".join(rel_src.with_suffix("").parts)
            except ValueError:
                file_mod = ".".join(rel.with_suffix("").parts)
            try:
                content = pf.read_text(encoding="utf-8")
            except OSError:
                continue

            imports = extract_python_imports_with_lines(content, file_module=file_mod)
            for imp, line_no in imports:
                tgt_ctx = self._resolve_context(imp)
                if not tgt_ctx or tgt_ctx == src_ctx:
                    continue

                matrix[src_ctx][tgt_ctx] = matrix[src_ctx].get(tgt_ctx, 0) + 1

                # Rule 1: Private internals import
                parts = imp.split(".")
                if any(p.startswith("_") or p == "internals" for p in parts):
                    violations.append(
                        SeamViolation(
                            source_file=str(rel), source_context=src_ctx,
                            imported_module=imp, target_context=tgt_ctx,
                            reason=f"Illegal direct import of private {tgt_ctx} internals", line=line_no,
                        )
                    )
                    continue

                # Rule 2: Domain model purity rule
                is_domain = "/domain/" in f"/{rel}/" or rel.name == "models.py"
                if is_domain and tgt_ctx in ("visualizer", "cli", "presentation", "infrastructure"):
                    violations.append(
                        SeamViolation(
                            source_file=str(rel), source_context=src_ctx,
                            imported_module=imp, target_context=tgt_ctx,
                            reason=f"Pure domain model cannot import '{tgt_ctx}' layer (ADR-0007)",
                            line=line_no,
                        )
                    )
                    continue

                # Rule 3: Configured boundary rules
                forb_list = self.forbidden_rules.get(src_ctx, [])
                if any(fnmatch.fnmatch(tgt_ctx, f) or fnmatch.fnmatch(imp, f) for f in forb_list):
                    violations.append(
                        SeamViolation(
                            source_file=str(rel), source_context=src_ctx,
                            imported_module=imp, target_context=tgt_ctx,
                            reason=f"Context '{src_ctx}' is forbidden from importing '{tgt_ctx}' (ADR-0007)",
                            line=line_no,
                        )
                    )

        # Compute metrics
        metrics: dict[str, ContextMetrics] = {}
        for c in self.contexts:
            outgoing = [tgt for tgt, cnt in matrix[c].items() if cnt > 0 and tgt != c]
            incoming = [src for src in self.contexts if matrix[src].get(c, 0) > 0 and src != c]
            ce = len(outgoing)
            ca = len(incoming)
            instability = calculate_instability(ca, ce)
            metrics[c] = ContextMetrics(
                context=c, afferent_coupling=ca, efferent_coupling=ce,
                instability=instability, incoming_contexts=incoming, outgoing_contexts=outgoing,
            )

        return SeamAuditReport(
            contexts=self.contexts, metrics=metrics, coupling_matrix=matrix, violations=violations,
        )


def export_coupling_heatmap(report: SeamAuditReport, dest_path: Path | str) -> Path:
    """Exports cross-context coupling matrix as Markdown, JSON, or HTML."""
    dest = Path(dest_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.suffix.lower() == ".json":
        dest.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        return dest

    if dest.suffix.lower() == ".html":
        rows = "".join(
            f"<tr><th>{c}</th>" + "".join(
                f"<td style='background-color:rgba(56,189,248,{min(1.0, report.coupling_matrix.get(c, {}).get(o, 0)*0.2):.2f})'>"
                f"{report.coupling_matrix.get(c, {}).get(o, 0)}</td>" for o in report.contexts
            ) + f"<td>{report.metrics.get(c, ContextMetrics(c)).instability:.2f}</td></tr>"
            for c in report.contexts
        )
        content = (
            f"<!DOCTYPE html><html><head><title>Coupling Heatmap</title></head><body>"
            f"<h2>Context Coupling Heatmap</h2><table border='1'>"
            f"<tr><th>From \\ To</th>{''.join(f'<th>{c}</th>' for c in report.contexts)}<th>I</th></tr>"
            f"{rows}</table></body></html>"
        )
        dest.write_text(content, encoding="utf-8")
        return dest

    # Markdown format
    headers = ["From \\ To"] + report.contexts + ["Ce", "Ca", "Instability"]
    sep = ["---"] * len(headers)
    table_lines = [f"| {' | '.join(headers)} |", f"| {' | '.join(sep)} |"]
    for c in report.contexts:
        m = report.metrics.get(c, ContextMetrics(c))
        vals = [str(report.coupling_matrix.get(c, {}).get(o, 0)) for o in report.contexts]
        row = [c] + vals + [str(m.efferent_coupling), str(m.afferent_coupling), f"{m.instability:.3f}"]
        table_lines.append(f"| {' | '.join(row)} |")

    dest.write_text("\n".join(table_lines) + "\n", encoding="utf-8")
    return dest


def handle_seam_audit(
    config: Any, strict: bool = False, json_output: bool = False, export_heatmap: str | None = None
) -> int:
    """CLI handler for 'spec-ops architecture seams'."""
    auditor = SeamAuditor(config.root_dir)
    report = auditor.audit()

    if export_heatmap:
        out_p = export_coupling_heatmap(report, export_heatmap)
        print(f"📊 Exported cross-context coupling heatmap to {out_p}")

    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if (report.is_valid or not strict) else 1

    print(report.format_text())
    if strict and not report.is_valid:
        return 1
    return 0
