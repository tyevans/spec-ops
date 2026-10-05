"""Architectural Decision Record (ADR) incremental amendment domain and cycle detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re
from typing import Any
import yaml

from ..core.parser import extract_frontmatter
from .supersede import (
    ADRNotFoundError,
    find_adr_file,
    normalize_adr_id,
    parse_adr_info,
    write_adr_frontmatter,
)


class CircularAmendmentError(ValueError):
    """Raised when an ADR amendment introduces a circular dependency loop."""


@dataclass
class AmendResult:
    """Atomic outcome of an ADR amendment operation."""

    old_id: str
    new_id: str
    old_file: Path
    new_file: Path
    warnings: list[str] = field(default_factory=list)


def discover_amended_adrs(adrs_dir: Path) -> dict[str, list[str]]:
    """Discovers all amendment relationships: {amending_id: [amended_target_ids]}."""
    amends_map: dict[str, list[str]] = {}
    if not adrs_dir.exists():
        return amends_map

    for p in adrs_dir.rglob("*.md"):
        if not p.is_file() or p.name in ("REGISTRY.md", "README.md"):
            continue
        try:
            content = p.read_text(encoding="utf-8")
            meta, body = extract_frontmatter(content)
            num_match = re.search(r"adr-(\d+)", p.stem, re.IGNORECASE)
            curr_id = normalize_adr_id(str(meta.get("id", num_match.group(0) if num_match else p.stem)))

            raw_amends = meta.get("amends")
            if raw_amends:
                items = [normalize_adr_id(str(x)) for x in raw_amends] if isinstance(raw_amends, list) else [normalize_adr_id(str(raw_amends))]
                for item in items:
                    amends_map.setdefault(curr_id, [])
                    if item not in amends_map[curr_id]:
                        amends_map[curr_id].append(item)

            # Also check amended_by on target ADRs to be robust
            raw_amended_by = meta.get("amended_by")
            if raw_amended_by:
                items = [normalize_adr_id(str(x)) for x in raw_amended_by] if isinstance(raw_amended_by, list) else [normalize_adr_id(str(raw_amended_by))]
                for item in items:
                    amends_map.setdefault(item, [])
                    if curr_id not in amends_map[item]:
                        amends_map[item].append(curr_id)

            # Check markdown body for mentions like "Amends [`ADR-XXXX`]"
            body_match = re.search(r"amends\s+(?:\[`?)?(ADR-\d+)", body, re.IGNORECASE)
            if body_match:
                tgt = normalize_adr_id(body_match.group(1))
                amends_map.setdefault(curr_id, [])
                if tgt not in amends_map[curr_id]:
                    amends_map[curr_id].append(tgt)
        except OSError:
            continue

    return amends_map


def discover_amendments_by_target(adrs_dir: Path) -> dict[str, list[str]]:
    """Discovers reverse amendment relationships: {target_adr_id: [amending_adr_ids]}."""
    target_map: dict[str, list[str]] = {}
    forward_map = discover_amended_adrs(adrs_dir)
    for amending_id, targets in forward_map.items():
        for tgt in targets:
            target_map.setdefault(tgt, [])
            if amending_id not in target_map[tgt]:
                target_map[tgt].append(amending_id)
    return target_map


def detect_amendment_cycles(
    existing_map: dict[str, list[str]],
    new_pair: tuple[str, str] | None = None,
) -> None:
    """Validates that adding (new_amending_id -> old_target_id) does not create circular amendment."""
    temp_map: dict[str, list[str]] = {k: list(v) for k, v in existing_map.items()}
    if new_pair is not None:
        amending_id, target_id = new_pair
        if amending_id == target_id:
            raise CircularAmendmentError(f"ADR {amending_id} cannot amend itself.")
        temp_map.setdefault(amending_id, [])
        if target_id not in temp_map[amending_id]:
            temp_map[amending_id].append(target_id)

    # Standard DFS cycle detection
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)

        for neighbor in temp_map.get(node, []):
            if neighbor in stack:
                cycle_idx = stack.index(neighbor)
                cycle_nodes = stack[cycle_idx:] + [neighbor]
                cycle_str = " -> ".join(cycle_nodes)
                raise CircularAmendmentError(f"Circular ADR amendment detected: {cycle_str}")
            if neighbor not in visited:
                dfs(neighbor)

        stack.pop()

    for start_node in list(temp_map.keys()):
        if start_node not in visited:
            dfs(start_node)


def update_registry_amendment(
    registry_file: Path,
    old_id: str,
    new_id: str,
    new_title: str = "",
    new_date: str | None = None,
) -> None:
    """Updates REGISTRY.md table rows for old and new ADRs without marking old as Superseded."""
    if not registry_file.exists():
        return

    content = registry_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated_lines: list[str] = []
    new_found = False

    row_pattern = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$")

    for line in lines:
        m = row_pattern.match(line.strip())
        if m:
            row_id = normalize_adr_id(m.group(1))
            row_title = m.group(2).strip()
            row_status = m.group(3).strip()
            row_date = m.group(4).strip()

            if row_id == old_id:
                # Do NOT mark as Superseded; maintain Accepted status
                clean_status = "Accepted" if "superseded" not in row_status.lower() else row_status
                updated_lines.append(f"| {row_id} | {row_title} | {clean_status} | {row_date} |")
                continue

            if row_id == new_id:
                updated_lines.append(f"| {row_id} | {row_title} | Accepted | {row_date} |")
                new_found = True
                continue

        updated_lines.append(line)

    if not new_found and new_id:
        target_date = new_date or date.today().isoformat()
        target_title = new_title or new_id
        updated_lines.append(f"| {new_id} | {target_title} | Accepted | {target_date} |")

    registry_file.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")
