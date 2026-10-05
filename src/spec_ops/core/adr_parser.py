"""ADR markdown parser for SpecOps."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .models import ADR


def parse_adr(file_path: Path) -> ADR:
    """Parses an ADR markdown file."""
    from .parser import extract_frontmatter

    content = file_path.read_text(encoding="utf-8")
    meta, body = extract_frontmatter(content)
    num_match = re.search(r"adr-(\d+)", file_path.stem, re.IGNORECASE)
    raw_id = (
        f"ADR-{num_match.group(1).zfill(4)}"
        if num_match
        else str(meta.get("id", file_path.stem.upper()))
    )
    clean_title = str(meta.get("title", ""))
    if not clean_title:
        title_line = (
            body.strip().splitlines()[0]
            if body.strip()
            else (content.splitlines()[0] if content else file_path.stem)
        )
        clean_title = re.sub(r"^#\s*(ADR-\d+:\s*)?", "", title_line).strip()

    status = str(meta.get("status", "Accepted"))
    domain = str(meta.get("domain", "Architecture"))

    ctx_m = re.search(r"## Context\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    dec_m = re.search(r"## Decision\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    con_m = re.search(r"## Consequences\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)

    supersedes = str(meta.get("supersedes", "") or "")
    superseded_by = str(meta.get("superseded_by", "") or "")

    raw_amends = meta.get("amends", [])
    if isinstance(raw_amends, list):
        amends = [str(x).upper() for x in raw_amends if str(x).strip()]
    elif raw_amends:
        amends = [str(raw_amends).upper()]
    else:
        amends = []

    raw_amended_by = meta.get("amended_by", [])
    if isinstance(raw_amended_by, list):
        amended_by = [str(x).upper() for x in raw_amended_by if str(x).strip()]
    elif raw_amended_by:
        amended_by = [str(raw_amended_by).upper()]
    else:
        amended_by = []

    return ADR(
        id=raw_id,
        title=clean_title,
        status=status,
        domain=domain,
        context=ctx_m.group(1).strip() if ctx_m else "",
        decision=dec_m.group(1).strip() if dec_m else "",
        consequences=con_m.group(1).strip() if con_m else "",
        raw_markdown=content,
        file_path=file_path,
        supersedes=supersedes,
        superseded_by=superseded_by,
        amends=amends,
        amended_by=amended_by,
    )
