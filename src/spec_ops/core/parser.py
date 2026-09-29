"""Universal parser for SpecOps documentation entities."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import ADR, PRD, Persona, ProjectData, Task, UserStory

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extracts YAML frontmatter and returns (metadata_dict, body_markdown)."""
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, content
    try:
        data = yaml.safe_load(match.group(1)) or {}
        body = content[match.end():]
        return data, body
    except yaml.YAMLError:
        return {}, content


def parse_priority_ranks(backlog_dir: Path) -> dict[str, int]:
    """Parses PRIORITY.md to establish task ordering ranks."""
    priority_file = backlog_dir / "PRIORITY.md"
    if not priority_file.exists():
        return {}
    ranks: dict[str, int] = {}
    rank = 1
    for line in priority_file.read_text(encoding="utf-8").splitlines():
        match = re.search(r"TASK-0*(\d+)", line, re.IGNORECASE)
        if match:
            cid = f"TASK-{match.group(1).zfill(4)}"
            if cid not in ranks:
                ranks[cid] = rank
                rank += 1
    return ranks


def parse_personas(persona_file: Path) -> list[Persona]:
    """Parses PERSONAS.md into Persona domain objects."""
    if not persona_file.exists():
        return []
    content = persona_file.read_text(encoding="utf-8")
    personas: list[Persona] = []
    sections = re.split(r"\n##\s+", content)
    for sec in sections[1:]:
        lines = sec.strip().splitlines()
        header = lines[0].strip()
        name_match = re.search(r"\d+\.\s*([^—–-]+)", header)
        name = name_match.group(1).strip() if name_match else header
        role_match = re.search(r"[—–-]\s*(.+)$", header)
        role = role_match.group(1).strip() if role_match else ""
        pid = name.lower().split()[0]
        personas.append(Persona(id=pid, name=name, role=role))
    return personas


def parse_task(file_path: Path, priority_rank: int = 999999) -> Task:
    """Parses a markdown task file with YAML frontmatter."""
    content = file_path.read_text(encoding="utf-8")
    meta, body = extract_frontmatter(content)
    raw_id = str(meta.get("id", file_path.stem.split("-")[0]))
    status = meta.get("status", "Proposed")
    if file_path.parent.name == "complete":
        status = "Complete"
    elif file_path.parent.name == "refined":
        status = "Refined"
    elif file_path.parent.name == "proposed":
        status = "Proposed"

    return Task(
        id=raw_id,
        title=str(meta.get("title", file_path.stem)),
        status=status,
        dependencies=[str(d) for d in meta.get("dependencies", [])],
        governing_adrs=[str(a) for a in meta.get("governing_adrs", [])],
        governing_prds=[str(p) for p in meta.get("governing_prds", [])],
        governing_stories=[str(s) for s in meta.get("governing_stories", [])],
        target_bc=str(meta.get("target_bc", "")),
        target_release=str(meta.get("target_release", "")),
        prs=[str(p) for p in meta.get("prs", [])],
        pr_url=str(meta.get("pr_url", "")),
        claimed_by=str(meta.get("claimed_by", "")),
        branch=str(meta.get("branch", "")),
        priority_rank=priority_rank,
        body=body,
        raw_markdown=content,
        file_path=file_path,
    )


def parse_user_story(file_path: Path) -> UserStory:
    """Parses a user story markdown file with YAML frontmatter."""
    content = file_path.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)
    raw_id = str(meta.get("id", file_path.stem.split("-")[0]))
    cid = f"US-{raw_id.zfill(4)}" if raw_id.isdigit() else raw_id
    scenarios = re.findall(r"Scenario:\s*(.+)", content)
    return UserStory(
        id=cid,
        title=str(meta.get("title", file_path.stem)),
        status=str(meta.get("status", "Accepted")),
        persona=str(meta.get("persona", "")),
        feature=str(meta.get("feature", "")),
        governing_prd=str(meta.get("governing_prd", "")),
        scenarios=scenarios,
        raw_markdown=content,
        file_path=file_path,
    )


