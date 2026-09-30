"""Continuous PRD outcome coverage audit and specification drift detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import ProjectData
from ..core.parser import SpecOpsParser
from .delta import CheckableOutcome, parse_checkable_outcomes


@dataclass
class OrphanedOutcome:
    prd_id: str
    outcome_id: int
    outcome_text: str

    @property
    def diagnostic(self) -> str:
        return (
            f"Orphaned Outcome: '{self.outcome_text}' in {self.prd_id} "
            f"has no linked user story or backlog tasks"
        )

    @property
    def suggestion(self) -> str:
        return f"Run 'spec-ops prd decompose {self.prd_id} --by-outcomes' to generate missing stories"


@dataclass
class UnanchoredTask:
    task_id: str
    prd_id: str
    title: str = ""

    @property
    def diagnostic(self) -> str:
        return (
            f"Unanchored Task: {self.task_id} references {self.prd_id} "
            f"but is not linked to any checkable outcome"
        )


@dataclass
class OutcomeAuditResult:
    total_outcomes: int = 0
    covered_outcomes: int = 0
    coverage_pct: float = 100.0
    orphaned_outcomes: list[OrphanedOutcome] = field(default_factory=list)
    unanchored_tasks: list[UnanchoredTask] = field(default_factory=list)
    diagnostic_messages: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    buffer_status: str = "OPTIMAL"

    @property
    def is_clean(self) -> bool:
        return len(self.orphaned_outcomes) == 0 and len(self.unanchored_tasks) == 0

    @property
    def drift_count(self) -> int:
        return len(self.orphaned_outcomes) + len(self.unanchored_tasks)


def calculate_outcome_coverage(total: int, covered: int) -> float:
    """Calculates coverage percentage, guaranteed strictly between 0.0 and 100.0."""
    if total <= 0:
        return 100.0
    if covered <= 0:
        return 0.0
    if covered >= total:
        return 100.0
    pct = round((covered / total) * 100.0, 1)
    return max(0.0, min(100.0, pct))


def _clean_prd_id(raw_id: str) -> str:
    clean = raw_id.upper().replace("PRD-", "").lstrip("0")
    return f"PRD-{clean.zfill(4)}" if clean else raw_id.upper()


def _clean_story_id(raw_id: str) -> str:
    clean = raw_id.upper().replace("US-", "").lstrip("0")
    return f"US-{clean.zfill(4)}" if clean else raw_id.upper()


def _clean_task_id(raw_id: str) -> str:
    clean = raw_id.upper().replace("TASK-", "").lstrip("0")
    return f"TASK-{clean.zfill(4)}" if clean else raw_id.upper()


class DeepPRDAuditor:
    """Audits checkable outcome coverage across accepted PRDs and detects specification drift."""

    def __init__(self, config: SpecOpsConfig | None = None, project_data: ProjectData | None = None):
        self.config = config
        self._project_data = project_data

    def _load_data(self) -> ProjectData:
        if self._project_data is not None:
            return self._project_data
        if self.config is None:
            raise ValueError("DeepPRDAuditor requires either SpecOpsConfig or ProjectData")
        parser = SpecOpsParser(self.config.project_docs_dir)
        return parser.parse_all()

    def audit_all_accepted(self, prd_id: str | None = None) -> OutcomeAuditResult:
        """Audits accepted PRDs for complete checkable outcome coverage and drift."""
        data = self._load_data()
        target_prds = []
        clean_target = _clean_prd_id(prd_id) if prd_id else None

        for prd in data.prds:
            c_id = _clean_prd_id(prd.id)
            if clean_target and c_id != clean_target:
                continue
            is_accepted = (
                prd.status.lower() == "accepted"
                or (prd.file_path and "accepted" in prd.file_path.parts)
            )
            if is_accepted or clean_target:
                target_prds.append(prd)

        total_outcomes = 0
        covered_outcomes = 0
        orphaned: list[OrphanedOutcome] = []
        unanchored: list[UnanchoredTask] = []
        diagnostics: list[str] = []
        suggestions: list[str] = []

        all_tasks = data.tasks
        all_stories = data.stories

        for prd in target_prds:
            c_prd_id = _clean_prd_id(prd.id)
            outcomes = parse_checkable_outcomes(prd.raw_markdown)
            if not outcomes and prd.outcomes:
                outcomes = [
                    CheckableOutcome(id=i + 1, raw_text=ot, clean_text=ot)
                    for i, ot in enumerate(prd.outcomes)
                ]

            total_outcomes += len(outcomes)

            # Stories linked to this PRD
            prd_stories = [
                s for s in all_stories
                if _clean_prd_id(s.governing_prd) == c_prd_id
                or s.id in prd.linked_stories
                or _clean_story_id(s.id) in [_clean_story_id(ls) for ls in prd.linked_stories]
            ]

            # Tasks claiming this PRD
            prd_tasks = [
                t for t in all_tasks
                if any(_clean_prd_id(gp) == c_prd_id for gp in t.governing_prds)
                or t.canonical_id in prd.implementing_tasks
                or _clean_task_id(t.canonical_id) in [_clean_task_id(it) for it in prd.implementing_tasks]
            ]

            outcome_mapped_tasks: set[str] = set()

            for outcome in outcomes:
                # Find matching stories
                linked_stories = []
                for s in prd_stories:
                    matches = False
                    raw_meta_outcome = None
                    if hasattr(s, "raw_markdown") and s.raw_markdown:
                        m_oid = re.search(r"outcome_id:\s*(\d+)", s.raw_markdown, re.IGNORECASE)
                        if m_oid:
                            raw_meta_outcome = int(m_oid.group(1))

                    if raw_meta_outcome is not None and raw_meta_outcome == outcome.id:
                        matches = True
                    elif outcome.clean_text.lower() in s.title.lower():
                        matches = True
                    elif s.scenarios and any(outcome.clean_text.lower() in sc.lower() for sc in s.scenarios):
                        matches = True
                    elif outcome.clean_text.lower() in s.raw_markdown.lower():
                        matches = True

                    if matches:
                        linked_stories.append(s)

                # Find implementing tasks for this outcome
                linked_tasks = []
                linked_story_ids = {s.id for s in linked_stories} | {_clean_story_id(s.id) for s in linked_stories}

                for t in prd_tasks:
                    task_matches = False
                    t_story_ids = {_clean_story_id(gs) for gs in t.governing_stories}
                    if t_story_ids & linked_story_ids:
                        task_matches = True

                    if hasattr(t, "raw_markdown") and t.raw_markdown:
                        m_oid = re.search(r"outcome_id:\s*(\d+)", t.raw_markdown, re.IGNORECASE)
                        if m_oid and int(m_oid.group(1)) == outcome.id:
                            task_matches = True

                    if outcome.clean_text.lower() in t.title.lower():
                        task_matches = True

                    if task_matches:
                        linked_tasks.append(t)
                        outcome_mapped_tasks.add(t.canonical_id)

                if linked_stories and linked_tasks:
                    covered_outcomes += 1
                else:
                    orphan = OrphanedOutcome(
                        prd_id=c_prd_id,
                        outcome_id=outcome.id,
                        outcome_text=outcome.clean_text,
                    )
                    orphaned.append(orphan)
                    diagnostics.append(orphan.diagnostic)
                    suggestions.append(orphan.suggestion)

            # Check for unanchored tasks claiming this PRD
            for t in prd_tasks:
                if t.canonical_id not in outcome_mapped_tasks:
                    unanchored_task = UnanchoredTask(
                        task_id=t.canonical_id,
                        prd_id=c_prd_id,
                        title=t.title,
                    )
                    unanchored.append(unanchored_task)
                    diagnostics.append(unanchored_task.diagnostic)

        # Check any tasks claiming a PRD not in target_prds
        audited_prd_ids = {_clean_prd_id(p.id) for p in target_prds}
        seen_unanchored_pairs = {(u.task_id, u.prd_id) for u in unanchored}
        for t in all_tasks:
            for gp in t.governing_prds:
                c_gp = _clean_prd_id(gp)
                if c_gp not in audited_prd_ids:
                    if (t.canonical_id, c_gp) not in seen_unanchored_pairs:
                        unanchored_task = UnanchoredTask(
                            task_id=t.canonical_id,
                            prd_id=c_gp,
                            title=t.title,
                        )
                        unanchored.append(unanchored_task)
                        diagnostics.append(unanchored_task.diagnostic)
                        seen_unanchored_pairs.add((t.canonical_id, c_gp))

        cov_pct = calculate_outcome_coverage(total_outcomes, covered_outcomes)
        is_clean = len(orphaned) == 0 and len(unanchored) == 0
        buf_status = "OPTIMAL" if is_clean else "INCOMPLETE_COVERAGE"

        return OutcomeAuditResult(
            total_outcomes=total_outcomes,
            covered_outcomes=covered_outcomes,
            coverage_pct=cov_pct,
            orphaned_outcomes=orphaned,
            unanchored_tasks=unanchored,
            diagnostic_messages=diagnostics,
            suggestions=list(dict.fromkeys(suggestions)),
            buffer_status=buf_status,
        )

    def format_report(self, result: OutcomeAuditResult) -> str:
        """Formats the audit outcome report for CLI output."""
        lines = ["=== Continuous PRD Outcome Coverage Audit ==="]
        lines.append(f"Outcome Coverage: {result.coverage_pct:.0f}% ({result.covered_outcomes}/{result.total_outcomes} outcomes covered)")
        lines.append(f"Specification Drift: {result.drift_count} issues detected")
        lines.append(f"Buffer Health: {result.buffer_status}")

        if result.orphaned_outcomes:
            lines.append("\n⚠️ Orphaned Outcomes:")
            for o in result.orphaned_outcomes:
                lines.append(f"   - {o.diagnostic}")
                lines.append(f"     Suggestion: {o.suggestion}")

        if result.unanchored_tasks:
            lines.append("\n⚠️ Unanchored Tasks:")
            for u in result.unanchored_tasks:
                lines.append(f"   - {u.diagnostic}")

        return "\n".join(lines)


def run_deep_audit(config: SpecOpsConfig, prd_id: str | None = None) -> int:
    """CLI entrypoint for spec-ops prd audit --deep."""
    auditor = DeepPRDAuditor(config)
    result = auditor.audit_all_accepted(prd_id=prd_id)
    print(auditor.format_report(result))
    return 0 if result.is_clean else 1
