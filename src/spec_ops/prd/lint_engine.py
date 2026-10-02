"""Domain model and state handlers for PRD line-level linting and remediation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..core.parser import extract_frontmatter
from .linter import PRDLinter
from .studio import KNOWN_PERSONAS

RULE_MISSING_PERSONA = "PRD-LINT-001"
RULE_UNFALSIFIABLE_OUTCOME = "PRD-LINT-002"
RULE_MISSING_SECTION = "PRD-LINT-003"
RULE_EMPTY_OUTCOMES = "PRD-LINT-004"
RULE_FRONTMATTER_SYNTAX = "PRD-LINT-005"


@dataclass
class LineLevelSuggestion:
    """Actionable line-level suggestion and concrete remediation hint."""

    line: int
    rule_id: str
    original_text: str
    suggested_text: str
    remediation_hint: str


@dataclass
class PRDLintDiagnostic:
    """Rich domain diagnostic representing a specific PRD quality violation."""

    file_path: str
    line: int
    rule_id: str
    severity: str  # "error" | "warning"
    message: str
    guidance: str
    suggestion: LineLevelSuggestion | None = None


@dataclass
class PRDLintReport:
    """Comprehensive linting report with line-level diagnostics and audit metrics."""

    file_path: str
    is_valid: bool
    diagnostics: list[PRDLintDiagnostic] = field(default_factory=list)
    falsifiable_count: int = 0
    unfalsifiable_count: int = 0
    outcome_checks: list[Any] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "falsifiable_count": self.falsifiable_count,
            "unfalsifiable_count": self.unfalsifiable_count,
            "diagnostics": [asdict(d) for d in self.diagnostics],
        }


class PRDLintEngine:
    """Pure domain engine evaluating PRD quality with line-level remediation synthesis."""

    REWRITE_MAP: dict[str, str] = {
        "clean": "observable and structured",
        "modern": "standards-compliant",
        "intuitive": "verified through public frontdoors",
        "fast": "executes in <200ms",
        "faster": "demonstrates 2x lower latency in benchmark",
        "responsive": "handles requests within 100ms",
        "simple": "requires zero manual workarounds",
        "easy": "operates with a single CLI command",
        "seamless": "integrates without data loss",
        "robust": "handles errors gracefully with zero crashes",
        "beautiful": "standards-compliant",
        "elegant": "structured and modular",
        "smooth": "deterministic",
        "frictionless": "self-service",
        "delightful": "fulfills user journey acceptance criteria",
        "user-friendly": "accessible",
        "user friendly": "accessible",
    }

    def __init__(self, root_dir: Path | str | None = None) -> None:
        self.root_dir = Path(root_dir).resolve() if root_dir else None
        self._linter = PRDLinter(root_dir=self.root_dir)

    def synthesize_remediation(self, rule_id: str, line: int, text: str, detail: str = "") -> LineLevelSuggestion:
        """Synthesizes line-level replacement text and explanatory remediation hint."""
        if rule_id == RULE_MISSING_PERSONA:
            valid_list = ", ".join(sorted(KNOWN_PERSONAS))
            return LineLevelSuggestion(
                line=line,
                rule_id=rule_id,
                original_text=text or "target_persona: [unmapped]",
                suggested_text="target_persona: Taylor",
                remediation_hint=f"Assign an authorized persona. Choose from: {valid_list}",
            )

        if rule_id == RULE_UNFALSIFIABLE_OUTCOME:
            suggested = text
            for word, rep in self.REWRITE_MAP.items():
                suggested = re.sub(
                    r"\b" + re.escape(word) + r"\b",
                    rep,
                    suggested,
                    flags=re.IGNORECASE,
                )
            if detail and re.search(r"\b" + re.escape(detail) + r"\b", suggested, re.IGNORECASE):
                suggested = re.sub(
                    r"\b" + re.escape(detail) + r"\b",
                    "observable and verified",
                    suggested,
                    flags=re.IGNORECASE,
                )
            return LineLevelSuggestion(
                line=line,
                rule_id=rule_id,
                original_text=text,
                suggested_text=suggested,
                remediation_hint=(
                    "Replace subjective adjectives with observable, "
                    "falsifiable behavioral contracts or measurable boundary thresholds."
                ),
            )

        return LineLevelSuggestion(
            line=line,
            rule_id=rule_id,
            original_text=text,
            suggested_text=f"## {detail}" if detail else text,
            remediation_hint=f"Ensure required section '{detail}' is authored according to ADR-0001.",
        )

    def lint_content(self, content: str, file_path: str = "<in-memory>") -> PRDLintReport:
        """Analyzes PRD text and synthesizes rich line-level diagnostics."""
        base_result = self._linter.lint_text(content, file_path=file_path)
        diagnostics: list[PRDLintDiagnostic] = []

        lines = content.splitlines()
        meta, _ = extract_frontmatter(content)

        # Check persona
        persona = str(meta.get("target_persona", "")).strip()
        if not persona or persona.lower() in ("unmapped", "none", "unknown"):
            target_line = 1
            for idx, line in enumerate(lines, 1):
                if line.strip().startswith("target_persona:"):
                    target_line = idx
                    break
            suggestion = self.synthesize_remediation(
                RULE_MISSING_PERSONA,
                line=target_line,
                text=lines[target_line - 1] if target_line <= len(lines) else "",
            )
            diagnostics.append(
                PRDLintDiagnostic(
                    file_path=file_path,
                    line=target_line,
                    rule_id=RULE_MISSING_PERSONA,
                    severity="error",
                    message="Target persona is missing or unmapped in frontmatter (ADR-0001)",
                    guidance="Link to an approved persona from docs/project/user_stories/PERSONAS.md",
                    suggestion=suggestion,
                )
            )

        # Map base violations to structured diagnostics
        for v in base_result.violations:
            rule_id = RULE_FRONTMATTER_SYNTAX
            if "Target persona" in v.message:
                continue  # Already captured with LineLevelSuggestion above
            elif "Subjective adjective" in v.message:
                rule_id = RULE_UNFALSIFIABLE_OUTCOME
                m = re.search(r"'(.*?)'", v.message)
                subj = m.group(1) if m else ""
                orig = lines[v.line - 1] if 1 <= v.line <= len(lines) else ""
                sug = self.synthesize_remediation(rule_id, v.line, orig, detail=subj)
                diagnostics.append(
                    PRDLintDiagnostic(
                        file_path=file_path,
                        line=v.line,
                        rule_id=rule_id,
                        severity="error",
                        message=v.message,
                        guidance=v.guidance,
                        suggestion=sug,
                    )
                )
            elif "Missing required section" in v.message:
                rule_id = RULE_MISSING_SECTION
                m = re.search(r"'(.*?)'", v.message)
                sec = m.group(1) if m else "Section"
                sug = self.synthesize_remediation(rule_id, v.line, "", detail=sec)
                diagnostics.append(
                    PRDLintDiagnostic(
                        file_path=file_path,
                        line=v.line,
                        rule_id=rule_id,
                        severity="error",
                        message=v.message,
                        guidance=v.guidance,
                        suggestion=sug,
                    )
                )
            elif "No checkable outcomes" in v.message:
                rule_id = RULE_EMPTY_OUTCOMES
                diagnostics.append(
                    PRDLintDiagnostic(
                        file_path=file_path,
                        line=v.line,
                        rule_id=rule_id,
                        severity="error",
                        message=v.message,
                        guidance=v.guidance,
                    )
                )
            else:
                diagnostics.append(
                    PRDLintDiagnostic(
                        file_path=file_path,
                        line=v.line,
                        rule_id=rule_id,
                        severity="error",
                        message=v.message,
                        guidance=v.guidance,
                    )
                )

        falsifiable_count = sum(1 for c in base_result.outcome_checks if c.is_falsifiable)
        unfalsifiable_count = sum(1 for c in base_result.outcome_checks if not c.is_falsifiable)

        is_valid = len(diagnostics) == 0 and len(base_result.violations) == 0

        return PRDLintReport(
            file_path=file_path,
            is_valid=is_valid,
            diagnostics=diagnostics,
            falsifiable_count=falsifiable_count,
            unfalsifiable_count=unfalsifiable_count,
            outcome_checks=base_result.outcome_checks,
        )

    def lint_file(self, target_file: Path | str) -> PRDLintReport:
        """Lints an on-disk PRD file with line-level diagnostics."""
        path = Path(target_file)
        if not path.is_file():
            return PRDLintReport(
                file_path=str(target_file),
                is_valid=False,
                diagnostics=[
                    PRDLintDiagnostic(
                        file_path=str(target_file),
                        line=1,
                        rule_id="PRD-LINT-000",
                        severity="error",
                        message=f"File not found: {target_file}",
                        guidance="Ensure target PRD file exists on disk",
                    )
                ],
            )
        content = path.read_text(encoding="utf-8")
        rel_path = str(path.relative_to(self.root_dir)) if self.root_dir and path.is_relative_to(self.root_dir) else str(path)
        return self.lint_content(content, file_path=rel_path)
