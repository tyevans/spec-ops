"""Domain models and serialization for user story authoring and traceability.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007; PRD-0006; US-0117.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


def slugify_story_title(text: str) -> str:
    """Produces a clean filesystem-safe slug from a story title."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:50] or "story"


def normalize_story_id(raw: str, prefix: str) -> str:
    """Normalizes an ID string into canonical prefix format (e.g. US-0001)."""
    digits = re.search(r"\d+", raw)
    if digits:
        return f"{prefix}-{int(digits.group(0)):04d}"
    return raw.strip().upper()


@dataclass
class StoryTraceItem:
    """Traceability status and relational lineage for a single user story."""

    id: str
    title: str
    status: str = "Accepted"
    persona: str = ""
    governing_prd: str = ""
    target_bc: str = ""
    feature: str = ""
    implementing_tasks: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        return len(self.implementing_tasks) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "persona": self.persona,
            "governing_prd": self.governing_prd,
            "target_bc": self.target_bc,
            "feature": self.feature,
            "implementing_tasks": self.implementing_tasks,
            "commits": self.commits,
            "issues": self.issues,
            "is_covered": self.is_covered,
        }


@dataclass
class StoryTraceReport:
    """Comprehensive traceability audit report across Personas, PRDs, Stories, Tasks, and Commits."""

    stories: list[StoryTraceItem] = field(default_factory=list)
    orphaned_stories: list[str] = field(default_factory=list)
    unlinked_tasks: list[str] = field(default_factory=list)
    broken_references: list[str] = field(default_factory=list)
    total_stories: int = 0
    covered_stories: int = 0

    @property
    def is_clean(self) -> bool:
        return len(self.orphaned_stories) == 0 and len(self.broken_references) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_clean": self.is_clean,
            "total_stories": self.total_stories,
            "covered_stories": self.covered_stories,
            "coverage_percentage": (
                round((self.covered_stories / self.total_stories) * 100, 1)
                if self.total_stories > 0
                else 100.0
            ),
            "orphaned_stories_count": len(self.orphaned_stories),
            "orphaned_stories": self.orphaned_stories,
            "unlinked_tasks_count": len(self.unlinked_tasks),
            "unlinked_tasks": self.unlinked_tasks,
            "broken_references_count": len(self.broken_references),
            "broken_references": self.broken_references,
            "stories": [s.to_dict() for s in self.stories],
        }

    def format_text(self) -> str:
        pct = (self.covered_stories / self.total_stories * 100) if self.total_stories > 0 else 100.0
        lines = [
            "=== SpecOps User Story Traceability Audit ===",
            f"Total User Stories: {self.total_stories}",
            f"Stories with Implementing Tasks: {self.covered_stories} ({pct:.1f}%)",
            f"Orphaned Stories (missing PRD/Persona): {len(self.orphaned_stories)}",
            f"Unlinked Backlog Tasks: {len(self.unlinked_tasks)}",
            f"Broken References: {len(self.broken_references)}",
            "",
        ]

        if self.orphaned_stories:
            lines.append("⚠️  Orphaned Stories:")
            for o in self.orphaned_stories:
                lines.append(f"   • {o}")
            lines.append("")

        if self.unlinked_tasks:
            lines.append("⚠️  Unlinked Backlog Tasks:")
            for ut in self.unlinked_tasks:
                lines.append(f"   • {ut}")
            lines.append("")

        if self.broken_references:
            lines.append("❌ Broken References:")
            for br in self.broken_references:
                lines.append(f"   • {br}")
            lines.append("")

        if self.is_clean:
            lines.append("✅ Traceability Invariant Met: All user stories have clean relational linkages.")
        else:
            lines.append("⚠️  Traceability Warnings Detected: Review items above to restore relational integrity.")

        return "\n".join(lines)


@dataclass
class StoryScaffoldResult:
    """Result of authoring a new user story."""

    id: str
    title: str
    file_path: Path
    content: str
    registry_updated: bool
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "file_path": str(self.file_path),
            "registry_updated": self.registry_updated,
            "dry_run": self.dry_run,
        }
