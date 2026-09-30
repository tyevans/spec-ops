"""Static bounded context boundary and dependency direction enforcement."""

from __future__ import annotations

import ast
import fnmatch
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "site",
    "__pycache__",
    ".pytest_cache",
    ".worktrees",
}


@dataclass
class ArchitectureViolation:
    file_path: str
    imported_module: str
    rule_description: str
    is_domain_leak: bool = False

    def format_message(self) -> str:
        if self.is_domain_leak:
            return (
                f"{self.file_path}\n"
                f"Architecture Invariant Violated: Domain layer cannot import external infrastructure '{self.imported_module}'"
            )
        return (
            f"{self.file_path}\n"
            f"Architecture Invariant Violated: Forbidden import '{self.imported_module}' ({self.rule_description})"
        )


@dataclass
class ArchitectureReport:
    violations: list[ArchitectureViolation] = field(default_factory=list)
    cycles: list[str] = field(default_factory=list)
    contexts_scanned: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0 and len(self.cycles) == 0

    def format_output(self) -> str:
        if self.is_valid:
            return "Invariant Met: Bounded context boundary rules validated with 0 violations. Clean boundary separation verified with 0 illegal cross-context imports."

        lines: list[str] = []
        for v in self.violations:
            lines.append(v.format_message())
        for c in self.cycles:
            lines.append(f"Cyclic Architecture Dependency Detected: {c}")
        return "\n".join(lines)


def parse_python_imports(source_code: str, file_module: str = "") -> list[str]:
    """Extracts all imported module names from Python source code."""
    imported: list[str] = []
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return imported

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level > 0:
                # Relative import resolution
                parts = file_module.split(".") if file_module else []
                base_parts = parts[:-node.level] if len(parts) >= node.level else []
                full_mod = ".".join(base_parts + ([mod] if mod else []))
                imported.append(full_mod)
            else:
                imported.append(mod)
    return imported


def parse_ts_imports(source_code: str, file_path: str = "") -> list[str]:
    """Extracts imported modules from TypeScript/JavaScript files."""
    imported: list[str] = []
    pattern = re.compile(r"""(?:import\s+.*?\s+from\s+|require\(\s*)['"]([^'"]+)['"]""")
    for m in pattern.finditer(source_code):
        raw = m.group(1).replace("/", ".").lstrip(".")
        if raw.startswith("src."):
            raw = raw[4:]
        imported.append(raw)
    return imported


