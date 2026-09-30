"""CLI handler for ergonomic task authoring and Definition of Ready scaffolding."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from ..backlog.dor import validate_task_dor
from ..config.models import SpecOpsConfig


def get_next_task_number(backlog_dir: Path) -> int:
    """Calculates the next sequential integer task number across backlog and PRIORITY.md."""
    max_id = 0
    if backlog_dir.exists():
        for p in backlog_dir.rglob("*.md"):
            m = re.match(r"^(\d+)", p.stem)
            if m:
                max_id = max(max_id, int(m.group(1)))

    p_file = backlog_dir / "PRIORITY.md"
    if p_file.is_file():
        content = p_file.read_text(encoding="utf-8")
        for m in re.finditer(r"TASK-(\d+)", content):
            max_id = max(max_id, int(m.group(1)))

    return max_id + 1


def slugify_task_title(title: str) -> str:
    """Generates a clean filesystem-safe slug from a task title."""
    cleaned = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:50] or "task"


def normalize_id_list(raw_items: list[str] | None, prefix: str) -> list[str]:
    """Normalizes a list of identifier strings (e.g. PRD-0001, 1 -> PRD-0001)."""
    if not raw_items:
        return []
    result: list[str] = []
    for item in raw_items:
        for part in str(item).split(","):
            token = part.strip()
            if not token:
                continue
            digits = re.search(r"\d+", token)
            if digits:
                num = int(digits.group(0))
                cid = f"{prefix}-{num:04d}"
            else:
                cid = token.upper()
            if cid not in result:
                result.append(cid)
    return result


def append_task_to_priority(
    backlog_dir: Path, canonical_id: str, stage: str, filename: str
) -> None:
    """Appends newly generated task to PRIORITY.md if not already indexed."""
    priority_file = backlog_dir / "PRIORITY.md"
    if not priority_file.exists():
        return
    content = priority_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    status_label = stage.capitalize()
    folder = "refined" if status_label == "Refined" else "proposed"
    stem = Path(filename).stem
    entry = f"- **{canonical_id} ({status_label})**: [`{stem}`]({folder}/{filename})"

    if entry not in lines and canonical_id not in content:
        lines.append(entry)
        priority_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scaffold_task_file(
    backlog_dir: Path,
    title: str,
    target_bc: str = "worker",
    governing_prds: list[str] | None = None,
    governing_stories: list[str] | None = None,
    governing_adrs: list[str] | None = None,
    dependencies: list[str] | None = None,
    stage: str = "proposed",
    summary: str = "",
    problem: str = "",
) -> tuple[str, Path]:
    """Creates a structured PMaC task markdown file and synchronizes PRIORITY.md."""
    next_num = get_next_task_number(backlog_dir)
    num_str = f"{next_num:04d}"
    canonical_id = f"TASK-{num_str}"
    slug = slugify_task_title(title)
    filename = f"{num_str}-{slug}.md"

    stage_folder = "refined" if stage.lower() == "refined" else "proposed"
    dest_dir = backlog_dir / stage_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / filename

    meta: dict[str, Any] = {
        "id": num_str,
        "title": title,
        "status": stage.capitalize(),
    }
    if dependencies:
        meta["dependencies"] = dependencies
    if governing_adrs:
        meta["governing_adrs"] = governing_adrs
    if governing_prds:
        meta["governing_prds"] = governing_prds
    if governing_stories:
        meta["governing_stories"] = governing_stories
    if target_bc:
        meta["target_bc"] = target_bc

    yaml_block = yaml.dump(meta, sort_keys=False).strip()

    body = f"""# {canonical_id}: {title}

## Summary
{summary or title}

## Problem Statement & Context
{problem or f"Task {canonical_id} implements {title} in bounded context {target_bc}."}

## Definition of Done (Blackbox Frontdoor TDD)
1. Public interfaces or standard domain contracts implemented.
2. Verified via automated blackbox tests without private backdoor manipulation.
3. All new source files strictly under 500 lines.
"""

    dest_file.write_text(f"---\n{yaml_block}\n---\n\n{body}\n", encoding="utf-8")
    append_task_to_priority(backlog_dir, canonical_id, stage, filename)

    return canonical_id, dest_file


def handle_task_command(
    args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser
) -> int:
    """Dispatches task CLI subcommands."""
    action = getattr(args, "task_action", None)
    if not action:
        try:
            parser.parse_args(["task", "--help"])
        except SystemExit:
            pass
        return 0

    if action == "create":
        title = getattr(args, "title", None)
        bc = getattr(args, "target_bc", None)
        raw_prds = getattr(args, "prd", None) or []
        raw_stories = getattr(args, "story", None) or []
        raw_adrs = getattr(args, "adr", None) or []
        raw_deps = getattr(args, "dependencies", None) or []
        stage = getattr(args, "stage", "proposed") or "proposed"
        non_interactive = getattr(args, "non_interactive", False)

        # Interactive prompts if required fields are missing and interactive
        is_interactive = not non_interactive and (
            not title or not bc or not raw_prds or not raw_stories
        ) and sys.stdin.isatty()

        if is_interactive:
            print("\n📝 SpecOps Interactive Task Authoring")
            if not title:
                title = input("Task Title: ").strip()
            if not bc:
                bc = input("Target Bounded Context [worker]: ").strip() or "worker"
            if not raw_prds:
                p_in = input("Governing PRD (e.g. PRD-0001): ").strip()
                if p_in:
                    raw_prds = [p_in]
            if not raw_stories:
                s_in = input("Governing Story (e.g. US-0002): ").strip()
                if s_in:
                    raw_stories = [s_in]
            if not raw_adrs:
                a_in = input("Governing ADRs (comma-separated, optional): ").strip()
                if a_in:
                    raw_adrs = [a_in]

        if not title:
            print("❌ Error: Task title is required (--title <title>).", file=sys.stderr)
            return 1

        target_bc = bc or "worker"
        prds = normalize_id_list(raw_prds, "PRD")
        stories = normalize_id_list(raw_stories, "US")
        adrs = normalize_id_list(raw_adrs, "ADR")
        deps = normalize_id_list(raw_deps, "TASK")

        # Validate DoR if promoting or scaffolding straight to refined
        if stage.lower() == "refined":
            task_dict: dict[str, Any] = {
                "title": title,
                "target_bc": target_bc,
                "governing_prds": prds,
                "governing_stories": stories,
                "governing_adrs": adrs,
            }
            dor_ok, dor_errors = validate_task_dor(task_dict, config)
            if not dor_ok:
                print("❌ Definition of Ready (DoR) validation failed for promotion to refined:")
                for err in dor_errors:
                    print(f"   • {err}")
                return 1

        cid, created_file = scaffold_task_file(
            backlog_dir=config.backlog_dir,
            title=title,
            target_bc=target_bc,
            governing_prds=prds,
            governing_stories=stories,
            governing_adrs=adrs,
            dependencies=deps,
            stage=stage,
        )

        print(f"✨ Scaffolding complete: Created task {cid} under {created_file}")
        return 0

    try:
        parser.parse_args(["task", "--help"])
    except SystemExit:
        pass
    return 0
