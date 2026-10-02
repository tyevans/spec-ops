"""Task memory and frontmatter parsing utilities.

Governed by ADR-0007, ADR-0020, and ADR-0021. Core utilities for parsing failure history
and invariant identifiers from task specifications without upward dependencies.
"""

from __future__ import annotations

import re
from typing import Any

import yaml


def extract_failed_invariants(reason: str) -> list[str]:
    """Extracts ADR invariant identifiers mentioned in a failure reason string."""
    found = re.findall(r"\bADR-\d{4}\b", reason, re.IGNORECASE)
    seen: set[str] = set()
    result: list[str] = []
    for inv in found:
        upper = inv.upper()
        if upper not in seen:
            seen.add(upper)
            result.append(upper)
    return result


def parse_task_memory(content: str) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    """Extracts frontmatter metadata dict, markdown body verbatim, and failure_history entries."""
    if not content.startswith("---"):
        return {}, content, []

    first_newline = content.find("\n")
    if first_newline == -1:
        return {}, content, []

    m = re.search(r"(\r?\n)---[ \t]*(\r?\n|\Z)", content[first_newline:])
    if not m:
        return {}, content, []

    closing_start = first_newline + m.start()
    closing_end = first_newline + m.end()

    raw_yaml = content[first_newline + 1 : closing_start]
    body = content[closing_end:]

    try:
        data = yaml.safe_load(raw_yaml) or {}
    except Exception:
        return {}, content, []

    if not isinstance(data, dict):
        return {}, content, []

    raw_history = data.get("failure_history", [])
    history: list[dict[str, Any]] = []
    if isinstance(raw_history, list):
        for item in raw_history:
            if isinstance(item, dict):
                history.append(dict(item))

    return data, body, history
