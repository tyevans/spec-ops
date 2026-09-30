"""Specification frontmatter automated migration and in-place rewrite engine."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

import yaml

from .schema_validator import collect_specification_files, detect_document_type


def canonicalize_adr_id(val: Any) -> str:
    """Normalizes an ADR reference into canonical ADR-XXXX format."""
    s = str(val).strip()
    if s.isdigit():
        return f"ADR-{s.zfill(4)}"
    m = re.match(r"^ADR-?0*(\d+)$", s, re.IGNORECASE)
    if m:
        return f"ADR-{m.group(1).zfill(4)}"
    return s


def canonicalize_prd_id(val: Any) -> str:
    """Normalizes a PRD reference into canonical PRD-XXXX format."""
    s = str(val).strip()
    if s.isdigit():
        return f"PRD-{s.zfill(4)}"
    m = re.match(r"^PRD-?0*(\d+)$", s, re.IGNORECASE)
    if m:
        return f"PRD-{m.group(1).zfill(4)}"
    return s


def canonicalize_story_id(val: Any) -> str:
    """Normalizes a User Story reference into canonical US-XXXX format."""
    s = str(val).strip()
    if s.isdigit():
        return f"US-{s.zfill(4)}"
    m = re.match(r"^US-?0*(\d+)$", s, re.IGNORECASE)
    if m:
        return f"US-{m.group(1).zfill(4)}"
    return s


def canonicalize_task_id(val: Any) -> str:
    """Normalizes a Task reference into canonical TASK-XXXX format."""
    s = str(val).strip()
    if s.isdigit():
        return f"TASK-{s.zfill(4)}"
    m = re.match(r"^TASK-?0*(\d+)$", s, re.IGNORECASE)
    if m:
        return f"TASK-{m.group(1).zfill(4)}"
    return s


def parse_frontmatter_and_body(content: str) -> tuple[dict[str, Any], str, str]:
    """Extracts frontmatter metadata dict, raw YAML string, and markdown body verbatim.

    Guarantees 100% byte-for-byte preservation of the non-frontmatter body.
    """
    if not content.startswith("---"):
        return {}, "", content

    first_newline = content.find("\n")
    if first_newline == -1:
        return {}, "", content

    # Match closing '---' preceded by a newline and followed by horizontal spaces and a newline
    m = re.search(r"(\r?\n)---[ \t]*(\r?\n|\Z)", content[first_newline:])
    if not m:
        return {}, "", content

    closing_start = first_newline + m.start()
    closing_end = first_newline + m.end()

    raw_yaml = content[first_newline + 1 : closing_start]
    body = content[closing_end:]

    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        return {}, raw_yaml, body

    if not isinstance(data, dict):
        return {}, raw_yaml, body

    return data, raw_yaml, body


def to_list_value(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return list(val)
    return [val]


def migrate_task_metadata(meta: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Upgrades legacy fields in a Task frontmatter dictionary."""
    migrated = dict(meta)
    was_modified = False

    # 1. governing_adr -> governing_adrs
    if "governing_adr" in migrated:
        raw_val = migrated.pop("governing_adr")
        new_adrs = [canonicalize_adr_id(x) for x in to_list_value(raw_val)]
        existing = [canonicalize_adr_id(x) for x in to_list_value(migrated.get("governing_adrs", []))]
        combined = list(dict.fromkeys(existing + new_adrs))
        migrated["governing_adrs"] = combined
        was_modified = True

    # 2. governing_prd / prd -> governing_prds
    if "governing_prd" in migrated or "prd" in migrated:
        raw_prds = to_list_value(migrated.pop("governing_prd", None)) + to_list_value(migrated.pop("prd", None))
        new_prds = [canonicalize_prd_id(x) for x in raw_prds]
        existing = [canonicalize_prd_id(x) for x in to_list_value(migrated.get("governing_prds", []))]
        combined = list(dict.fromkeys(existing + new_prds))
        migrated["governing_prds"] = combined
        was_modified = True

    # 3. governing_story / story / stories -> governing_stories
    if "governing_story" in migrated or "story" in migrated or "stories" in migrated:
        raw_stories = (
            to_list_value(migrated.pop("governing_story", None))
            + to_list_value(migrated.pop("story", None))
            + to_list_value(migrated.pop("stories", None))
        )
        new_stories = [canonicalize_story_id(x) for x in raw_stories]
        existing = [canonicalize_story_id(x) for x in to_list_value(migrated.get("governing_stories", []))]
        combined = list(dict.fromkeys(existing + new_stories))
        migrated["governing_stories"] = combined
        was_modified = True

    # 4. dependency -> dependencies
    if "dependency" in migrated:
        raw_deps = to_list_value(migrated.pop("dependency"))
        new_deps = [canonicalize_task_id(x) for x in raw_deps]
        existing = [canonicalize_task_id(x) for x in to_list_value(migrated.get("dependencies", []))]
        combined = list(dict.fromkeys(existing + new_deps))
        migrated["dependencies"] = combined
        was_modified = True

    # Standardize field ordering
    standard_order = [
        "id",
        "title",
        "status",
        "dependencies",
        "governing_adrs",
        "governing_prds",
        "governing_stories",
        "target_bc",
    ]
    reordered: dict[str, Any] = {}
    for key in standard_order:
        if key in migrated:
            reordered[key] = migrated[key]
    for key, value in migrated.items():
        if key not in reordered:
            reordered[key] = value

    return reordered, was_modified


