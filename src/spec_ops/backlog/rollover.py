"""Milestone scope transition and automated rollover engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0077.
Deals strictly with public domain contracts and keeps source under 400 lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any

from ..config.loader import SpecOpsConfig
from ..core.migration import parse_frontmatter_and_body
from ..core.roadmap import parse_roadmap_milestones


def normalize_ms_token(s: str) -> str:
    """Normalizes milestone identifier into clean lowercase alphanumeric token."""
    return re.sub(r"[\s\-_]+", "", str(s)).strip().lower()


def matches_milestone(candidate: Any, query: str) -> bool:
    """Evaluates whether candidate milestone metadata matches a target query identifier."""
    if candidate is None:
        return False
    cand_str = str(candidate).strip()
    query_str = str(query).strip()
    if not cand_str or not query_str:
        return False

    if cand_str.lower() == query_str.lower():
        return True

    cand_norm = normalize_ms_token(cand_str)
    query_norm = normalize_ms_token(query_str)
    if cand_norm == query_norm:
        return True

    cand_stripped = re.sub(r"^milestone", "", cand_norm)
    query_stripped = re.sub(r"^milestone", "", query_norm)
    if cand_stripped and query_stripped:
        if cand_stripped == query_stripped:
            return True
        if (
            cand_stripped.lstrip("m") == query_stripped.lstrip("m")
            and cand_stripped.lstrip("m").isdigit()
        ):
            return True

    if cand_norm.startswith(query_norm) or query_norm.startswith(cand_norm):
        m_cand = re.search(r"\d+", cand_str)
        m_query = re.search(r"\d+", query_str)
        if m_cand and m_query and m_cand.group(0) == m_query.group(0):
            return True

    return False


def update_frontmatter_milestone(
    content: str,
    from_milestone: str,
    to_milestone: str,
    force_update: bool = False,
) -> tuple[bool, str, str, str]:
    """Updates target milestone field in frontmatter while preserving all other bytes.

    Returns (was_modified, new_content, matched_key, old_value).
    """
    meta, raw_yaml, body = parse_frontmatter_and_body(content)
    if not meta:
        return False, content, "", ""

    matched_keys: list[tuple[str, str]] = []
    for k in ("target_release", "milestone", "target_milestone"):
        if k in meta and matches_milestone(meta[k], from_milestone):
            matched_keys.append((k, str(meta[k])))

    if not matched_keys and not force_update:
        return False, content, "", ""

    primary_key = matched_keys[0][0] if matched_keys else "target_release"
    old_val = matched_keys[0][1] if matched_keys else ""
    keys_to_update = [k for k, _ in matched_keys] if matched_keys else [primary_key]

    lines = raw_yaml.splitlines(keepends=True)
    new_lines: list[str] = []
    updated_keys: set[str] = set()

    for line in lines:
        replaced = False
        for k in keys_to_update:
            pattern = (
                r"^([ \t]*"
                + re.escape(k)
                + r"[ \t]*:[ \t]*)(['\"]?).*?\2([ \t]*(?:#.*)?)$"
            )
            m = re.match(pattern, line.rstrip("\r\n"))
            if m:
                indent_and_key = m.group(1)
                quote = m.group(2)
                comment = m.group(3) or ""

                if not quote and any(c in to_milestone for c in (":", "#", " ", "'", '"')):
                    val_str = f"'{to_milestone}'"
                elif quote:
                    val_str = f"{quote}{to_milestone}{quote}"
                else:
                    val_str = to_milestone

                eol = (
                    "\r\n"
                    if line.endswith("\r\n")
                    else ("\n" if line.endswith("\n") else "")
                )
                new_lines.append(f"{indent_and_key}{val_str}{comment}{eol}")
                updated_keys.add(k)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    newline = "\r\n" if "\r\n" in content[: content.find("\n") + 2] else "\n"
    for k in keys_to_update:
        if k not in updated_keys:
            if new_lines and not new_lines[-1].endswith(("\n", "\r")):
                new_lines[-1] += newline
            val_str = (
                f"'{to_milestone}'"
                if any(c in to_milestone for c in (":", "#", " ", "'", '"'))
                else to_milestone
            )
            new_lines.append(f"{k}: {val_str}{newline}")

    updated_raw_yaml = "".join(new_lines)
    if not updated_raw_yaml.endswith(("\n", "\r")):
        updated_raw_yaml += newline
    new_content = f"---{newline}{updated_raw_yaml}---{newline}{body}"

    return True, new_content, primary_key, old_val


@dataclass
class RolloverTaskDetail:
    task_id: str
    title: str
    file_path: Path
    stage: str
    old_milestone: str
    new_milestone: str


@dataclass
class RolloverResult:
    from_milestone: str
    to_milestone: str
    transitioned_count: int
    transitioned_tasks: list[str]
    dry_run: bool = False
    details: list[RolloverTaskDetail] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_milestone": self.from_milestone,
            "to_milestone": self.to_milestone,
            "transitioned_count": self.transitioned_count,
            "transitioned_tasks": self.transitioned_tasks,
            "dry_run": self.dry_run,
            "details": [
                {
                    "task_id": d.task_id,
                    "title": d.title,
                    "file_path": str(d.file_path),
                    "stage": d.stage,
                    "old_milestone": d.old_milestone,
                    "new_milestone": d.new_milestone,
                }
                for d in self.details
            ],
        }


class MilestoneRolloverCoordinator:
    """Coordinates automated milestone rollover transitions across backlog tasks."""

    def __init__(
        self,
        config_or_dir: SpecOpsConfig | Path | str,
        roadmap_path: Path | str | None = None,
    ) -> None:
        if isinstance(config_or_dir, SpecOpsConfig):
            self.backlog_dir = config_or_dir.backlog_dir
            self.roadmap_path = (
                Path(roadmap_path)
                if roadmap_path
                else config_or_dir.backlog_dir / "ROADMAP.md"
            )
        else:
            self.backlog_dir = Path(config_or_dir)
            self.roadmap_path = (
                Path(roadmap_path)
                if roadmap_path
                else self.backlog_dir / "ROADMAP.md"
            )

    def _get_roadmap_task_ids(self, from_milestone: str) -> set[str]:
        if not self.roadmap_path or not self.roadmap_path.exists():
            return set()
        milestones = parse_roadmap_milestones(self.roadmap_path)
        matched_ids: set[str] = set()
        for ms in milestones:
            if matches_milestone(ms.get("id"), from_milestone) or matches_milestone(
                ms.get("title"), from_milestone
            ):
                for tid in ms.get("tasks", []):
                    matched_ids.add(str(tid).upper())
        return matched_ids

    def rollover(
        self,
        from_milestone: str,
        to_milestone: str,
        dry_run: bool = False,
    ) -> RolloverResult:
        """Executes milestone rollover on uncompleted tasks (refined/ and proposed/)."""
        roadmap_task_ids = self._get_roadmap_task_ids(from_milestone)
        candidate_dirs = [
            ("refined", self.backlog_dir / "refined"),
            ("proposed", self.backlog_dir / "proposed"),
        ]

        transitioned_details: list[RolloverTaskDetail] = []
        transitioned_ids: list[str] = []

        for stage, target_dir in candidate_dirs:
            if not target_dir.exists():
                continue
            for fpath in sorted(target_dir.glob("*.md")):
                content = fpath.read_text(encoding="utf-8")
                meta, _, _ = parse_frontmatter_and_body(content)
                if not meta or "id" not in meta:
                    continue

                raw_status = str(meta.get("status", "")).strip().lower()
                if raw_status in ("complete", "graduated", "shipped"):
                    continue

                raw_id = str(meta.get("id", ""))
                clean_num = raw_id.replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
                canonical_id = f"TASK-{clean_num.zfill(4)}" if clean_num else raw_id

                is_in_roadmap = canonical_id.upper() in roadmap_task_ids

                was_modified, new_content, _, old_val = update_frontmatter_milestone(
                    content,
                    from_milestone=from_milestone,
                    to_milestone=to_milestone,
                    force_update=is_in_roadmap,
                )

                if was_modified:
                    if not dry_run:
                        tmp_path = fpath.with_name(f"{fpath.name}.{os.getpid()}.tmp")
                        try:
                            tmp_path.write_text(new_content, encoding="utf-8")
                            tmp_path.replace(fpath)
                        except Exception:
                            if tmp_path.exists():
                                tmp_path.unlink(missing_ok=True)
                            raise

                    detail = RolloverTaskDetail(
                        task_id=canonical_id,
                        title=str(meta.get("title", fpath.stem)),
                        file_path=fpath,
                        stage=stage,
                        old_milestone=old_val or from_milestone,
                        new_milestone=to_milestone,
                    )
                    transitioned_details.append(detail)
                    transitioned_ids.append(canonical_id)

        transitioned_details.sort(key=lambda d: d.task_id)
        transitioned_ids.sort()

        return RolloverResult(
            from_milestone=from_milestone,
            to_milestone=to_milestone,
            transitioned_count=len(transitioned_ids),
            transitioned_tasks=transitioned_ids,
            dry_run=dry_run,
            details=transitioned_details,
        )


def rollover_milestone(
    backlog_dir: Path | str,
    from_milestone: str,
    to_milestone: str,
    dry_run: bool = False,
    roadmap_path: Path | str | None = None,
) -> RolloverResult:
    """Convenience functional frontdoor for milestone scope rollover."""
    coordinator = MilestoneRolloverCoordinator(backlog_dir, roadmap_path=roadmap_path)
    return coordinator.rollover(from_milestone, to_milestone, dry_run=dry_run)
