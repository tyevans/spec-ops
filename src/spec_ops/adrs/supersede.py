"""Architectural Decision Record (ADR) supersession and deprecation workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re
from typing import Any
import yaml

from ..core.parser import extract_frontmatter


class CircularSupersessionError(ValueError):
    """Raised when an ADR supersession introduces a circular dependency loop."""


class ADRNotFoundError(FileNotFoundError):
    """Raised when an ADR specification cannot be located on disk."""


@dataclass
class SupersedeResult:
    """Atomic outcome of an ADR supersession operation."""

    old_id: str
    new_id: str
    old_file: Path
    new_file: Path
    warnings: list[str] = field(default_factory=list)


def normalize_adr_id(adr_input: str | Path) -> str:
    """Normalizes any ADR identifier, filename, or string into canonical ADR-XXXX format."""
    s = Path(adr_input).name if isinstance(adr_input, Path) else str(adr_input).strip()
    m_stem = re.search(r"adr-(\d+)", s, re.IGNORECASE)
    if m_stem:
        return f"ADR-{int(m_stem.group(1)):04d}"
    m_num = re.search(r"^\d+$", s)
    if m_num:
        return f"ADR-{int(m_num.group(0)):04d}"
    m_adr = re.search(r"ADR-(\d+)", s, re.IGNORECASE)
    if m_adr:
        return f"ADR-{int(m_adr.group(1)):04d}"
    return s.upper()


def find_adr_file(adrs_dir: Path, target: str | Path) -> Path:
    """Locates an ADR markdown file within the ADR directory by path or canonical ID."""
    p_direct = Path(str(target))
    if p_direct.is_file():
        return p_direct.resolve()

    for base in [adrs_dir, adrs_dir.parent, adrs_dir.parent.parent]:
        p_check = base / str(target)
        if p_check.is_file():
            return p_check.resolve()

    canon_id = normalize_adr_id(target)
    m = re.search(r"\d+", canon_id)
    num = int(m.group(0)) if m else None

    candidates: list[Path] = []
    if adrs_dir.exists():
        for p in adrs_dir.rglob("*.md"):
            if not p.is_file() or p.name in ("REGISTRY.md", "README.md"):
                continue
            if canon_id.lower() in p.stem.lower():
                return p.resolve()
            if num is not None and (f"adr-{num:04d}" in p.stem.lower() or f"adr-{num}" in p.stem.lower()):
                return p.resolve()
            candidates.append(p)

    for p in candidates:
        try:
            content = p.read_text(encoding="utf-8")
            meta, _ = extract_frontmatter(content)
            fid = meta.get("id")
            if fid and normalize_adr_id(str(fid)) == canon_id:
                return p.resolve()
            first_line = content.splitlines()[0] if content else ""
            if canon_id in first_line.upper():
                return p.resolve()
        except OSError:
            continue

    raise ADRNotFoundError(f"Governing ADR '{target}' could not be located under {adrs_dir}.")


def parse_adr_info(path: Path) -> tuple[dict[str, Any], str, str, str]:
    """Reads ADR markdown file returning (metadata_dict, body_text, title, canonical_id)."""
    content = path.read_text(encoding="utf-8")
    meta, body = extract_frontmatter(content)

    num_match = re.search(r"adr-(\d+)", path.stem, re.IGNORECASE)
    canon_id = f"ADR-{int(num_match.group(1)):04d}" if num_match else path.stem.upper()
    if meta.get("id"):
        canon_id = normalize_adr_id(str(meta["id"]))

    title = ""
    if meta.get("title") is not None:
        raw = str(meta["title"]).strip()
        if raw:
            title = raw

    if not title:
        for line in (body or content).splitlines():
            line_str = line.strip()
            if line_str.startswith("#"):
                clean = re.sub(r"^#+\s*(ADR-\d+:\s*)?", "", line_str).strip()
                if clean:
                    title = clean
                    break
    if not title:
        title = path.stem

    return meta, body, title, canon_id


def write_adr_frontmatter(path: Path, meta: dict[str, Any], body: str) -> None:
    """Serializes updated YAML frontmatter and body into target ADR file."""
    yaml_str = yaml.dump(meta, sort_keys=False, default_flow_style=False).strip()
    clean_body = body.strip()
    if clean_body:
        rendered = f"---\n{yaml_str}\n---\n\n{clean_body}\n"
    else:
        rendered = f"---\n{yaml_str}\n---\n"
    path.write_text(rendered, encoding="utf-8")


def discover_superseded_adrs(adrs_dir: Path) -> dict[str, str]:
    """Discovers all superseded ADR relationships: {superseded_adr_id: active_adr_id}."""
    superseded_map: dict[str, str] = {}
    if not adrs_dir.exists():
        return superseded_map

    # 1. Inspect REGISTRY.md
    registry_file = adrs_dir / "REGISTRY.md"
    if registry_file.exists():
        for line in registry_file.read_text(encoding="utf-8").splitlines():
            m = re.search(r"(ADR-\d+).*?Superseded\s*(?:\(by\s*(ADR-\d+)\))?", line, re.IGNORECASE)
            if m and m.group(2):
                superseded_map[normalize_adr_id(m.group(1))] = normalize_adr_id(m.group(2))

    # 2. Inspect individual ADR files
    for p in adrs_dir.rglob("*.md"):
        if not p.is_file() or p.name in ("REGISTRY.md", "README.md"):
            continue
        try:
            content = p.read_text(encoding="utf-8")
            meta, body = extract_frontmatter(content)
            adr_id_match = re.search(r"ADR-\d+", p.stem.upper())
            curr_id = normalize_adr_id(str(meta.get("id", adr_id_match.group(0) if adr_id_match else "")))

            superseded_by = meta.get("superseded_by")
            if superseded_by and curr_id:
                superseded_map[curr_id] = normalize_adr_id(str(superseded_by))

            body_match = re.search(r"Superseded\s+by\s+(?:\[`?)?(ADR-\d+)", body, re.IGNORECASE)
            if body_match and curr_id:
                superseded_map[curr_id] = normalize_adr_id(body_match.group(1))
        except OSError:
            continue

    # Flatten transitive links
    for old_id, new_id in list(superseded_map.items()):
        target = new_id
        visited = {old_id}
        while target in superseded_map and target not in visited:
            visited.add(target)
            target = superseded_map[target]
        superseded_map[old_id] = target

    return superseded_map


def detect_supersession_cycles(existing_map: dict[str, str], new_pair: tuple[str, str]) -> None:
    """Validates that adding (old_id -> new_id) does not create circular supersession."""
    old_id, new_id = new_pair
    if old_id == new_id:
        raise CircularSupersessionError(f"ADR {old_id} cannot supersede itself.")

    temp_map = dict(existing_map)
    temp_map[old_id] = new_id

    for start in temp_map:
        curr = start
        visited: list[str] = []
        while curr in temp_map:
            if curr in visited:
                idx = visited.index(curr)
                cycle_nodes = visited[idx:] + [curr]
                cycle_str = " -> ".join(cycle_nodes)
                raise CircularSupersessionError(f"Circular ADR supersession detected: {cycle_str}")
            visited.append(curr)
            curr = temp_map[curr]


def update_registry_supersession(
    registry_file: Path,
    old_id: str,
    new_id: str,
    new_title: str = "",
    new_date: str | None = None,
) -> None:
    """Updates REGISTRY.md table rows for old and new ADRs."""
    if not registry_file.exists():
        return

    content = registry_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated_lines: list[str] = []
    old_updated = False
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
                new_status = f"Superseded (by {new_id})"
                updated_lines.append(f"| {row_id} | {row_title} | {new_status} | {row_date} |")
                old_updated = True
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


def find_tasks_citing_adr(backlog_dir: Path, adr_id: str) -> list[str]:
    """Finds all active tasks in refined/ or proposed/ citing the specified ADR."""
    citing: list[str] = []
    canon_adr = normalize_adr_id(adr_id)
    if not backlog_dir.exists():
        return citing

    for folder_name in ["refined", "proposed"]:
        folder = backlog_dir / folder_name
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            if p.name.startswith("."):
                continue
            try:
                content = p.read_text(encoding="utf-8")
                meta, body = extract_frontmatter(content)
                raw_adrs = meta.get("governing_adrs") or []
                if "governing_adr" in meta:
                    raw_adrs = [meta["governing_adr"]] + (raw_adrs if isinstance(raw_adrs, list) else [])

                adrs_list = [normalize_adr_id(str(a)) for a in raw_adrs] if isinstance(raw_adrs, list) else [normalize_adr_id(str(raw_adrs))]
                matched = canon_adr in adrs_list

                if not matched:
                    pattern = rf"\b{re.escape(canon_adr)}\b"
                    if re.search(pattern, content, re.IGNORECASE):
                        matched = True

                if matched:
                    tid = str(meta.get("id", p.stem.split("-")[0]))
                    if not tid.upper().startswith("TASK-"):
                        m_num = re.search(r"\d+", tid)
                        cid = f"TASK-{int(m_num.group(0)):04d}" if m_num else tid.upper()
                    else:
                        cid = tid.upper()
                    if cid not in citing:
                        citing.append(cid)
            except OSError:
                continue

    return sorted(citing)


def supersede_adr(
    old_target: str | Path,
    new_target: str | Path,
    docs_dir: Path,
) -> SupersedeResult:
    """Executes atomic ADR supersession updating files, frontmatters, and REGISTRY.md."""
    if (docs_dir / "project" / "adrs").exists():
        adrs_dir = docs_dir / "project" / "adrs"
        backlog_dir = docs_dir / "project" / "backlog"
    elif (docs_dir / "adrs").exists():
        adrs_dir = docs_dir / "adrs"
        backlog_dir = docs_dir / "backlog"
    else:
        adrs_dir = docs_dir
        backlog_dir = docs_dir.parent / "backlog"

    old_file = find_adr_file(adrs_dir, old_target)
    new_file = find_adr_file(adrs_dir, new_target)

    old_meta, old_body, old_title, old_id = parse_adr_info(old_file)
    new_meta, new_body, new_title, new_id = parse_adr_info(new_file)

    existing_map = discover_superseded_adrs(adrs_dir)
    detect_supersession_cycles(existing_map, (old_id, new_id))

    # 1. Update old ADR
    old_meta["status"] = "Superseded"
    old_meta["superseded_by"] = new_id
    if "## Status" in old_body:
        old_body = re.sub(r"## Status\s*\n[^\n]+", f"## Status\nSuperseded (by {new_id})", old_body)
    write_adr_frontmatter(old_file, old_meta, old_body)

    # 2. Update new ADR
    new_meta["status"] = "Accepted"
    new_meta["supersedes"] = old_id
    if "## Status" in new_body:
        new_body = re.sub(r"## Status\s*\n[^\n]+", "## Status\nAccepted", new_body)

    # Move new ADR to accepted/ if it was in proposed/ or elsewhere
    accepted_dir = adrs_dir / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    if new_file.parent.resolve() != accepted_dir.resolve():
        target_path = accepted_dir / new_file.name
        new_file.rename(target_path)
        new_file = target_path

    write_adr_frontmatter(new_file, new_meta, new_body)

    # 3. Update REGISTRY.md
    registry_file = adrs_dir / "REGISTRY.md"
    update_registry_supersession(registry_file, old_id, new_id, new_title)

    # 4. Find active tasks citing superseded ADR
    citing_tasks = find_tasks_citing_adr(backlog_dir, old_id)
    warnings = [
        f"Task {tid} cites superseded {old_id}; requires architectural re-refinement"
        for tid in citing_tasks
    ]

    return SupersedeResult(
        old_id=old_id,
        new_id=new_id,
        old_file=old_file,
        new_file=new_file,
        warnings=warnings,
    )
