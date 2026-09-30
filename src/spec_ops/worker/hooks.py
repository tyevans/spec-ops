"""Local pre-commit and git hook evaluators for SpecOps invariants."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..backlog.health import HealthChecker, HealthCheckReport
from ..config.loader import load_config
from ..config.models import SpecOpsConfig


@dataclass
class HookEvaluationResult:
    """Outcome of a git hook health evaluation."""

    success: bool
    exit_code: int
    output: str
    violations_count: int = 0
    warnings_count: int = 0


class PreCommitHookEvaluator:
    """Evaluates local pre-commit hooks enforcing hard file limits and PRIORITY.md sync."""

    def __init__(self, root_dir: Path | None = None, config: SpecOpsConfig | None = None):
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.config = config or load_config(root_dir=self.root_dir)
        self.checker = HealthChecker(self.config)

    def evaluate(self) -> HookEvaluationResult:
        """Evaluates health invariants and returns a HookEvaluationResult."""
        report = self.checker.run_check()

        output_lines: list[str] = [
            f"=== SpecOps Pre-Commit Health Gate ({self.config.project.name}) ===",
            f"Limit: <{self.config.architecture.file_length_limit} lines per file",
        ]

        # File length violations (>500 lines)
        if report.violations:
            output_lines.append(f"❌ {len(report.violations)} File Length Violation(s):")
            for v in report.violations:
                output_lines.append(
                    f"File Length Violation: {v.path} ({v.lines} lines > {v.limit} line limit)"
                )
                output_lines.append(f"   Violation on line {v.lines}: {v.path} ({v.lines} lines > {v.limit} line limit)")
        else:
            output_lines.append("✅ Invariant Met: Zero source files exceed length limit.")

        # File length warnings (>=400 lines)
        if report.warnings:
            output_lines.append(
                f"\n⚠️ {len(report.warnings)} Proactive Refactoring Warning(s) (approaching limit):"
            )
            for w in report.warnings:
                output_lines.append(
                    f"⚠️ Proactive Refactoring Warning: {w.path} ({w.lines} lines >= {w.threshold} line warning threshold)"
                )

        # PRIORITY.md sync check
        if not report.priority_sync_ok:
            output_lines.append("\n❌ PRIORITY.md Sync Errors:")
            for err in report.sync_errors:
                output_lines.append(f"   - {err}")
        else:
            output_lines.append("✅ PRIORITY.md is synchronized with disk state.")

        output = "\n".join(output_lines)
        exit_code = 0 if report.is_healthy else 1
        return HookEvaluationResult(
            success=report.is_healthy,
            exit_code=exit_code,
            output=output,
            violations_count=len(report.violations),
            warnings_count=len(report.warnings),
        )


def install_pre_commit_hook(repo_root: Path) -> Path:
    """Installs native git pre-commit hook enforcing SpecOps health invariants."""
    from ..scaffold.native_hooks import install_native_hooks

    pre_commit, _ = install_native_hooks(repo_root, force=True)
    return pre_commit


def run_spec_ops_health_hook(repo_root: Path | None = None) -> HookEvaluationResult:
    """Runs the health hook evaluator on the repository."""
    evaluator = PreCommitHookEvaluator(root_dir=repo_root)
    return evaluator.evaluate()
