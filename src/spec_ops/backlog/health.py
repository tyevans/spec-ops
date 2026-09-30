"""Health checker for repository invariants, file lengths, and backlog buffers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "site",
    "storybook-static",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "mutants",
    ".mutmut-cache",
    ".hypothesis",
    ".worktrees",
}


SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".js",
    ".html",
    ".css",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    ".c",
    ".h",
}


@dataclass
class FileLengthViolation:
    path: Path
    lines: int
    limit: int
    is_expanded: bool = False
    is_unexempt: bool = True


@dataclass
class FileLengthWarning:
    path: Path
    lines: int
    threshold: int
    limit: int


@dataclass
class HealthCheckReport:
    violations: list[FileLengthViolation] = field(default_factory=list)
    warnings: list[FileLengthWarning] = field(default_factory=list)
    grandfathered_debt: list[tuple[Path, int, int]] = field(default_factory=list)
    top_largest_files: list[tuple[int, Path]] = field(default_factory=list)
    completed_tasks: int = 0
    refined_tasks: int = 0
    proposed_tasks: int = 0
    buffer_status: str = "OPTIMAL"
    priority_sync_ok: bool = True
    sync_errors: list[str] = field(default_factory=list)
    constitution_drift_warnings: list[str] = field(default_factory=list)
    superseded_adr_warnings: list[str] = field(default_factory=list)
    numbering_collisions: list[Any] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return (
            len(self.violations) == 0
            and self.priority_sync_ok
            and len(self.constitution_drift_warnings) == 0
            and len(self.numbering_collisions) == 0
        )


class HealthChecker:
    """Evaluates repository health against SpecOps invariants."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.root_dir = config.root_dir
        self.limit = config.architecture.file_length_limit
        self.warning_threshold = config.architecture.file_warning_threshold
        self.backlog_dir = config.backlog_dir
        self.tracked_debt: list[tuple[Path, int, int]] = []

    def scan_file_lengths(self) -> tuple[list[FileLengthViolation], list[FileLengthWarning], list[tuple[int, Path]]]:
        from ..core.debt_baseline import evaluate_file_debt, load_grandfathered_debt

        violations: list[FileLengthViolation] = []
        warnings: list[FileLengthWarning] = []
        all_files: list[tuple[int, Path]] = []
        self.tracked_debt = []

        baseline = load_grandfathered_debt(self.root_dir)

        for p in self.root_dir.rglob("*"):
            if not p.is_file():
                continue
            rel_path = p.relative_to(self.root_dir)
            if any(part in EXCLUDE_DIRS for part in rel_path.parts):
                continue
            if p.suffix not in SOURCE_EXTENSIONS:
                continue

            try:
                line_count = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                all_files.append((line_count, rel_path))
                eval_res = evaluate_file_debt(rel_path, line_count, baseline, self.limit)

                if eval_res.status == "grandfathered":
                    self.tracked_debt.append((rel_path, line_count, eval_res.baseline_lines or self.limit))
                elif eval_res.status == "expanded":
                    violations.append(
                        FileLengthViolation(
                            rel_path,
                            line_count,
                            eval_res.baseline_lines or self.limit,
                            is_expanded=True,
                            is_unexempt=False,
                        )
                    )
                elif eval_res.status == "unexempt":
                    violations.append(
                        FileLengthViolation(
                            rel_path,
                            line_count,
                            self.limit,
                            is_expanded=False,
                            is_unexempt=True,
                        )
                    )
                elif line_count >= self.warning_threshold:
                    warnings.append(FileLengthWarning(rel_path, line_count, self.warning_threshold, self.limit))
            except (OSError, UnicodeDecodeError):
                continue

        all_files.sort(key=lambda x: x[0], reverse=True)
        return violations, warnings, all_files[:10]

    def check_priority_sync(self) -> tuple[bool, list[str]]:
        priority_file = self.backlog_dir / "PRIORITY.md"
        if not priority_file.exists():
            return True, []

        content = priority_file.read_text(encoding="utf-8")
        errors: list[str] = []

        for folder_name in ["complete", "refined", "proposed"]:
            folder = self.backlog_dir / folder_name
            if not folder.exists():
                continue
            for p in folder.glob("*.md"):
                if p.name.startswith("."):
                    continue
                m = re.match(r"^(\d+)", p.stem)
                if not m:
                    continue
                cid = f"TASK-{m.group(1).zfill(4)}"
                expected_tag = folder_name.capitalize()
                # Check line in priority file
                pattern = rf"\*\*{cid}\s*\(([^)]+)\)\*\*:\s*\[`?[^`\]]+`?\]\(([^/]+)/"
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    found_status = match.group(1).strip()
                    found_folder = match.group(2).strip()
                    if found_folder != folder_name and not (folder_name == "refined" and found_status in ("In-Progress", "Review")):
                        errors.append(f"{cid} is in {folder_name}/ on disk but referenced as {found_folder}/ in PRIORITY.md")

        return len(errors) == 0, errors

    def check_constitution(self) -> list[str]:
        agents_md = self.root_dir / "AGENTS.md"
        if not agents_md.exists():
            return ["AGENTS.md is missing. Run 'spec-ops scaffold agents' to restore."]

        warnings: list[str] = []
        content = agents_md.read_text(encoding="utf-8")

        has_security = (
            self.config.security is not None
            or (self.root_dir / "docs" / "project" / "SECURITY.md").exists()
        )
        if not has_security:
            toml_path = self.root_dir / "specops.toml"
            if toml_path.exists() and "[security]" in toml_path.read_text(encoding="utf-8"):
                has_security = True

        if has_security:
            if "Security & Supply-Chain Hard Invariants" not in content and "Security & Supply-Chain Invariants" not in content:
                warnings.append("AGENTS.md is missing Security & Supply-Chain Hard Invariants. Run 'spec-ops scaffold agents' to update.")

        return warnings

    def check_security_policy(self) -> tuple[bool, str]:
        from ..profiles.security import validate_security_policy

        return validate_security_policy(self.root_dir)

    def check_superseded_adrs(self) -> list[str]:
        from ..adrs.supersede import discover_superseded_adrs, find_tasks_citing_adr

        adrs_dir = self.root_dir / "docs" / "project" / "adrs"
        superseded_map = discover_superseded_adrs(adrs_dir)
        if not superseded_map:
            return []

        warnings: list[str] = []
        for old_id in sorted(superseded_map.keys()):
            citing_tasks = find_tasks_citing_adr(self.backlog_dir, old_id)
            for tid in sorted(citing_tasks):
                msg = f"Task {tid} cites superseded {old_id}; requires architectural re-refinement"
                if msg not in warnings:
                    warnings.append(msg)
        return warnings

    def check_numbering(self) -> list[Any]:
        from ..core.numbering import audit_numbering_uniqueness

        report = audit_numbering_uniqueness(self.config)
        return report.collisions

    def run_check(self) -> HealthCheckReport:
        violations, warnings, top_files = self.scan_file_lengths()
        sync_ok, sync_errors = self.check_priority_sync()
        constitution_warnings = self.check_constitution()
        superseded_adr_warnings = self.check_superseded_adrs()
        numbering_collisions = self.check_numbering()

        complete_count = 0
        refined_count = 0
        proposed_count = 0

        if self.backlog_dir.exists():
            for folder, name in [("complete", "c"), ("refined", "r"), ("proposed", "p")]:
                fpath = self.backlog_dir / folder
                if fpath.exists():
                    count = len([x for x in fpath.glob("*.md") if not x.name.startswith(".")])
                    if name == "c":
                        complete_count = count
                    elif name == "r":
                        refined_count = count
                    elif name == "p":
                        proposed_count = count

        target = self.config.architecture.buffer_target
        threshold = self.config.architecture.buffer_warning_threshold
        buffer_status = "OPTIMAL"
        if refined_count < threshold:
            buffer_status = "UNDER_BUFFERED"
        elif refined_count > target * 2:
            buffer_status = "OVER_BUFFERED"

        return HealthCheckReport(
            violations=violations,
            warnings=warnings,
            grandfathered_debt=self.tracked_debt,
            top_largest_files=top_files,
            completed_tasks=complete_count,
            refined_tasks=refined_count,
            proposed_tasks=proposed_count,
            buffer_status=buffer_status,
            priority_sync_ok=sync_ok,
            sync_errors=sync_errors,
            constitution_drift_warnings=constitution_warnings,
            superseded_adr_warnings=superseded_adr_warnings,
            numbering_collisions=numbering_collisions,
        )
