"""Diataxis documentation drift auditor and validator for SpecOps."""

from __future__ import annotations

import argparse
from pathlib import Path

from .cli_inspector import check_cli_drift, extract_doc_commands, extract_parser_commands
from .models import (
    ALLOWED_ROOT_FILES,
    APPROVED_QUADRANTS,
    AuditReport,
    AuditViolation,
    ParsedCLICommand,
)
from .snippet_tester import check_code_snippets


def check_diataxis_structure(docs_dir: Path) -> tuple[list[AuditViolation], list[str]]:
    """Validates that all documentation files reside in approved Diataxis quadrants."""
    violations: list[AuditViolation] = []
    checked_quadrants = sorted(APPROVED_QUADRANTS)

    if not docs_dir.exists():
        violations.append(
            AuditViolation(
                category="structure",
                file_path=docs_dir,
                message=f"Documentation directory not found: {docs_dir}",
                severity="error",
            )
        )
        return violations, checked_quadrants

    # 1. Verify existence of required quadrants and ensure they contain markdown docs
    for quad in checked_quadrants:
        quad_dir = docs_dir / quad
        if not quad_dir.is_dir():
            violations.append(
                AuditViolation(
                    category="structure",
                    file_path=quad_dir,
                    message=f"Missing Diataxis quadrant directory: docs/{quad}/",
                    severity="error",
                )
            )
        else:
            md_files = list(quad_dir.rglob("*.md"))
            if not md_files:
                violations.append(
                    AuditViolation(
                        category="structure",
                        file_path=quad_dir,
                        message=f"Diataxis quadrant directory is empty: docs/{quad}/",
                        severity="error",
                    )
                )

    # 2. Check for configured allowed extra directories or root files
    extra_dirs: set[str] = set()
    extra_root: set[str] = set()
    toml_path = docs_dir.parent / "specops.toml"
    if toml_path.is_file():
        try:
            import sys
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib  # type: ignore
            with toml_path.open("rb") as f:
                tdata = tomllib.load(f)
            doc_cfg = tdata.get("documentation", {})
            extra_dirs = set(doc_cfg.get("allowed_directories", []))
            extra_root = set(doc_cfg.get("allowed_root_files", []))
        except Exception:
            pass

    # 3. Validate all files under docs_dir
    for path in sorted(docs_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(docs_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue

        if len(rel.parts) == 1:
            if rel.name not in ALLOWED_ROOT_FILES and rel.name not in extra_root:
                violations.append(
                    AuditViolation(
                        category="structure",
                        file_path=path,
                        message=(
                            f"File '{rel.as_posix()}' resides in docs root outside approved quadrants "
                            f"({', '.join(checked_quadrants)})"
                        ),
                        severity="error",
                    )
                )
        else:
            top_dir = rel.parts[0]
            if top_dir not in APPROVED_QUADRANTS and top_dir not in extra_dirs:
                violations.append(
                    AuditViolation(
                        category="structure",
                        file_path=path,
                        message=(
                            f"File '{rel.as_posix()}' resides in unapproved quadrant '{top_dir}' "
                            f"(approved quadrants: {', '.join(checked_quadrants)})"
                        ),
                        severity="error",
                    )
                )

    return violations, checked_quadrants


class DocsAuditor:
    """Orchestrates Diataxis structure validation, CLI drift checking, and snippet verification."""

    def __init__(
        self,
        docs_dir: Path,
        parser: argparse.ArgumentParser | None = None,
    ) -> None:
        self.docs_dir = docs_dir
        self.parser = parser

    def run_audit(self) -> AuditReport:
        """Executes all three Diataxis audit dimensions and returns a unified report."""
        report = AuditReport()

        struct_violations, checked_quads = check_diataxis_structure(self.docs_dir)
        report.violations.extend(struct_violations)
        report.quadrants_checked = checked_quads

        if self.parser is not None:
            cli_violations, cmd_count = check_cli_drift(self.docs_dir, self.parser)
            report.violations.extend(cli_violations)
            report.cli_commands_checked = cmd_count

        snippet_violations, snippet_count = check_code_snippets(self.docs_dir, self.parser)
        report.violations.extend(snippet_violations)
        report.snippets_checked = snippet_count

        return report

    def print_report(self, report: AuditReport) -> None:
        """Prints formatted audit diagnostics to stdout."""
        print("=== SpecOps Documentation Drift Audit ===")
        print(f"📁 Documentation Directory: {self.docs_dir}\n")

        struct_errors = [v for v in report.violations if v.category == "structure"]
        print("1. Diataxis Quadrant Structure:")
        if not struct_errors:
            print(f"   ✅ All {len(report.quadrants_checked)} approved quadrants verified: {', '.join(report.quadrants_checked)}")
            print("   ✅ All documentation files reside within approved quadrants")
        else:
            for v in struct_errors:
                print(f"   ❌ {v.message}")
        print()

        cli_errors = [v for v in report.violations if v.category == "cli_drift"]
        print("2. CLI Reference & Option Drift:")
        if not cli_errors:
            print(f"   ✅ docs/reference/cli.md matches CLI parser ({report.cli_commands_checked} commands verified)")
        else:
            for v in cli_errors:
                print(f"   ❌ {v.message}")
        print()

        snippet_errors = [v for v in report.violations if v.category == "snippet"]
        print("3. Code Snippet Verification:")
        if not snippet_errors:
            print(f"   ✅ {report.snippets_checked} code snippet(s) verified (syntax and CLI arguments)")
        else:
            for v in snippet_errors:
                print(f"   ❌ {v.message}")
        print()

        if report.is_clean:
            print(f"Status: ✅ CLEAN (0 errors, {len(report.warnings)} warnings)")
        else:
            print(f"Status: ❌ DRIFT DETECTED ({len(report.errors)} error(s), {len(report.warnings)} warning(s))")