def parse_prd(file_path: Path) -> PRD:
    """Parses a PRD markdown file with YAML frontmatter."""
    content = file_path.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)
    raw_id = str(meta.get("id", file_path.stem.split("-")[0]))
    cid = f"PRD-{raw_id.zfill(4)}" if raw_id.isdigit() else raw_id
    linked_stories = [
        f"US-{m.zfill(4)}" for m in re.findall(r"US-(\d+)", content, re.IGNORECASE)
    ]
    implementing_tasks = [
        f"TASK-{m.zfill(4)}" for m in re.findall(r"TASK-(\d+)", content, re.IGNORECASE)
    ]
    return PRD(
        id=cid,
        title=str(meta.get("title", file_path.stem)),
        status=str(meta.get("status", "Accepted")),
        linked_stories=list(dict.fromkeys(linked_stories)),
        implementing_tasks=list(dict.fromkeys(implementing_tasks)),
        raw_markdown=content,
        file_path=file_path,
    )


def parse_adr(file_path: Path) -> ADR:
    """Parses an ADR markdown file."""
    content = file_path.read_text(encoding="utf-8")
    num_match = re.search(r"adr-(\d+)", file_path.stem, re.IGNORECASE)
    raw_id = f"ADR-{num_match.group(1).zfill(4)}" if num_match else file_path.stem.upper()
    title_line = content.splitlines()[0] if content else file_path.stem
    clean_title = re.sub(r"^#\s*(ADR-\d+:\s*)?", "", title_line).strip()
    return ADR(
        id=raw_id,
        title=clean_title,
        status="Accepted",
        raw_markdown=content,
        file_path=file_path,
    )


class SpecOpsParser:
    """Orchestrates parsing of all entities in a project docs directory."""

    def __init__(self, docs_dir: Path):
        self.docs_dir = docs_dir.resolve()

    def parse_all(self) -> ProjectData:
        data = ProjectData()

        # 1. Personas
        persona_file = self.docs_dir / "user_stories" / "PERSONAS.md"
        data.personas = parse_personas(persona_file)

        # 2. User Stories
        us_dir = self.docs_dir / "user_stories"
        if us_dir.exists():
            for p in sorted(us_dir.rglob("*.md")):
                if p.is_file() and p.name != "PERSONAS.md" and p.name != "REGISTRY.md" and p.name != "PRIORITY.md":
                    data.stories.append(parse_user_story(p))

        # 3. PRDs
        prd_dir = self.docs_dir / "product"
        if prd_dir.exists():
            for p in sorted(prd_dir.rglob("*.md")):
                if p.is_file() and p.name != "REGISTRY.md" and p.name != "FEATURE_INVENTORY.md" and p.name != "README.md":
                    data.prds.append(parse_prd(p))

        # 4. ADRs
        adr_dir = self.docs_dir / "adrs"
        if adr_dir.exists():
            for p in sorted(adr_dir.rglob("*.md")):
                if p.is_file() and p.name != "REGISTRY.md" and p.name != "PRIORITY.md":
                    data.adrs.append(parse_adr(p))

        # 5. Backlog Tasks
        backlog_dir = self.docs_dir / "backlog"
        if backlog_dir.exists():
            ranks = parse_priority_ranks(backlog_dir)
            for folder in ["complete", "refined", "proposed"]:
                fpath = backlog_dir / folder
                if fpath.exists():
                    for p in sorted(fpath.glob("*.md")):
                        if p.is_file() and not p.name.startswith("."):
                            m = re.match(r"^(\d+)", p.stem)
                            cid = f"TASK-{m.group(1).zfill(4)}" if m else p.stem
                            task = parse_task(p, priority_rank=ranks.get(cid, 999999))
                            data.tasks.append(task)

        return data
