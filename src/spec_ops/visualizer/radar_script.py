"""Living architectural review radar and bounded context dependency auditor (US-0106)."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Sequence

from ..config.models import SpecOpsConfig
from ..core.models import ProjectData

_BUILTIN_STDLIB: set[str] = set(sys.builtin_module_names)
if hasattr(sys, "stdlib_module_names"):
    _BUILTIN_STDLIB.update(sys.stdlib_module_names)
else:
    _BUILTIN_STDLIB.update({
        "os", "sys", "re", "json", "ast", "math", "time", "datetime",
        "pathlib", "typing", "collections", "itertools", "functools",
        "subprocess", "hashlib", "io", "copy", "dataclasses", "unittest",
        "shutil", "tempfile", "traceback", "logging", "abc", "contextlib",
    })


def is_stdlib_module(module_name: str) -> bool:
    """Returns True if the given module name belongs to the Python standard library."""
    if not module_name:
        return False
    clean = module_name.replace("/", ".").strip()
    root_pkg = clean.split(".")[0].strip()
    return root_pkg in _BUILTIN_STDLIB


def _matches_pattern(module_name: str, pattern: str) -> bool:
    """Checks whether a module matches a given rule pattern (exact, prefix, or glob)."""
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return module_name == prefix or module_name.startswith(prefix + ".")
    return module_name == pattern or fnmatch.fnmatch(module_name, pattern)


def partition_acyclic_layers(graph: dict[str, Sequence[str] | set[str]]) -> list[list[str]]:
    """Partitions bounded contexts into acyclic topological layers, ignoring standard library imports."""
    clean_graph: dict[str, set[str]] = {}
    for u, targets in graph.items():
        if is_stdlib_module(u):
            continue
        clean_u = u.strip()
        if not clean_u:
            continue
        clean_targets = {
            v.strip() for v in targets
            if not is_stdlib_module(v) and v.strip() and v.strip() != clean_u
        }
        if clean_u not in clean_graph:
            clean_graph[clean_u] = set()
        clean_graph[clean_u].update(clean_targets)
        for v in clean_targets:
            if v not in clean_graph:
                clean_graph[v] = set()

    if not clean_graph:
        return []

    remaining: dict[str, set[str]] = {k: set(v) for k, v in clean_graph.items()}
    layers: list[list[str]] = []
    assigned: set[str] = set()

    while remaining:
        current_layer = [
            node for node, deps in remaining.items()
            if deps.issubset(assigned)
        ]
        if not current_layer:
            layers.append(sorted(remaining.keys()))
            break

        current_layer.sort()
        layers.append(current_layer)
        for node in current_layer:
            assigned.add(node)
            del remaining[node]

    return layers


@dataclass
class BoundaryViolation:
    """Represents an illegal cross-context module import or architectural seam violation."""

    source: str
    target: str
    violation_type: str  # "forbidden_import", "unauthorized_import", "backward_dependency", "domain_leak"
    message: str
    file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.violation_type,
            "message": self.message,
            "file_path": self.file_path,
        }


def detect_boundary_violations(
    deps: dict[str, Sequence[str] | set[str]],
    layers: Sequence[Sequence[str]] | None = None,
    forbidden_rules: dict[str, Sequence[str] | set[str]] | None = None,
    permissible_rules: dict[str, Sequence[str] | set[str]] | None = None,
    file_paths: dict[tuple[str, str], str] | None = None,
) -> list[BoundaryViolation]:
    """Evaluates cross-context dependencies against boundary rules, layer ordering, and domain purity."""
    violations: list[BoundaryViolation] = []
    node_to_layer: dict[str, int] = {}
    if layers:
        for idx, layer_nodes in enumerate(layers):
            for node in layer_nodes:
                node_to_layer[node] = idx

    for source, targets in sorted(deps.items()):
        if is_stdlib_module(source):
            continue
        for target in sorted(targets):
            if is_stdlib_module(target) or source == target:
                continue

            file_path = (file_paths or {}).get((source, target), "")

            if forbidden_rules and source in forbidden_rules:
                if any(_matches_pattern(target, forb) for forb in forbidden_rules[source]):
                    violations.append(
                        BoundaryViolation(
                            source=source,
                            target=target,
                            violation_type="forbidden_import",
                            message=f"Illegal cross-context import: {source} cannot import forbidden {target}",
                            file_path=file_path,
                        )
                    )
                    continue

            if permissible_rules and source in permissible_rules:
                if not any(_matches_pattern(target, perm) for perm in permissible_rules[source]):
                    violations.append(
                        BoundaryViolation(
                            source=source,
                            target=target,
                            violation_type="unauthorized_import",
                            message=f"Unauthorized import: {source} is not permitted to import {target}",
                            file_path=file_path,
                        )
                    )
                    continue

            is_source_domain = ".domain" in source or "/domain" in source or source.endswith(".domain")
            is_target_infra = ".infrastructure" in target or "/infrastructure" in target or target.endswith(".infrastructure")
            if is_source_domain and is_target_infra:
                violations.append(
                    BoundaryViolation(
                        source=source,
                        target=target,
                        violation_type="domain_leak",
                        message=f"Domain layer leak: {source} cannot import external infrastructure {target}",
                        file_path=file_path,
                    )
                )
                continue

            if layers and source in node_to_layer and target in node_to_layer:
                src_layer = node_to_layer[source]
                tgt_layer = node_to_layer[target]
                if src_layer < tgt_layer:
                    violations.append(
                        BoundaryViolation(
                            source=source,
                            target=target,
                            violation_type="backward_dependency",
                            message=f"Illegal backward dependency violating ADR-0007: {source} (layer {src_layer}) cannot depend on higher layer {target} (layer {tgt_layer})",
                            file_path=file_path,
                        )
                    )

    return violations


def harvest_architecture_radar(config: SpecOpsConfig, data: ProjectData | None = None) -> dict[str, Any]:
    """Harvests coupling matrices, boundary violations, ADR supersessions, and spec drift."""
    from ..adrs.supersede import discover_superseded_adrs, find_tasks_citing_adr
    from ..core.arch_checker import ArchitectureChecker

    checker = ArchitectureChecker(config.root_dir)
    arch_report = checker.check()

    bcs = sorted(checker.bounded_contexts)
    adrs_dir = config.project_docs_dir / "adrs"
    backlog_dir = config.backlog_dir

    superseded_map = discover_superseded_adrs(adrs_dir) if adrs_dir.exists() else {}
    obsolete_citations: list[dict[str, str]] = []
    if backlog_dir.exists():
        for old_id in sorted(superseded_map.keys()):
            for tid in find_tasks_citing_adr(backlog_dir, old_id):
                obsolete_citations.append({"task_id": tid, "adr_id": old_id})

    # Harvest context dependencies
    context_deps: dict[str, set[str]] = {bc: set() for bc in bcs}
    file_paths: dict[tuple[str, str], str] = {}
    src_dir = config.root_dir / "src"
    if src_dir.is_dir():
        from ..core.arch_checker import get_module_for_file, parse_python_imports
        for p in src_dir.rglob("*.py"):
            if not p.is_file():
                continue
            rel = p.relative_to(config.root_dir)
            file_mod = get_module_for_file(rel)
            file_ctx = checker._determine_context(file_mod)
            if not file_ctx:
                continue
            try:
                code = p.read_text(encoding="utf-8", errors="ignore")
                for imp in parse_python_imports(code, file_mod):
                    imp_ctx = checker._determine_context(imp)
                    if imp_ctx and imp_ctx != file_ctx:
                        context_deps[file_ctx].add(imp_ctx)
                        file_paths[(file_ctx, imp_ctx)] = str(rel).replace("\\", "/")
            except OSError:
                continue

    layers = partition_acyclic_layers(context_deps)
    forbidden_rules: dict[str, list[str]] = {}
    for src_pat, forb_list, _ in checker.rules:
        prefix = src_pat.replace(".*", "")
        forbidden_rules.setdefault(prefix, []).extend(forb_list)

    violations = detect_boundary_violations(
        context_deps,
        layers=layers,
        forbidden_rules=forbidden_rules,
        file_paths=file_paths,
    )

    # Coupling matrix
    coupling_matrix = []
    for src in bcs:
        for tgt in bcs:
            if src == tgt:
                continue
            count = 1 if tgt in context_deps.get(src, set()) else 0
            is_prohibited = any(v.source == src and v.target == tgt for v in violations)
            coupling_matrix.append({
                "from_bc": src,
                "to_bc": tgt,
                "count": count,
                "is_prohibited": is_prohibited,
                "status": "prohibited" if is_prohibited else "permissible",
            })

    # Specification drift audit
    tasks = data.tasks if data else []
    stories = data.stories if data else []
    prds = data.prds if data else []

    orphaned_tasks = [
        {"id": t.canonical_id, "title": t.title, "file_path": str(t.file_path)}
        for t in tasks
        if not t.governing_prds and not t.governing_stories
    ]
    orphaned_stories = [
        {"id": s.id, "title": s.title, "file_path": str(s.file_path)}
        for s in stories
        if not s.governing_prd
    ]
    orphaned_prds = [
        {"id": p.id, "title": p.title, "file_path": str(p.file_path)}
        for p in prds
        if not p.implementing_tasks
    ]

    drift_audit = {
        "orphaned_tasks": orphaned_tasks,
        "orphaned_stories": orphaned_stories,
        "orphaned_prds": orphaned_prds,
        "orphaned_commits": [],
        "total_orphans": len(orphaned_tasks) + len(orphaned_stories) + len(orphaned_prds),
    }

    return {
        "bounded_contexts": bcs,
        "layers": layers,
        "coupling_matrix": coupling_matrix,
        "violations": [v.to_dict() for v in violations],
        "obsolete_citations": obsolete_citations,
        "superseded_map": superseded_map,
        "drift_audit": drift_audit,
    }


def export_specification_drift_report(
    config: SpecOpsConfig,
    output_path: str | Path = "dist/spec-drift-audit.json",
) -> Path:
    """Exports specification drift audit report to the requested json file."""
    data = harvest_architecture_radar(config)
    report_dict = data.get("drift_audit", {})
    report_dict["timestamp"] = "2026-09-30T12:00:00Z"

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    return out


_RADAR_JS_PATH = Path(__file__).parent / "templates" / "radar.js"
RADAR_JS = _RADAR_JS_PATH.read_text(encoding="utf-8") if _RADAR_JS_PATH.is_file() else ""
