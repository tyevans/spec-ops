"""Persona-to-commit bidirectional traceability matrix and coverage auditor."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester
from ..core.models import Persona, ProjectData, Task, UserStory
from ..core.parser import SpecOpsParser


@dataclass
class PersonaLineageRecord:
    persona: str
    prd: str
    story: str
    task: str
    commit: str
    status: str
    permalink: str = ""

    def to_row(self) -> list[str]:
        return [self.persona, self.prd, self.story, self.task, self.commit, self.status]


@dataclass
class PersonaCoverageReport:
    distribution: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    orphan_tasks: list[str] = field(default_factory=list)
    lineage_records: list[PersonaLineageRecord] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0 or len(self.orphan_tasks) > 0


def _clean_prd_id(raw_id: str) -> str:
    clean = raw_id.upper().replace("PRD-", "").lstrip("0")
    return f"PRD-{clean.zfill(4)}" if clean else raw_id.upper()


def _clean_story_id(raw_id: str) -> str:
    clean = raw_id.upper().replace("US-", "").lstrip("0")
    return f"US-{clean.zfill(4)}" if clean else raw_id.upper()


def _clean_task_id(raw_id: str) -> str:
    clean = raw_id.upper().replace("TASK-", "").lstrip("0")
    return f"TASK-{clean.zfill(4)}" if clean else raw_id.upper()


class PersonaTraceabilityEngine:
    """Computes unbroken persona-to-commit lineage and audits persona coverage."""

    def __init__(self, config: SpecOpsConfig | None = None, project_data: ProjectData | None = None):
        self.config = config
        self._project_data = project_data

    def _load_data(self) -> ProjectData:
        if self._project_data is not None:
            return self._project_data
        if self.config is None:
            raise ValueError("PersonaTraceabilityEngine requires either SpecOpsConfig or ProjectData")
        parser = SpecOpsParser(self.config.project_docs_dir)
        data = parser.parse_all()

        harvester = GitMetadataHarvester(self.config.root_dir)
        git_map = harvester.harvest()
        for t in data.tasks:
            if t.canonical_id in git_map:
                commits, prs = git_map[t.canonical_id]
                t.commits = commits
                t.prs = list(dict.fromkeys(t.prs + prs))
        return data

    def _match_persona(self, persona: Persona, story: UserStory) -> bool:
        if not story.persona:
            return False
        p_name = persona.name.lower()
        p_id = persona.id.lower()
        s_persona = story.persona.lower()
        return p_id in s_persona or p_name in s_persona or story.id in persona.story_ids

    def build_lineage(self, persona_filter: str | None = None) -> list[PersonaLineageRecord]:
        """Builds unbroken lineage paths: Persona -> PRD -> User Story -> Backlog Task -> Git Commit."""
        data = self._load_data()
        records: list[PersonaLineageRecord] = []

        norm_filter = persona_filter.lower().replace("persona:", "").strip() if persona_filter else None

        for p in data.personas:
            if norm_filter and norm_filter not in p.name.lower() and norm_filter != p.id.lower():
                continue

            # Find stories linked to persona
            linked_stories = [s for s in data.stories if self._match_persona(p, s)]

            for s in linked_stories:
                prd_id = _clean_prd_id(s.governing_prd) if s.governing_prd else "PRD-0001"
                filter_key = s.feature or s.id
                permalink = f"#tab=prds&entity={prd_id}&filter={filter_key}"

                # Find tasks for story
                c_sid = _clean_story_id(s.id)
                linked_tasks = [
                    t for t in data.tasks
                    if any(_clean_story_id(gs) == c_sid for gs in t.governing_stories)
                    or t.canonical_id in s.implementing_tasks
                    or _clean_task_id(t.canonical_id) in [_clean_task_id(it) for it in s.implementing_tasks]
                ]

                if not linked_tasks:
                    records.append(
                        PersonaLineageRecord(
                            persona=p.name,
                            prd=prd_id,
                            story=s.id,
                            task="—",
                            commit="—",
                            status=s.status,
                            permalink=permalink,
                        )
                    )
                    continue

                for t in linked_tasks:
                    if t.commits:
                        for c in t.commits:
                            c_hash = c.hash[:7] if c.hash else "—"
                            records.append(
                                PersonaLineageRecord(
                                    persona=p.name,
                                    prd=prd_id,
                                    story=s.id,
                                    task=t.canonical_id,
                                    commit=c_hash,
                                    status=t.status,
                                    permalink=permalink,
                                )
                            )
                    else:
                        records.append(
                            PersonaLineageRecord(
                                persona=p.name,
                                prd=prd_id,
                                story=s.id,
                                task=t.canonical_id,
                                commit="—",
                                status=t.status,
                                permalink=permalink,
                            )
                        )

        return records

    def audit_persona_coverage(self) -> PersonaCoverageReport:
        """Audits persona allocation, active workload, neglected personas, and orphan tasks."""
        data = self._load_data()
        distribution: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        orphan_tasks: list[str] = []

        active_task_statuses = {"Proposed", "Refined", "In-Progress", "Review", "Ready"}

        # Task to persona mappings
        task_to_personas: dict[str, set[str]] = {}

        for p in data.personas:
            p_stories = [s for s in data.stories if self._match_persona(p, s)]
            p_story_ids = {_clean_story_id(s.id) for s in p_stories}

            p_tasks = [
                t for t in data.tasks
                if any(_clean_story_id(gs) in p_story_ids for gs in t.governing_stories)
                or any(_clean_task_id(t.canonical_id) in [_clean_task_id(it) for it in s.implementing_tasks] for s in p_stories)
            ]

            for t in p_tasks:
                task_to_personas.setdefault(t.canonical_id, set()).add(p.name)

            active_tasks = [
                t for t in p_tasks
                if t.status in active_task_statuses
                or (t.file_path and t.file_path.parent.name in ("proposed", "refined"))
            ]

            # Active stories: stories with active tasks or not Complete
            active_stories = [
                s for s in p_stories
                if s.status.lower() not in ("complete", "shipped", "graduated")
                and any(t.canonical_id in [at.canonical_id for at in active_tasks] for t in p_tasks)
            ]
            if not active_stories and p_stories and any(t.status in active_task_statuses for t in p_tasks):
                active_stories = [s for s in p_stories if s.status.lower() not in ("complete", "shipped")]

            distribution[p.name] = {
                "persona_id": p.id,
                "role": p.role,
                "total_stories": len(p_stories),
                "active_stories": len(active_stories),
                "total_tasks": len(p_tasks),
                "active_tasks": len(active_tasks),
            }

            if len(active_stories) == 0:
                warnings.append(
                    f"Warning: Persona '{p.name}' has 0 active stories in the current milestone"
                )

        # Flag orphan tasks
        for t in data.tasks:
            has_governing_story = bool(t.governing_stories)
            has_persona_lineage = t.canonical_id in task_to_personas and len(task_to_personas[t.canonical_id]) > 0

            if not has_governing_story or not has_persona_lineage:
                orphan_msg = f"Orphan Task: {t.canonical_id} lacks governing user story or persona lineage"
                orphan_tasks.append(orphan_msg)

        lineage = self.build_lineage()

        return PersonaCoverageReport(
            distribution=distribution,
            warnings=warnings,
            orphan_tasks=orphan_tasks,
            lineage_records=lineage,
        )

    def format_persona_coverage(self, report: PersonaCoverageReport) -> str:
        """Formats the persona coverage and workload allocation report for CLI."""
        lines = [
            "=== Persona Coverage & Workload Distribution Matrix ===",
            f"{'Persona':<24} {'Stories':<10} {'Active Stories':<16} {'Tasks':<8} {'Active Tasks':<14} {'Status'}",
            "-" * 84,
        ]

        for name, stats in report.distribution.items():
            status = "Active" if stats["active_stories"] > 0 else "Neglected (0 active stories)"
            lines.append(
                f"{name:<24} {stats['total_stories']:<10} {stats['active_stories']:<16} "
                f"{stats['total_tasks']:<8} {stats['active_tasks']:<14} {status}"
            )

        if report.warnings:
            lines.append("\n⚠️ Coverage Warnings:")
            for w in report.warnings:
                lines.append(f"   - {w}")

        if report.orphan_tasks:
            lines.append("\n⚠️ Orphan Tasks (lacking story or persona lineage):")
            for ot in report.orphan_tasks:
                lines.append(f"   - {ot}")

        return "\n".join(lines)

    def format_lineage_table(self, records: list[PersonaLineageRecord]) -> str:
        """Formats multi-column markdown table of persona lineage."""
        lines = [
            "| Persona | PRD | User Story | Backlog Task | Git Commit | Status |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in records:
            lines.append(f"| {r.persona} | {r.prd} | {r.story} | {r.task} | {r.commit} | {r.status} |")
        return "\n".join(lines)
