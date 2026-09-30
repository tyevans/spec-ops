"""PRD checkable outcome parsing, falsifiability validation, and delta scope calculation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.parser import extract_frontmatter
from .linter import PRDLinter


class FalsifiabilityError(Exception):
    """Raised when one or more PRD outcomes fail falsifiability checks."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class CheckableOutcome:
    """Represents a discrete checkable outcome extracted from a PRD."""

    id: int
    raw_text: str
    clean_text: str
    is_falsifiable: bool = True
    subjective_term: str = ""


@dataclass
class PRDDeltaResult:
    """Result of delta scope calculation comparing PRD outcomes against backlog."""

    prd_id: str
    current_outcomes: list[CheckableOutcome] = field(default_factory=list)
    added_outcomes: list[CheckableOutcome] = field(default_factory=list)
    existing_outcomes: list[CheckableOutcome] = field(default_factory=list)
    removed_outcome_ids: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pending_tasks_for_removed: list[dict[str, Any]] = field(default_factory=list)


def parse_checkable_outcomes(prd_content: str) -> list[CheckableOutcome]:
    """Extracts discrete checkable outcomes from the '## Checkable Outcomes' section."""
    lines = prd_content.splitlines()
    header_idx = -1
    for idx, line in enumerate(lines):
        if re.match(r"^##\s+Checkable Outcomes\b", line, re.IGNORECASE):
            header_idx = idx
            break

    if header_idx == -1:
        return []

    linter = PRDLinter()
    outcomes: list[CheckableOutcome] = []
    seq_id = 0

    for line in lines[header_idx + 1:]:
        if re.match(r"^##\s+", line):
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue

        clean = re.sub(r"<!--.*?-->", "", stripped).strip()
        if not clean:
            continue

        bullet_num = None
        m_bullet = re.match(r"^(\d+)\.\s*(.*)$", clean)
        if m_bullet:
            bullet_num = m_bullet.group(1)
            clean = m_bullet.group(2).strip()
        else:
            m_bullet = re.match(r"^[\-\*]\s*(.*)$", clean)
            if m_bullet:
                clean = m_bullet.group(1).strip()

        explicit_id = None
        m_outcome = re.match(r"^Outcome\s*(\d+)[:\s\-\.]+\s*(.*)$", clean, re.IGNORECASE)
        if m_outcome:
            explicit_id = m_outcome.group(1)
            clean = m_outcome.group(2).strip()

        if not clean:
            continue

        seq_id += 1
        num_str = explicit_id or bullet_num
        outcome_id = int(num_str) if num_str else seq_id

        subj = linter.check_subjective_terms(clean)
        is_falsifiable = subj is None
        subjective_term = subj or ""

        outcomes.append(
            CheckableOutcome(
                id=outcome_id,
                raw_text=stripped,
                clean_text=clean,
                is_falsifiable=is_falsifiable,
                subjective_term=subjective_term,
            )
        )

    return outcomes


def validate_falsifiability(outcomes: list[CheckableOutcome]) -> list[str]:
    """Validates falsifiability of outcomes, returning error messages for any subjective outcomes."""
    errors: list[str] = []
    for o in outcomes:
        if not o.is_falsifiable:
            errors.append(
                f"Outcome '{o.clean_text}' is non-falsifiable; refine into an observable metric or contract"
            )
    return errors


def find_existing_stories(stories_dir: Path, prd_canonical_id: str) -> list[dict[str, Any]]:
    """Scans user stories directory for stories linked to prd_canonical_id."""
    clean_id = prd_canonical_id.upper().replace("PRD-", "").lstrip("0")
    results: list[dict[str, Any]] = []
    if not stories_dir.exists():
        return results

    for p in sorted(stories_dir.rglob("*.md")):
        content = p.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(content)
        gov_prd = str(meta.get("governing_prd", "")).upper()
        if not gov_prd:
            continue
        gov_clean = gov_prd.replace("PRD-", "").lstrip("0")
        if gov_clean == clean_id:
            raw_outcome_id = meta.get("outcome_id") or meta.get("governing_outcome")
            outcome_id = None
            if raw_outcome_id is not None:
                try:
                    outcome_id = int(raw_outcome_id)
                except (ValueError, TypeError):
                    outcome_id = None
            raw_sid = str(meta.get("id", ""))
            story_id = raw_sid
            if not story_id.upper().startswith("US-"):
                m = re.search(r"us-(\d+)", f"{raw_sid} {p.stem}", re.IGNORECASE)
                if m:
                    story_id = f"US-{int(m.group(1)):04d}"
                elif story_id.isdigit():
                    story_id = f"US-{int(story_id):04d}"
                elif not story_id:
                    story_id = p.stem
            results.append(
                {
                    "id": story_id,
                    "path": p,
                    "title": str(meta.get("title", "")),
                    "outcome_id": outcome_id,
                    "meta": meta,
                }
            )
    return results