def get_module_for_file(rel_path: str | Path) -> str:
    """Converts a relative file path to its dot-separated module representation."""
    p = Path(rel_path)
    parts = list(p.with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def matches_rule(imported: str, pattern: str) -> bool:
    """Checks if imported module matches a glob or prefix rule pattern."""
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return imported == prefix or imported.startswith(prefix + ".")
    return imported == pattern or fnmatch.fnmatch(imported, pattern)


class ArchitectureChecker:
    """Validates bounded context boundaries, DDD layering, and dependency acyclicity."""

    def __init__(self, root_dir: Path, toml_data: dict[str, Any] | None = None):
        self.root_dir = root_dir.resolve()
        self.toml_data = toml_data or self._load_toml()
        self.bounded_contexts = self._discover_bounded_contexts()
        self.rules = self._extract_rules()

    def _load_toml(self) -> dict[str, Any]:
        toml_path = self.root_dir / "specops.toml"
        if not toml_path.is_file():
            return {}
        try:
            with toml_path.open("rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    def _discover_bounded_contexts(self) -> list[str]:
        contexts: set[str] = set()

        # 1. Check specops.toml
        arch = self.toml_data.get("architecture", {})
        bc_table = arch.get("bounded_contexts", self.toml_data.get("bounded_contexts", {}))
        if isinstance(bc_table, dict):
            for k in bc_table.keys():
                contexts.add(k)
        elif isinstance(bc_table, list):
            for item in bc_table:
                if isinstance(item, dict) and "id" in item:
                    contexts.add(item["id"])

        for comp in arch.get("components", []):
            if isinstance(comp, dict) and "id" in comp and comp["id"] != "core":
                contexts.add(comp["id"])

        # 2. Check src/ directory structure
        src_dir = self.root_dir / "src"
        if src_dir.is_dir():
            for child in src_dir.iterdir():
                if child.is_dir() and not child.name.startswith(".") and child.name not in EXCLUDE_DIRS:
                    contexts.add(child.name)

        return sorted(contexts)

    def _extract_rules(self) -> list[tuple[str, list[str], str]]:
        """Extracts (source_pattern, forbidden_patterns, description) tuples."""
        rules: list[tuple[str, list[str], str]] = []
        arch = self.toml_data.get("architecture", {})

        # 1. architecture.boundary_rules or architecture.rules
        b_rules = arch.get("boundary_rules", arch.get("rules", {}))
        if isinstance(b_rules, dict):
            for src_pattern, forbidden in b_rules.items():
                forb_list = [forbidden] if isinstance(forbidden, str) else list(forbidden)
                rules.append((src_pattern, forb_list, f"Rule: {src_pattern} cannot import {forb_list}"))

        # 2. architecture.bounded_contexts.<name>.forbidden_imports
        bc_table = arch.get("bounded_contexts", {})
        if isinstance(bc_table, dict):
            for bc_name, bc_cfg in bc_table.items():
                if isinstance(bc_cfg, dict):
                    forb = bc_cfg.get("forbidden_imports", [])
                    if forb:
                        forb_list = [forb] if isinstance(forb, str) else list(forb)
                        rules.append((f"{bc_name}.*", forb_list, f"Context {bc_name} forbidden imports"))
                    rules_sub = bc_cfg.get("rules", {})
                    if isinstance(rules_sub, dict):
                        for src_pattern, f_list in rules_sub.items():
                            f_items = [f_list] if isinstance(f_list, str) else list(f_list)
                            rules.append((src_pattern, f_items, f"Rule: {src_pattern} cannot import {f_items}"))

        return rules

    def _determine_context(self, module_name: str) -> str | None:
        """Determines which bounded context a module belongs to."""
        parts = module_name.split(".")
        for part in parts:
            if part in self.bounded_contexts:
                return part
        return None

    def check(self) -> ArchitectureReport:
        violations: list[ArchitectureViolation] = []
        context_deps: dict[str, set[str]] = {ctx: set() for ctx in self.bounded_contexts}

        for path in self.root_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root_dir)
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue
            if path.suffix not in (".py", ".ts", ".tsx", ".js", ".jsx"):
                continue

            rel_str = str(rel).replace("\\", "/")
            file_mod = get_module_for_file(rel)
            file_ctx = self._determine_context(file_mod)

            try:
                code = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            imports = (
                parse_ts_imports(code, rel_str)
                if path.suffix in (".ts", ".tsx", ".js", ".jsx")
                else parse_python_imports(code, file_mod)
            )

            for imp in imports:
                imp_ctx = self._determine_context(imp)
                if file_ctx and imp_ctx and file_ctx != imp_ctx:
                    context_deps[file_ctx].add(imp_ctx)

                # Check DDD domain purity rule:
                # Domain layer cannot import external infrastructure
                is_domain_file = ".domain." in f".{file_mod}." or "/domain/" in f"/{rel_str}/"
                is_external_infra = ".infrastructure" in imp or "/infrastructure" in imp
                if is_domain_file and is_external_infra:
                    # External if from another context or explicitly flagged
                    if imp_ctx != file_ctx or (imp_ctx and imp_ctx != file_ctx):
                        violations.append(
                            ArchitectureViolation(
                                file_path=rel_str,
                                imported_module=imp,
                                rule_description="Domain layer cannot import external infrastructure",
                                is_domain_leak=True,
                            )
                        )
                        continue

                # Check configured boundary rules
                for src_pattern, forbidden_list, desc in self.rules:
                    if matches_rule(file_mod, src_pattern) or matches_rule(rel_str, src_pattern):
                        for forb in forbidden_list:
                            if matches_rule(imp, forb):
                                violations.append(
                                    ArchitectureViolation(
                                        file_path=rel_str,
                                        imported_module=imp,
                                        rule_description=desc,
                                        is_domain_leak=is_domain_file and is_external_infra,
                                    )
                                )
                                break

        # Check cyclic dependencies between contexts
        cycles: list[str] = []
        reported_pairs: set[tuple[str, str]] = set()

        for c1, deps in context_deps.items():
            for c2 in deps:
                if c1 in context_deps.get(c2, set()):
                    pair = tuple(sorted([c1, c2]))
                    if pair not in reported_pairs:
                        reported_pairs.add(pair)
                        cycles.append(f"{pair[0]} <-> {pair[1]}")

        return ArchitectureReport(
            violations=violations,
            cycles=cycles,
            contexts_scanned=self.bounded_contexts,
        )
