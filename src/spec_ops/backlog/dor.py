"""Definition of Ready (DoR) gate validation for backlog tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..core.parser import extract_frontmatter


def validate_task_dor(task: Task | dict[str, Any], config: SpecOpsConfig) -> tuple[bool, list[str]]:
    """Validates that a task satisfies all Definition of Ready (DoR) criteria."""
    errors: list[str] = []

    # Helper getters
    def _get(field: str) -> Any:
        if isinstance(task, Task):
            return getattr(task, field, None)
        return task.get(field)

    governing_adrs = _get("governing_adrs") or []
    governing_stories = _get("governing_stories") or []
    governing_prds = _get("governing_prds") or []
    target_bc = _get("target_bc") or ""

    # 1. Governing ADRs
    if not governing_adrs:
        errors.append("Missing governing ADRs: task must link at least 1 accepted ADR")
    else:
        adrs_dir = Path(config.project.docs_dir) / "adrs"
        if not adrs_dir.is_absolute():
            adrs_dir = config.root_dir / adrs_dir
        for adr_ref in governing_adrs:
            clean_num = adr_ref.upper().replace("ADR-", "").lstrip("0")
            target_stem = clean_num.zfill(4)
            found = False
            if adrs_dir.exists():
                for p in adrs_dir.rglob("*.md"):
                    if (target_stem in p.stem.upper() or adr_ref.upper() in p.name.upper()) and p.is_file():
                        if p.parent.name.lower() == "accepted":
                            found = True
                            break
                        status_str = str(meta.get("status", "")).strip().lower()
                        if status_str == "accepted" or status_str.startswith("accepted"):
                            found = True
                            break
            if not found:
                errors.append(f"Missing governing ADRs: task must link at least 1 accepted ADR ({adr_ref} not found in accepted/)")

    # 2. Governing BDD user stories
    if not governing_stories:
        errors.append("Missing governing story: task must trace back to an accepted BDD user story")
    else:
        stories_dir = Path(config.project.docs_dir) / "user_stories"
        if not stories_dir.is_absolute():
            stories_dir = config.root_dir / stories_dir
        for s_ref in governing_stories:
            clean_s = s_ref.upper().replace("US-", "").lstrip("0")
            target_stem = clean_s.zfill(4)
            found = False
            if stories_dir.exists():
                for p in stories_dir.rglob("*.md"):
                    if (target_stem in p.stem.upper() or s_ref.upper() in p.name.upper()) and p.is_file():
                        if p.parent.name.lower() == "accepted":
                            found = True
                            break
                        meta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
                        if str(meta.get("status", "")).strip().lower() == "accepted":
                            found = True
                            break
            if not found:
                errors.append(f"Missing governing story: task must trace back to an accepted BDD user story ({s_ref} not found in accepted/)")

    # 3. Governing PRDs
    if not governing_prds:
        errors.append("Missing governing PRD: task must link at least 1 accepted PRD")
    else:
        prd_dir = Path(config.project.docs_dir) / "product"
        if not prd_dir.is_absolute():
            prd_dir = config.root_dir / prd_dir
        for prd_ref in governing_prds:
            clean_p = prd_ref.upper().replace("PRD-", "").lstrip("0")
            target_stem = clean_p.zfill(4)
            found = False
            if prd_dir.exists():
                for p in prd_dir.rglob("*.md"):
                    if (target_stem in p.stem.upper() or prd_ref.upper() in p.name.upper()) and p.is_file():
                        if p.parent.name.lower() in ("accepted", "shipped"):
                            found = True
                            break
                        meta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
                        if str(meta.get("status", "")).strip().lower() in ("accepted", "shipped"):
                            found = True
                            break
            if not found:
                errors.append(f"Missing governing PRD: task must link at least 1 accepted PRD ({prd_ref} not found in accepted/)")

    # 4. Target Bounded Context
    if not target_bc:
        errors.append("Missing target bounded context: task frontmatter must include target_bc")

    return len(errors) == 0, errors
