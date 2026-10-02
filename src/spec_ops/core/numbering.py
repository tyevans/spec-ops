"""Numbering integrity and collision detection for SpecOps PMaC artifacts (ADRs, PRDs, Tasks, Stories)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

IGNORED_FILE_NAMES = {
    "registry.md",
    "readme.md",
    "priority.md",
    "roadmap.md",
    "feature_inventory.md",
    "personas.md",
    "security.md",
}


@dataclass
class NumberingCollision:
    """Represents a duplicate number collision within an artifact group."""

    group: str
    number: int
    canonical_id: str
    paths: list[Path]
    message: str = ""


@dataclass
class NumberingAuditReport:
    """Aggregated report of numbering uniqueness checks across artifact groups."""

    collisions: list[NumberingCollision] = field(default_factory=list)
    entity_counts: dict[str, int] = field(default_factory=dict)
    checked_files: int = 0

    @property
    def is_valid(self) -> bool:
        """True if zero collisions were detected."""
        return len(self.collisions) == 0

    def format_diagnostics(self) -> str:
        """Formats a human-readable diagnostic report."""
        if self.is_valid:
            total = sum(self.entity_counts.values())
            return (
                f"✅ Numbering Invariant Met: All {total} artifact IDs across "
                f"{len(self.entity_counts)} groups are unique."
            )

        lines = [f"❌ {len(self.collisions)} Numbering Collision(s) Detected:"]
        for c in self.collisions:
            lines.append(f"   - Group '{c.group.upper()}': {c.canonical_id} duplicated across {len(c.paths)} files:")
            for p in c.paths:
                lines.append(f"       • {p}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serializes audit report to dictionary for JSON output."""
        return {
            "is_valid": self.is_valid,
            "total_entities": sum(self.entity_counts.values()),
            "entity_counts": self.entity_counts,
            "checked_files": self.checked_files,
            "collision_count": len(self.collisions),
            "collisions": [
                {
                    "group": c.group,
                    "number": c.number,
                    "canonical_id": c.canonical_id,
                    "paths": [str(p) for p in c.paths],
                }
                for c in self.collisions
            ],
        }


def extract_numbers_for_file(file_path: Path, prefix: str, stem_regex: str) -> set[int]:
    """Extracts numbers associated with a markdown file from filename, frontmatter, and H1 heading."""
    numbers: set[int] = set()

    m_stem = re.search(stem_regex, file_path.stem, re.IGNORECASE)
    if m_stem:
        numbers.add(int(m_stem.group(1)))

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return numbers

    m_id = re.search(r"(?m)^\s*id:\s*['\"]?(?:" + prefix + r"-)?(\d+)['\"]?\s*$", content, re.IGNORECASE)
    if m_id:
        numbers.add(int(m_id.group(1)))

    m_h1 = re.search(r"#\s*" + prefix + r"-(\d+)", content, re.IGNORECASE)
    if m_h1:
        numbers.add(int(m_h1.group(1)))

    return numbers


def _audit_group(
    dir_path: Path,
    group_name: str,
    prefix: str,
    stem_regex: str,
) -> tuple[list[NumberingCollision], int, int]:
    """Audits numbering uniqueness within a single artifact directory."""
    if not dir_path.exists():
        return [], 0, 0

    seen_numbers: dict[int, list[Path]] = {}
    files_checked = 0

    for file_path in sorted(dir_path.rglob("*.md")):
        if file_path.name.lower() in IGNORED_FILE_NAMES or file_path.name.startswith("."):
            continue

        files_checked += 1
        numbers = extract_numbers_for_file(file_path, prefix, stem_regex)
        for num in numbers:
            seen_numbers.setdefault(num, []).append(file_path)

    collisions: list[NumberingCollision] = []
    for num, paths in sorted(seen_numbers.items()):
        # Filter duplicates: if the same file triggered via stem & frontmatter, dedup paths
        unique_paths = sorted(set(paths))
        if len(unique_paths) > 1:
            cid = f"{prefix}-{num:04d}"
            collisions.append(
                NumberingCollision(
                    group=group_name,
                    number=num,
                    canonical_id=cid,
                    paths=unique_paths,
                    message=f"{cid} is duplicated across {len(unique_paths)} files",
                )
            )

    return collisions, len(seen_numbers), files_checked


def audit_numbering_uniqueness(target: Any) -> NumberingAuditReport:
    """Audits numbering uniqueness across ADRs, PRDs, Tasks, and User Stories."""
    from ..config.models import SpecOpsConfig

    if isinstance(target, SpecOpsConfig):
        project_docs = target.project_docs_dir
    elif isinstance(target, Path):
        project_docs = target
        if (target / "docs" / "project").exists():
            project_docs = target / "docs" / "project"
    else:
        project_docs = Path("docs/project")

    groups: list[tuple[str, Path, str, str]] = [
        ("adrs", project_docs / "adrs", "ADR", r"^(?:adr-)?(\d+)"),
        ("prds", project_docs / "product", "PRD", r"^(?:prd-)?(\d+)"),
        ("tasks", project_docs / "backlog", "TASK", r"^(?:(?:task|spike)-)?(\d+)"),
        ("stories", project_docs / "user_stories", "US", r"^(?:us-)?(\d+)"),
    ]

    all_collisions: list[NumberingCollision] = []
    entity_counts: dict[str, int] = {}
    total_files = 0

    for group_name, dir_path, prefix, stem_regex in groups:
        cols, count, files_count = _audit_group(dir_path, group_name, prefix, stem_regex)
        all_collisions.extend(cols)
        entity_counts[group_name] = count
        total_files += files_count

    return NumberingAuditReport(
        collisions=all_collisions,
        entity_counts=entity_counts,
        checked_files=total_files,
    )
