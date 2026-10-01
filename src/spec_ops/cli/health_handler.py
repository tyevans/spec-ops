"""CLI handlers for repository health checks: invariants, modularity, numbering, and security."""

from __future__ import annotations

import argparse
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


def handle_health_numbering(config: SpecOpsConfig, json_output: bool = False) -> int:
    """Runs numbering uniqueness checks across ADRs, PRDs, Tasks, and User Stories."""
    import json
    from ..core.numbering import audit_numbering_uniqueness

    report = audit_numbering_uniqueness(config)
    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.format_diagnostics())
    return 0 if report.is_valid else 1


def handle_health_modularity(config: SpecOpsConfig, json_output: bool = False) -> int:
    """Computes modularity debt and source file growth telemetry."""
    import json
    from ..core.modularity_debt import ModularityDebtAnalyzer

    analyzer = ModularityDebtAnalyzer(config.root_dir)
    report = analyzer.analyze_directory(config.root_dir)
    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.summary())
    return 0


def handle_health_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Main entrypoint for spec-ops health CLI command."""
    from ..backlog.health import HealthChecker

    if getattr(args, "architecture", False):
        return handle_health_architecture(config)

    if getattr(args, "suggest_splits", False):
        return handle_health_suggest_splits(config, emit_task=getattr(args, "emit_task", False))

    if getattr(args, "generate_refactor_tasks", False):
        return handle_health_generate_refactor_tasks(config)

    if getattr(args, "check_uat", False):
        from ..prd.uat import handle_check_uat
        return handle_check_uat(config)

    if getattr(args, "numbering", False):
        return handle_health_numbering(config, json_output=getattr(args, "json", False))

    if getattr(args, "modularity", False):
        return handle_health_modularity(config, json_output=getattr(args, "json", False))

    checker = HealthChecker(config)
    report = checker.run_check()

    if getattr(args, "json", False):
        from .formatters import format_health_json
        print(format_health_json(report, config))
        return 0 if report.is_healthy else 1

    print(f"=== SpecOps Health Check ({config.project.name}) ===")
    print(f"Limit: <{config.architecture.file_length_limit} lines per file")
    if report.violations:
        print(f"❌ {len(report.violations)} File Length Violation(s):")
        for v in report.violations:
            print(f"File Length Violation: {v.path} ({v.lines} lines > {v.limit} line limit)")
            if getattr(v, "is_expanded", False):
                print(f"   {v.path}: {v.lines} lines (expanded beyond recorded baseline {v.limit} lines)")
            else:
                print(f"   {v.path}: {v.lines} lines (limit: {v.limit}) - unexempt file limit violation (>500 lines)")
    else:
        print("✅ Invariant Met: Zero source files exceed length limit.")

    if getattr(report, "grandfathered_debt", None):
        print(f"ℹ️ {len(report.grandfathered_debt)} grandfathered files remain tracked debt items.")

    if report.warnings:
        print(f"\n⚠️ {len(report.warnings)} Proactive Refactoring Warning(s) (approaching limit):")
        for w in report.warnings:
            print(f"⚠️ Proactive Refactoring Warning: {w.path} ({w.lines} lines >= {w.threshold} line warning threshold)")
            print(f"   {w.path}: {w.lines} lines (warning threshold: {w.threshold}, limit: {w.limit})")

    if getattr(report, "numbering_collisions", None):
        print(f"\n❌ {len(report.numbering_collisions)} Numbering Collision(s) Detected:")
        for col in report.numbering_collisions:
            print(f"   - Group '{col.group.upper()}': {col.canonical_id} duplicated across {len(col.paths)} files:")
            for p in col.paths:
                print(f"       • {p}")
    else:
        print("✅ Numbering Invariant Met: All ADR, PRD, Task, and User Story IDs are unique.")

    if report.constitution_drift_warnings:
        print(f"\n⚠️ {len(report.constitution_drift_warnings)} Constitution Drift Warning(s):")
        for cw in report.constitution_drift_warnings:
            print(f"   - {cw}")
    else:
        print("✅ 0 file limit violations (<500 lines) and 0 constitution drift warnings.")

    if getattr(report, "superseded_adr_warnings", None):
        print(f"\n⚠️ {len(report.superseded_adr_warnings)} Superseded ADR Warning(s):")
        for sw in report.superseded_adr_warnings:
            print(f"   - {sw}")

    print("\nBacklog State:")
    print(f"   Complete Tasks: {report.completed_tasks}")
    print(f"   Refined Buffer: {report.refined_tasks} ({report.buffer_status})")
    print(f"   Proposed Tasks: {report.proposed_tasks}")

    if not report.priority_sync_ok:
        print("❌ PRIORITY.md Sync Errors:")
        for err in report.sync_errors:
            print(f"   - {err}")
    else:
        print("✅ PRIORITY.md is synchronized with disk state.")

    if getattr(args, "security", False):
        has_sec = (
            config.security is not None
            or (config.root_dir / "docs" / "project" / "SECURITY.md").exists()
            or (
                (config.root_dir / "specops.toml").is_file()
                and "[security]" in (config.root_dir / "specops.toml").read_text(encoding="utf-8")
            )
        )
        if has_sec:
            sec_ok, sec_msg = checker.check_security_policy()
            if not sec_ok:
                print(f"❌ {sec_msg}")
                return 1
            print(f"✅ {sec_msg}")

        from ..security.secrets.scanner import scan_worktree

        scan_report = scan_worktree(config.root_dir)
        if not scan_report.is_clean:
            print(scan_report.format_diagnostics())
            return 1
        print("✅ Security Invariant Met: 0 credential leaks detected in working tree.")

    return 0 if report.is_healthy else 1