def find_existing_tasks(
    backlog_dir: Path,
    prd_canonical_id: str,
    stories_map: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Scans backlog tasks directory for tasks linked to prd_canonical_id."""
    clean_id = prd_canonical_id.upper().replace("PRD-", "").lstrip("0")
    results: list[dict[str, Any]] = []
    if not backlog_dir.exists():
        return results

    if stories_map is None:
        stories_map = {}

    for p in sorted(backlog_dir.rglob("*.md")):
        if p.name == "PRIORITY.md":
            continue
        content = p.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(content)
        gov_prds = meta.get("governing_prds", [])
        if isinstance(gov_prds, str):
            gov_prds = [gov_prds]
        matched = False
        for gp in gov_prds:
            gp_clean = str(gp).upper().replace("PRD-", "").lstrip("0")
            if gp_clean == clean_id:
                matched = True
                break
        if not matched:
            continue

        raw_outcome_id = meta.get("outcome_id") or meta.get("governing_outcome")
        outcome_id = None
        if raw_outcome_id is not None:
            try:
                outcome_id = int(raw_outcome_id)
            except (ValueError, TypeError):
                outcome_id = None

        gov_stories = meta.get("governing_stories", [])
        if isinstance(gov_stories, str):
            gov_stories = [gov_stories]

        if outcome_id is None:
            for sid in gov_stories:
                clean_sid = sid.upper().replace("US-", "").lstrip("0")
                if clean_sid in stories_map:
                    outcome_id = stories_map[clean_sid]
                    break

        if outcome_id is None:
            m = re.search(r"\boutcome\s+(\d+)\b", content, re.IGNORECASE)
            if m:
                outcome_id = int(m.group(1))

        status = str(meta.get("status", "Proposed"))
        task_id = str(meta.get("id", p.stem))
        if not task_id.upper().startswith("TASK-"):
            m = re.match(r"^(\d+)", p.stem)
            if m:
                task_id = f"TASK-{int(m.group(1)):04d}"

        results.append(
            {
                "id": task_id,
                "path": p,
                "title": str(meta.get("title", "")),
                "status": status,
                "outcome_id": outcome_id,
                "governing_stories": gov_stories,
                "meta": meta,
            }
        )
    return results


def calculate_prd_deltas(
    prd_id: str,
    current_outcomes: list[CheckableOutcome],
    existing_stories: list[dict[str, Any]],
    existing_tasks: list[dict[str, Any]],
) -> PRDDeltaResult:
    """Calculates added, existing, and removed outcomes along with pending task warnings."""
    current_outcome_ids = {o.id for o in current_outcomes}

    covered_outcome_ids: set[int] = set()
    for s in existing_stories:
        if s.get("outcome_id") is not None:
            covered_outcome_ids.add(s["outcome_id"])
    for t in existing_tasks:
        if t.get("outcome_id") is not None:
            covered_outcome_ids.add(t["outcome_id"])

    if not covered_outcome_ids and existing_stories:
        for idx in range(1, len(existing_stories) + 1):
            if idx in current_outcome_ids:
                covered_outcome_ids.add(idx)

    added: list[CheckableOutcome] = []
    existing: list[CheckableOutcome] = []

    for o in current_outcomes:
        if o.id in covered_outcome_ids:
            existing.append(o)
        else:
            matched_by_text = any(
                o.clean_text.lower() in str(s.get("title", "")).lower()
                for s in existing_stories
            )
            if matched_by_text:
                existing.append(o)
                covered_outcome_ids.add(o.id)
            else:
                added.append(o)

    all_referenced_outcome_ids: set[int] = set()
    for s in existing_stories:
        if s.get("outcome_id") is not None:
            all_referenced_outcome_ids.add(s["outcome_id"])
    for t in existing_tasks:
        if t.get("outcome_id") is not None:
            all_referenced_outcome_ids.add(t["outcome_id"])

    removed_outcome_ids = sorted(all_referenced_outcome_ids - current_outcome_ids)

    warnings: list[str] = []
    pending_tasks_for_removed: list[dict[str, Any]] = []

    for t in existing_tasks:
        t_outcome_id = t.get("outcome_id")
        if t_outcome_id in removed_outcome_ids:
            status = str(t.get("status", "Proposed"))
            if status.lower() != "complete":
                pending_tasks_for_removed.append(t)
                warnings.append(
                    f"Outcome {t_outcome_id} was removed from {prd_id} but has pending task {t['id']}"
                )

    return PRDDeltaResult(
        prd_id=prd_id,
        current_outcomes=current_outcomes,
        added_outcomes=added,
        existing_outcomes=existing,
        removed_outcome_ids=removed_outcome_ids,
        warnings=warnings,
        pending_tasks_for_removed=pending_tasks_for_removed,
    )