def migrate_story_metadata(meta: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Upgrades legacy fields in a User Story frontmatter dictionary."""
    migrated = dict(meta)
    was_modified = False

    if "governing_prds" in migrated:
        val = migrated.pop("governing_prds")
        lst = to_list_value(val)
        migrated["governing_prd"] = canonicalize_prd_id(lst[0]) if lst else ""
        was_modified = True
    elif "prd" in migrated:
        val = migrated.pop("prd")
        migrated["governing_prd"] = canonicalize_prd_id(val)
        was_modified = True
    elif "governing_prd" in migrated:
        can = canonicalize_prd_id(migrated["governing_prd"])
        if can != str(migrated["governing_prd"]):
            migrated["governing_prd"] = can
            was_modified = True

    return migrated, was_modified


def migrate_prd_metadata(meta: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Upgrades legacy fields in a PRD frontmatter dictionary."""
    migrated = dict(meta)
    was_modified = False

    if "target_bc" in migrated and "component" not in migrated:
        migrated["component"] = migrated.pop("target_bc")
        was_modified = True
    if "target_personas" in migrated and "target_persona" not in migrated:
        val = migrated.pop("target_personas")
        migrated["target_persona"] = val if isinstance(val, str) else ", ".join(str(x) for x in val)
        was_modified = True

    return migrated, was_modified


def migrate_frontmatter(meta: dict[str, Any], doc_type: str = "task") -> tuple[dict[str, Any], bool]:
    """Dispatches frontmatter migration based on document type."""
    if doc_type == "task":
        return migrate_task_metadata(meta)
    if doc_type == "story":
        return migrate_story_metadata(meta)
    if doc_type == "prd":
        return migrate_prd_metadata(meta)
    return dict(meta), False


def migrate_document_content(
    content: str, doc_type: str = "task", file_path: str = ""
) -> tuple[str, bool]:
    """Migrates specification document frontmatter preserving body content byte-for-byte."""
    meta, raw_yaml, body = parse_frontmatter_and_body(content)
    if not meta:
        return content, False

    migrated_meta, was_modified = migrate_frontmatter(meta, doc_type)
    if not was_modified:
        return content, False

    newline = "\r\n" if "\r\n" in content[:content.find("\n") + 2] else "\n"
    new_yaml = yaml.dump(migrated_meta, sort_keys=False, default_flow_style=False)
    # Ensure new_yaml uses the appropriate newline
    if newline != "\n":
        new_yaml = new_yaml.replace("\n", newline)

    new_content = f"---{newline}{new_yaml}---{newline}{body}"
    if new_content == content:
        return content, False

    return new_content, True


def generate_unified_diff(original: str, modified: str, file_path: str = "") -> str:
    """Generates a standard unified diff string between original and migrated content."""
    rel = file_path if file_path else "specification.md"
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )
    return "".join(diff_lines)


def migrate_file(file_path: Path, in_place: bool = False) -> tuple[bool, str, str]:
    """Migrates a single specification file on disk.

    Returns (was_modified, unified_diff_text, new_content).
    """
    try:
        original = file_path.read_text(encoding="utf-8")
    except OSError:
        return False, "", ""

    doc_type = detect_document_type(file_path)
    new_content, was_modified = migrate_document_content(original, doc_type=doc_type, file_path=str(file_path))
    if not was_modified:
        return False, "", original

    diff_text = generate_unified_diff(original, new_content, file_path=str(file_path))
    if in_place:
        file_path.write_text(new_content, encoding="utf-8")

    return True, diff_text, new_content


def migrate_specifications(
    root_dir: Path, target_path: Path | None = None, in_place: bool = False
) -> tuple[int, str, list[Path]]:
    """Migrates specification files across the target directory or workspace.

    Returns (modified_count, combined_diff_text, list_of_modified_files).
    """
    target = target_path if target_path is not None else (root_dir / "docs" / "project")
    if not target.exists():
        return 0, "", []

    spec_files = collect_specification_files(target)
    modified_files: list[Path] = []
    diff_chunks: list[str] = []

    for path in spec_files:
        was_mod, diff_text, _ = migrate_file(path, in_place=in_place)
        if was_mod:
            modified_files.append(path)
            if diff_text:
                diff_chunks.append(diff_text)

    combined_diff = "".join(diff_chunks)
    return len(modified_files), combined_diff, modified_files
