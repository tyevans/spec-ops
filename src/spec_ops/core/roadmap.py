"""Roadmap milestone parsing and alignment utilities.

Governed by ADR-0007 and ADR-0021. Core foundation utilities for parsing ROADMAP.md
milestones and target horizons without upward visualizer dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_roadmap_milestones(roadmap_path: Path) -> list[dict[str, Any]]:
    """Parses ROADMAP.md into structured milestones with associated tasks."""
    if not roadmap_path.exists():
        return []

    text = roadmap_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    milestones: list[dict[str, Any]] = []
    current_ms: dict[str, Any] | None = None

    for line in lines:
        m = re.match(
            r"^##\s+(?:Milestone\s+)?([A-Za-z0-9\-]+)(?::\s*([^(\n]+))?(?:\s*\(([^)]+)\))?",
            line,
            re.IGNORECASE,
        )
        if m:
            if current_ms:
                milestones.append(current_ms)
            mid = m.group(1).strip()
            title = (m.group(2) or mid).strip()
            status = (m.group(3) or "Active").strip()
            current_ms = {
                "id": mid,
                "title": title,
                "status": status,
                "tasks": [],
                "horizon": "2026-10-15",
            }
            continue

        if current_ms:
            t_matches = re.findall(r"`?(TASK-\d+)`?", line)
            if t_matches:
                for tid in t_matches:
                    clean_id = f"TASK-{tid.split('-')[-1].zfill(4)}"
                    if clean_id not in current_ms["tasks"]:
                        current_ms["tasks"].append(clean_id)

            hor_match = re.search(
                r"(?:completion date|target horizon|horizon closed for)[^:]*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
                line,
                re.IGNORECASE,
            )
            if hor_match:
                current_ms["horizon"] = hor_match.group(1).strip()

    if current_ms:
        milestones.append(current_ms)

    return milestones
