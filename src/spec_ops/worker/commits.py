"""Automated conventional commit type derivation and RFC-822 git trailer formatting."""

from __future__ import annotations

import re
from typing import Any

VALID_CONVENTIONAL_TYPES = {
    "feat",
    "refactor",
    "spike",
    "fix",
    "chore",
    "docs",
    "test",
    "perf",
    "style",
    "ci",
}

SLICE_TYPE_SYNONYMS = {
    "feature": "feat",
    "refactoring": "refactor",
    "bug": "fix",
    "bugfix": "fix",
    "spike_task": "spike",
}


def derive_conventional_type(task_or_meta: Any) -> str:
    """Derives conventional commit type from task vertical slice metadata or title/id."""
    raw_slice: Any = getattr(task_or_meta, "slice_type", None)
    if not raw_slice and isinstance(task_or_meta, dict):
        raw_slice = (
            task_or_meta.get("slice_type")
            or task_or_meta.get("slice")
            or task_or_meta.get("type")
        )
    elif not raw_slice:
        raw_slice = getattr(task_or_meta, "slice", None) or getattr(task_or_meta, "type", None)

    if raw_slice and isinstance(raw_slice, str):
        normalized = raw_slice.strip().lower()
        if normalized in VALID_CONVENTIONAL_TYPES:
            return normalized
        if normalized in SLICE_TYPE_SYNONYMS:
            return SLICE_TYPE_SYNONYMS[normalized]

    raw_id = str(
        getattr(task_or_meta, "canonical_id", "")
        or (task_or_meta.get("canonical_id") if isinstance(task_or_meta, dict) else "")
        or getattr(task_or_meta, "id", "")
        or (task_or_meta.get("id") if isinstance(task_or_meta, dict) else "")
    ).upper()

    if "SPIKE" in raw_id:
        return "spike"

    title = str(
        getattr(task_or_meta, "title", "")
        or (task_or_meta.get("title") if isinstance(task_or_meta, dict) else "")
    ).strip().lower()

    if title.startswith("spike:") or title.startswith("[spike]"):
        return "spike"
    if title.startswith("refactor:") or title.startswith("[refactor]"):
        return "refactor"
    if title.startswith("fix:") or title.startswith("[fix]") or title.startswith("bug:"):
        return "fix"

    return "feat"


def _normalize_task_id(task_or_meta: Any, upper: bool = False) -> str:
    """Normalizes task ID to canonical form (e.g. TASK-0018 or task-0018)."""
    raw_id = str(
        getattr(task_or_meta, "canonical_id", "")
        or (task_or_meta.get("canonical_id") if isinstance(task_or_meta, dict) else "")
        or getattr(task_or_meta, "id", "")
        or (task_or_meta.get("id") if isinstance(task_or_meta, dict) else "")
        or "TASK-0000"
    ).strip()

    is_spike = "SPIKE" in raw_id.upper()
    prefix = ("SPIKE-" if is_spike else "TASK-") if upper else ("spike-" if is_spike else "task-")
    digits = re.sub(r"[^\d]", "", raw_id)
    if digits:
        clean_num = digits.lstrip("0")
        num_str = clean_num.zfill(4) if clean_num else "0000"
        return f"{prefix}{num_str}"
    return raw_id.upper() if upper else raw_id.lower()


def build_commit_subject(task_or_meta: Any, slice_type: str | None = None) -> str:
    """Formats conventional commit subject as <type>(<task-id>): <title>."""
    c_type = slice_type.strip().lower() if slice_type else derive_conventional_type(task_or_meta)
    task_id = _normalize_task_id(task_or_meta, upper=False)

    title = str(
        getattr(task_or_meta, "title", "")
        or (task_or_meta.get("title") if isinstance(task_or_meta, dict) else "")
    ).strip()
    title = re.sub(r"^(?:feat|refactor|spike|fix)\s*:\s*", "", title, flags=re.IGNORECASE).strip()
    if not title:
        title = "update"

    return f"{c_type}({task_id}): {title}"


def build_commit_trailers(
    task_or_meta: Any,
    slice_type: str | None = None,
    provenance: str = "spec-ops-worker (autonomous)",
) -> dict[str, str]:
    """Generates standardized RFC-822 git trailers dict for task commit."""
    c_type = slice_type.strip().lower() if slice_type else derive_conventional_type(task_or_meta)
    task_id = _normalize_task_id(task_or_meta, upper=True)

    trailers: dict[str, str] = {
        "SpecOps-Task": task_id,
        "SpecOps-Slice": c_type,
    }

    # Governing PRDs
    prds = (
        getattr(task_or_meta, "governing_prds", None)
        or getattr(task_or_meta, "governing_prd", None)
        or (task_or_meta.get("governing_prds") if isinstance(task_or_meta, dict) else None)
        or (task_or_meta.get("governing_prd") if isinstance(task_or_meta, dict) else None)
    )
    if prds:
        if isinstance(prds, str):
            val = prds.strip()
        else:
            val = ", ".join(str(p).strip() for p in prds if str(p).strip())
        if val:
            trailers["SpecOps-PRD"] = val

    # Governing ADRs
    adrs = (
        getattr(task_or_meta, "governing_adrs", None)
        or getattr(task_or_meta, "governing_adr", None)
        or (task_or_meta.get("governing_adrs") if isinstance(task_or_meta, dict) else None)
        or (task_or_meta.get("governing_adr") if isinstance(task_or_meta, dict) else None)
    )
    if adrs:
        if isinstance(adrs, str):
            val = adrs.strip()
        else:
            val = ", ".join(str(a).strip() for a in adrs if str(a).strip())
        if val:
            trailers["SpecOps-ADR"] = val

    # Provenance
    prov_val = str(provenance).strip() if provenance else "spec-ops-worker (autonomous)"
    trailers["Provenance"] = prov_val

    # Optional signed off by
    signer = (
        getattr(task_or_meta, "signed_off_by", None)
        or (task_or_meta.get("signed_off_by") if isinstance(task_or_meta, dict) else None)
    )
    if signer and str(signer).strip():
        trailers["SpecOps-Signed-By"] = str(signer).strip()

    return trailers


def format_task_commit_message(
    task_or_meta: Any,
    body: str = "",
    provenance: str = "spec-ops-worker (autonomous)",
) -> str:
    """Formats full squash commit message with Conventional Commit subject and RFC-822 trailers."""
    subject = build_commit_subject(task_or_meta)
    trailers = build_commit_trailers(task_or_meta, provenance=provenance)
    trailer_block = "\n".join(f"{k}: {v}" for k, v in trailers.items())

    clean_body = body.strip()
    if clean_body:
        return f"{subject}\n\n{clean_body}\n\n{trailer_block}\n"
    return f"{subject}\n\n{trailer_block}\n"


def parse_commit_trailers(commit_text: str) -> dict[str, str]:
    """Parses RFC-822 trailers from commit message or git log output."""
    trailers: dict[str, str] = {}
    for line in commit_text.strip().splitlines():
        line_clean = line.strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9_-]*)\s*:\s*(.+)$", line_clean)
        if m:
            key, val = m.group(1), m.group(2).strip()
            trailers[key] = val
    return trailers
