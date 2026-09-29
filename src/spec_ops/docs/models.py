"""Domain models and data structures for Diataxis documentation audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

APPROVED_QUADRANTS: set[str] = {"tutorials", "how-to", "reference", "explanation", "project"}
ALLOWED_ROOT_FILES: set[str] = {
    "index.md",
    "operating-manual.md",
    "contributing.md",
    "delivering-real-value.md",
    "README.md",
}


@dataclass
class AuditViolation:
    category: str  # "structure", "cli_drift", "snippet"
    file_path: Path | None
    message: str
    severity: str = "error"  # "error", "warning"


@dataclass
class AuditReport:
    violations: list[AuditViolation] = field(default_factory=list)
    quadrants_checked: list[str] = field(default_factory=list)
    cli_commands_checked: int = 0
    snippets_checked: int = 0

    @property
    def is_clean(self) -> bool:
        return not any(v.severity == "error" for v in self.violations)

    @property
    def errors(self) -> list[AuditViolation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[AuditViolation]:
        return [v for v in self.violations if v.severity == "warning"]


@dataclass
class ParsedCLICommand:
    command: str
    options: set[str]
    positionals: list[str] = field(default_factory=list)
