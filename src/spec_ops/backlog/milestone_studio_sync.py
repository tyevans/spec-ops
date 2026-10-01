"""Atomic frontmatter and ROADMAP.md synchronization for Milestone Studio.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0025.
Target Bounded Context: backlog. Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import os
from pathlib import Path
import re

from ..core.migration import canonicalize_task_id, parse_frontmatter_and_body
from .rollover import matches_milestone


def update_task_frontmatter_milestone(
    content: str,
    new_milestone: str,
    execution_profile: str | None = None,
) -> tuple[bool, str]:
    """Updates target milestone in task frontmatter while preserving all other bytes."""
    meta, raw_yaml, body = parse_frontmatter_and_body(content)
    if not meta:
        return False, content

    milestone_keys = [k for k in ("milestone", "target_milestone", "target_release") if k in meta]
    key_to_update = milestone_keys[0] if milestone_keys else "milestone"

    lines = raw_yaml.splitlines(keepends=True)
    new_lines: list[str] = []
    milestone_updated = False
    profile_updated = False

    for line in lines:
        replaced = False
        # Match milestone key
        m_ms = re.match(
            r"^([ \t]*" + re.escape(key_to_update) + r"[ \t]*:[ \t]*)(['\"]?).*?\2([ \t]*(?:#.*)?)$",
            line.rstrip("\r\n"),
        )
        if m_ms:
            indent_key = m_ms.group(1)
            quote = m_ms.group(2)
            comment = m_ms.group(3) or ""
            val_str = (
                f"{quote}{new_milestone}{quote}"
                if quote
                else (f"'{new_milestone}'" if any(c in new_milestone for c in (":", "#", " ", "'", '"')) else new_milestone)
            )
            eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
            new_lines.append(f"{indent_key}{val_str}{comment}{eol}")
            milestone_updated = True
            replaced = True

        # Match execution profile if specified
        if execution_profile:
            m_ep = re.match(
                r"^([ \t]*execution_profile[ \t]*:[ \t]*)(['\"]?).*?\2([ \t]*(?:#.*)?)$",
                line.rstrip("\r\n"),
            )
            if m_ep:
                indent_key = m_ep.group(1)
                comment = m_ep.group(3) or ""
                eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
                new_lines.append(f"{indent_key}{execution_profile}{comment}{eol}")
                profile_updated = True
                replaced = True

        if not replaced:
            new_lines.append(line)

    newline = "\r\n" if "\r\n" in content[: content.find("\n") + 2] else "\n"
    if not milestone_updated:
        if new_lines and not new_lines[-1].endswith(("\n", "\r")):
            new_lines[-1] += newline
        val_str = f"'{new_milestone}'" if any(c in new_milestone for c in (":", "#", " ", "'", '"')) else new_milestone
        new_lines.append(f"{key_to_update}: {val_str}{newline}")

    if execution_profile and not profile_updated:
        if new_lines and not new_lines[-1].endswith(("\n", "\r")):
            new_lines[-1] += newline
        new_lines.append(f"execution_profile: {execution_profile}{newline}")

    updated_yaml = "".join(new_lines)
    if not updated_yaml.endswith(("\n", "\r")):
        updated_yaml += newline

    new_content = f"---{newline}{updated_yaml}---{newline}{body}"
    return True, new_content


def sync_roadmap_milestone(
    roadmap_path: Path,
    task_id: str,
    task_title: str,
    target_milestone: str,
) -> bool:
    """Synchronizes task milestone assignment to ROADMAP.md atomically."""
    clean_id = canonicalize_task_id(task_id).upper()
    bullet_line = f"- {task_title} (`{clean_id}`)."

    if not roadmap_path.exists():
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"# Delivery Roadmap\n\n## {target_milestone} (Active)\n{bullet_line}\n"
        atomic_write(roadmap_path, content)
        return True

    text = roadmap_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 1. Strip existing bullet for this task
    filtered_lines: list[str] = []
    for l in lines:
        if re.search(rf"\(`?{clean_id}`?\)", l):
            continue
        filtered_lines.append(l)

    # 2. Locate target milestone section
    ms_indices: list[tuple[int, str]] = []
    for idx, l in enumerate(filtered_lines):
        m = re.match(r"^##\s+(?:Milestone\s+)?([A-Za-z0-9\-]+)(?::\s*([^(\n]+))?", l, re.IGNORECASE)
        if m:
            full_title = f"{m.group(1)}: {m.group(2) or ''}".strip(": ")
            ms_indices.append((idx, full_title))

    target_idx = -1
    for idx, m_title in ms_indices:
        if matches_milestone(m_title, target_milestone):
            target_idx = idx
            break

    if target_idx != -1:
        next_sec_idx = len(filtered_lines)
        for idx, _ in ms_indices:
            if idx > target_idx:
                next_sec_idx = idx
                break

        insert_at = next_sec_idx
        for i in range(next_sec_idx - 1, target_idx, -1):
            line_str = filtered_lines[i].strip()
            if line_str.startswith("-"):
                insert_at = i + 1
                break
            if not line_str:
                insert_at = i

        filtered_lines.insert(insert_at, bullet_line)
    else:
        filtered_lines.append("")
        filtered_lines.append(f"## {target_milestone} (Active)")
        filtered_lines.append(bullet_line)

    new_content = "\n".join(filtered_lines) + "\n"
    atomic_write(roadmap_path, new_content)
    return True


def atomic_write(path: Path, content: str) -> None:
    """Writes content to target path atomically using a temporary file and replace."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
