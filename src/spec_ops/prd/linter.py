"""Automated structural and falsifiability markdown linter for PRD documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.parser import extract_frontmatter

COMPOUND_PHRASES: list[str] = [
    r"\bclean\s+and\s+modern\b",
    r"\bfast\s+and\s+responsive\b",
    r"\bsimple\s+and\s+intuitive\b",
    r"\bintuitive\s+and\s+easy\b",
    r"\beasy\s+to\s+use\b",
]

SUBJECTIVE_WORDS: list[str] = [
    "clean",
    "modern",
    "intuitive",
    "fast",
    "responsive",
    "simple",
    "easy",
    "seamless",
    "user-friendly",
    "user friendly",
    "robust",
    "beautiful",
    "elegant",
    "smooth",
    "frictionless",
    "delightful",
]


@dataclass
class LintViolation:
    file_path: Path | str
    line: int
    message: str
    guidance: str


@dataclass
class LintOutcomeCheck:
    line: int
    text: str
    is_falsifiable: bool
    subjective_term: str = ""


@dataclass
class LintResult:
    file_path: Path | str
    is_valid: bool
    violations: list[LintViolation] = field(default_factory=list)
    outcome_checks: list[LintOutcomeCheck] = field(default_factory=list)


class PRDLinter:
    """Validates PRD documents against required sections and falsifiability heuristics."""

    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir

    def check_subjective_terms(self, text: str) -> str | None:
        """Heuristically detects subjective adjectives and non-falsifiable phrases."""
        for pattern in COMPOUND_PHRASES:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(0).lower()

        pattern = r"\b(" + "|".join(re.escape(w) for w in SUBJECTIVE_WORDS) + r")\b"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(0).lower()
        return None

    def lint_text(self, content: str, file_path: Path | str = "<string>") -> LintResult:
        """Lints PRD markdown content in-memory."""
        violations: list[LintViolation] = []
        outcome_checks: list[LintOutcomeCheck] = []
        lines = content.splitlines()

        meta, _ = extract_frontmatter(content)
        if not meta:
            violations.append(
                LintViolation(
                    file_path=file_path,
                    line=1,
                    message="Missing or invalid YAML frontmatter",
                    guidance="Ensure document starts with '---' containing metadata",
                )
            )
        else:
            persona = str(meta.get("target_persona", "")).strip()
            if not persona or persona.lower() in ("unmapped", "none", "unknown"):
                line_no = 1
                for idx, line in enumerate(lines, 1):
                    if line.strip().startswith("target_persona:"):
                        line_no = idx
                        break
                violations.append(
                    LintViolation(
                        file_path=file_path,
                        line=line_no,
                        message="Target persona unmapped",
                        guidance="Map a target persona from docs/project/user_stories/PERSONAS.md",
                    )
                )

        has_problem = any(
            re.match(r"^##\s+(Who this is for|Problem Statement)\b", l, re.IGNORECASE)
            for l in lines
        )
        if not has_problem:
            violations.append(
                LintViolation(
                    file_path=file_path,
                    line=1,
                    message="Missing required section: '## Who this is for' or '## Problem Statement'",
                    guidance="Define the user problem statement and target persona context",
                )
            )

        has_good = any(
            re.match(r"^##\s+What good looks like\b", l, re.IGNORECASE) for l in lines
        )
        if not has_good:
            violations.append(
                LintViolation(
                    file_path=file_path,
                    line=1,
                    message="Missing required section: '## What good looks like'",
                    guidance="Define core capabilities describing what good looks like",
                )
            )

        has_anti_goals = any(
            re.match(r"^##\s+What this does not do\b", l, re.IGNORECASE) for l in lines
        )
        if not has_anti_goals:
            violations.append(
                LintViolation(
                    file_path=file_path,
                    line=1,
                    message="Missing required section: '## What this does not do'",
                    guidance="Define explicit anti-goals to prevent multi-agent scope creep",
                )
            )

        outcomes_header_idx = -1
        for idx, line in enumerate(lines, 1):
            if re.match(r"^##\s+Checkable Outcomes\b", line, re.IGNORECASE):
                outcomes_header_idx = idx
                break

        if outcomes_header_idx == -1:
            violations.append(
                LintViolation(
                    file_path=file_path,
                    line=1,
                    message="Missing required section: '## Checkable Outcomes'",
                    guidance="Define at least one falsifiable outcome with observable verification criteria",
                )
            )
        else:
            raw_outcomes: list[tuple[int, str]] = []
            for offset, line in enumerate(lines[outcomes_header_idx:], start=outcomes_header_idx + 1):
                if re.match(r"^##\s+", line):
                    break
                stripped = line.strip()
                if not stripped or stripped.startswith("<!--"):
                    continue
                m = re.match(r"^(\d+\.|\-|\*)\s+(.+)$", stripped)
                if m:
                    clean_text = re.sub(r"<!--.*?-->", "", m.group(2)).strip()
                    if clean_text:
                        raw_outcomes.append((offset, clean_text))

            if not raw_outcomes:
                violations.append(
                    LintViolation(
                        file_path=file_path,
                        line=outcomes_header_idx,
                        message="No checkable outcomes defined",
                        guidance="Provide at least one falsifiable, checkable outcome",
                    )
                )
            else:
                for line_no, outcome_text in raw_outcomes:
                    subjective = self.check_subjective_terms(outcome_text)
                    if subjective:
                        violations.append(
                            LintViolation(
                                file_path=file_path,
                                line=line_no,
                                message=f"Subjective adjective '{subjective}' is unfalsifiable",
                                guidance="Replace subjective adjectives with measurable frontdoor criteria or observable CLI/API assertions",
                            )
                        )
                        outcome_checks.append(
                            LintOutcomeCheck(
                                line=line_no,
                                text=outcome_text,
                                is_falsifiable=False,
                                subjective_term=subjective,
                            )
                        )
                    else:
                        outcome_checks.append(
                            LintOutcomeCheck(
                                line=line_no,
                                text=outcome_text,
                                is_falsifiable=True,
                            )
                        )

        is_valid = len(violations) == 0
        return LintResult(
            file_path=file_path,
            is_valid=is_valid,
            violations=violations,
            outcome_checks=outcome_checks,
        )

    def lint_file(self, file_path: Path | str) -> LintResult:
        """Lints a PRD file from disk."""
        path = Path(file_path).resolve()
        if not path.is_file():
            return LintResult(
                file_path=path,
                is_valid=False,
                violations=[
                    LintViolation(
                        file_path=path,
                        line=1,
                        message=f"File not found: {path}",
                        guidance="Ensure target PRD file exists on disk",
                    )
                ],
            )
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            return LintResult(
                file_path=path,
                is_valid=False,
                violations=[
                    LintViolation(
                        file_path=path,
                        line=1,
                        message=f"Error reading file: {exc}",
                        guidance="Check file permissions and UTF-8 encoding",
                    )
                ],
            )
        return self.lint_text(content, file_path=path)

    def lint_path(self, target_path: Path | str | None = None) -> list[LintResult]:
        """Lints a specific PRD file, directory of PRDs, or root PRD directory."""
        if target_path is None:
            if not self.root_dir:
                return []
            target = self.root_dir / "docs" / "project" / "product"
        else:
            target = Path(target_path).resolve()

        if target.is_file():
            return [self.lint_file(target)]

        results: list[LintResult] = []
        if target.is_dir():
            for p in sorted(target.rglob("*.md")):
                if p.name == "REGISTRY.md":
                    continue
                results.append(self.lint_file(p))
        return results

    def format_report(self, results: list[LintResult]) -> str:
        """Formats human-readable lint report with line-level diagnostics."""
        lines: list[str] = []
        total_violations = sum(len(r.violations) for r in results)

        for res in results:
            lines.append(f"=== PRD Markdown Lint: {res.file_path} ===")
            if res.outcome_checks:
                for idx, oc in enumerate(res.outcome_checks, 1):
                    if oc.is_falsifiable:
                        lines.append(
                            f"   [Outcome {idx}] passes as a valid falsifiable frontdoor contract"
                        )
                    else:
                        lines.append(
                            f"   [Outcome {idx}] flags Outcome {idx}: Subjective adjective '{oc.subjective_term}' is unfalsifiable"
                        )

            if res.violations:
                for v in res.violations:
                    lines.append(f"❌ Line {v.line} violation: \"{v.message}\"")
                    lines.append(f"   💡 guidance: \"{v.guidance}\"")
            else:
                lines.append("✅ All structural sections and falsifiability heuristics passed.")
            lines.append("")

        if total_violations == 0:
            lines.append("🎉 All PRDs passed falsifiable markdown linting.")
        else:
            lines.append(f"❌ Lint failed with {total_violations} violation(s).")
        return "\n".join(lines)
