"""Modularity debt scoring and source file growth proactive telemetry engine.

Fulfills ADR-0002, PRD-0005, and US-0017 by calculating modularity decay risk scores,
identifying danger zone files approaching warning thresholds (350-399 lines),
and providing proactive decomposition telemetry before hard 500-line invariant failures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .debt_baseline import EXCLUDE_DIRS, SOURCE_EXTENSIONS, is_excluded_path


def count_file_lines(file_path: Path) -> int:
    """Counts non-empty or total lines in a source file safely."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return len(content.splitlines())
    except (OSError, UnicodeDecodeError):
        return 0


def count_file_imports(file_path: Path) -> int:
    """Counts import declarations in source files using AST or regex fallback."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        if file_path.suffix == ".py":
            try:
                tree = ast.parse(content)
                count = 0
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        count += 1
                return count
            except SyntaxError:
                pass

        count = 0
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) or "require(" in stripped:
                count += 1
        return count
    except (OSError, UnicodeDecodeError):
        return 0


def determine_risk_level(score: float, line_count: int) -> str:
    """Maps risk score and line count to risk level category."""
    if line_count >= 400 or score >= 85.0:
        return "critical"
    if line_count >= 350 or score >= 70.0:
        return "high"
    if line_count >= 200 or score >= 40.0:
        return "moderate"
    return "low"


def get_recommended_action(risk_level: str, line_count: int) -> str:
    """Generates actionable decomposition guidance based on risk level."""
    if risk_level == "critical":
        return (
            "Urgent decomposition required: file exceeds 400-line warning threshold. "
            "Decompose immediately before 500-line hard failure."
        )
    if risk_level == "high":
        return (
            "Proactive decomposition recommended: file is in danger zone (approaching 400-line warning threshold). "
            "Split into cohesive submodules."
        )
    if risk_level == "moderate":
        return "Monitor file growth; keep responsibilities cohesive."
    return "Optimal modularity; maintain current structure."


@dataclass
class FileModularityScore:
    """Telemetry risk scoring for an individual project source file."""

    file_path: str
    line_count: int
    risk_score: float
    risk_level: str
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_count": self.line_count,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "recommended_action": self.recommended_action,
        }


@dataclass
class ModularityReport:
    """Project-wide modularity debt and file growth report."""

    files: list[FileModularityScore] = field(default_factory=list)
    overall_debt_score: float = 0.0
    danger_zone_files: list[FileModularityScore] = field(default_factory=list)

    def summary(self) -> str:
        """Renders human-readable summary of modularity health."""
        lines = [
            "=== SpecOps Modularity Debt Report ===",
            f"Overall Modularity Debt Score: {self.overall_debt_score:.1f} / 100.0",
            f"Total Files Analyzed: {len(self.files)}",
            f"Danger Zone Files (approaching 400 lines): {len(self.danger_zone_files)}",
        ]

        if self.danger_zone_files:
            lines.append("\n⚠️ Danger Zone Files (Approaching 400-Line Warning Threshold):")
            for f in self.danger_zone_files:
                lines.append(
                    f"   - {f.file_path}: {f.line_count} lines (Risk: {f.risk_level.upper()}, Score: {f.risk_score})"
                )
                lines.append(f"     Proactive decomposition warning: {f.recommended_action}")
        else:
            lines.append("\n✅ 0 proactive warnings; codebase modularity optimal")

        if self.files:
            lines.append("\nTop Modularity Risk Files:")
            sorted_files = sorted(self.files, key=lambda x: x.risk_score, reverse=True)
            for f in sorted_files[:10]:
                lines.append(
                    f"   • {f.file_path} ({f.line_count} lines, Score: {f.risk_score}, Risk: {f.risk_level.upper()}) - {f.recommended_action}"
                )

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serializes modularity report to dictionary."""
        return {
            "overall_debt_score": self.overall_debt_score,
            "total_files": len(self.files),
            "danger_zone_count": len(self.danger_zone_files),
            "files": [f.to_dict() for f in self.files],
            "danger_zone_files": [f.to_dict() for f in self.danger_zone_files],
        }


class ModularityDebtAnalyzer:
    """Analyzes source file line counts, import coupling, and modularity decay risk."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir

    @staticmethod
    def calculate_file_score(line_count: int, imports_count: int = 0) -> float:
        """Calculates modularity risk score bounded in [0.0, 100.0] scaling monotonically with line count."""
        if line_count <= 0:
            return 0.0

        if line_count < 200:
            base = line_count * 0.2
        elif line_count < 350:
            base = 40.0 + (line_count - 200) * 0.2
        elif line_count < 400:
            base = 70.0 + (line_count - 350) * 0.3
        elif line_count < 500:
            base = 85.0 + (line_count - 400) * 0.15
        else:
            base = 100.0

        import_penalty = min(10.0, max(0, imports_count) * 0.5)
        raw_score = base + import_penalty * (1.0 - base / 100.0)
        return round(max(0.0, min(100.0, raw_score)), 2)

    def analyze_file(self, file_path: Path) -> FileModularityScore:
        """Calculates modularity metrics for a single source file."""
        lines = count_file_lines(file_path)
        imports = count_file_imports(file_path)
        score = self.calculate_file_score(lines, imports)
        level = determine_risk_level(score, lines)
        action = get_recommended_action(level, lines)

        rel_path = file_path.as_posix()
        if self.root_dir:
            try:
                rel_path = file_path.resolve().relative_to(self.root_dir.resolve()).as_posix()
            except ValueError:
                try:
                    rel_path = file_path.relative_to(self.root_dir).as_posix()
                except ValueError:
                    rel_path = file_path.as_posix()

        return FileModularityScore(
            file_path=rel_path,
            line_count=lines,
            risk_score=score,
            risk_level=level,
            recommended_action=action,
        )

    def analyze_directory(self, root_dir: Path) -> ModularityReport:
        """Walks directory, evaluates source files, and aggregates project modularity report."""
        target_root = Path(root_dir)
        self.root_dir = target_root
        scores: list[FileModularityScore] = []

        for p in sorted(target_root.rglob("*")):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(target_root)
            except ValueError:
                continue

            if is_excluded_path(rel):
                continue
            if p.suffix not in SOURCE_EXTENSIONS:
                continue

            score = self.analyze_file(p)
            scores.append(score)

        scores.sort(key=lambda s: s.risk_score, reverse=True)
        danger_zone = [s for s in scores if s.line_count >= 350]
        overall_score = round(sum(s.risk_score for s in scores) / len(scores), 2) if scores else 0.0

        return ModularityReport(
            files=scores,
            overall_debt_score=overall_score,
            danger_zone_files=danger_zone,
        )
