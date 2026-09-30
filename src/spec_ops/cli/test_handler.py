"""CLI command handler for test quality gates, anti-mock audit, and frontdoor verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.anti_mock import audit_test_suite


def handle_mutation_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Executes 'spec-ops test mutation' quality gate command."""
    from ..core.mutation_gate import run_mutation_gate

    target = getattr(args, "opt_path", None) or getattr(args, "path", None)
    bc = getattr(args, "target_bc", "core")
    threshold = getattr(args, "threshold", 80.0)
    as_json = getattr(args, "json", False)
    force_run = getattr(args, "force_run", False)

    report = run_mutation_gate(
        root_dir=config.root_dir,
        target_module=target,
        bounded_context=bc,
        threshold=threshold,
        force_run=force_run,
    )

    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.is_passed else 1

    output = report.format_report()
    if report.is_passed:
        print(output)
        return 0

    print(output, file=sys.stderr)
    return 1


def handle_test_command(
    args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser
) -> int:
    """Executes 'spec-ops test' subcommands (audit-anti-mock, verify-frontdoors, properties, mutation)."""
    action = getattr(args, "test_action", None)
    if action in ("properties", "invariants"):
        from ..core.properties_runner import handle_properties_command
        return handle_properties_command(args, config)

    if action == "mutation":
        return handle_mutation_command(args, config)

    if not action or action not in ("audit-anti-mock", "verify-frontdoors"):
        parser.parse_args(["test", "--help"])
        return 0

    target = getattr(args, "opt_path", None) or getattr(args, "path", None)
    strict_mutation = getattr(args, "strict_mutation", False)
    threshold = getattr(args, "threshold", 80.0)
    as_json = getattr(args, "json", False)

    report = audit_test_suite(
        target_path=target,
        root_dir=config.root_dir,
        strict_mutation=strict_mutation,
        mutation_threshold=threshold,
    )

    if as_json:
        payload = {
            "is_clean": report.is_clean,
            "scanned_files": report.scanned_files,
            "violations_count": len(report.violations),
            "mutation_score": report.mutation_score,
            "surviving_mutants": report.surviving_mutants,
            "violations": [
                {
                    "file_path": v.file_path,
                    "line": v.line,
                    "column": v.column,
                    "rule": v.rule,
                    "message": v.message,
                    "snippet": v.snippet,
                }
                for v in report.violations
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0 if report.is_clean else 1

    output = report.format_output()
    if report.is_clean:
        print(f"✨ {output}")
        return 0

    print(output, file=sys.stderr)
    return 1
