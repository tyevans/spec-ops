"""Universal parser for SpecOps documentation entities."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import ADR, PRD, BlockerInfo, Persona, ProjectData, Task, UserStory

FRONTMATTER_PATTERN = re.compile(r"^---\s*(?:\r?\n)(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.DOTALL)


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


def serialize_frontmatter(metadata: dict[str, Any], body: str = "") -> str:
    """Serializes frontmatter dictionary and markdown body into canonical markdown."""
    yaml_str = yaml.dump(
        metadata,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{yaml_str}---\n{body}"


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

        pain_points = []
        pain_match = re.search(r"- \*\*Pain Points\*\*:(.*?)(?=- \*\*|\Z)", sec, re.DOTALL)
        if pain_match:
            pain_points = [
                re.sub(r"^\s*-\s*", "", l).strip()
                for l in pain_match.group(1).splitlines()
                if l.strip().startswith("-")
            ]

        goals = []
        goal_match = re.search(r"- \*\*Goals.*?\*\*:(.*?)(?=- \*\*|\Z)", sec, re.DOTALL)
        if goal_match:
            goals = [
                re.sub(r"^\s*-\s*", "", l).strip()
                for l in goal_match.group(1).splitlines()
                if l.strip().startswith("-")
            ]

        personas.append(
            Persona(
                id=pid,
                name=name,
                role=role,
                pain_points=pain_points,
                goals=goals,
                raw_markdown=f"## {sec}",
                file_path=persona_file,
            )
        )
    return personas


def parse_task(file_path: Path, priority_rank: int = 999999) -> Task:
    """Parses a markdown task file with YAML frontmatter."""
    content = file_path.read_text(encoding="utf-8")
    meta, body = extract_frontmatter(content)
    raw_id = str(meta.get("id", file_path.stem.split("-")[0]))
    raw_status = meta.get("status")
    if file_path.parent.name == "complete":
        status = "Graduated" if raw_status == "Graduated" else "Complete"
    elif file_path.parent.name == "refined":
        status = str(raw_status) if raw_status in ("In-Progress", "Review", "Ready") else "Refined"
    elif file_path.parent.name == "proposed":
        status = str(raw_status) if raw_status and str(raw_status).startswith("Blocked") else "Proposed"
    else:
        status = str(raw_status or "Proposed")

    blocker_raw = meta.get("blocker")
    blocker_info = None
    if isinstance(blocker_raw, dict):
        blocker_info = BlockerInfo(
            type=str(blocker_raw.get("type", "unknown")),
            question=str(blocker_raw.get("question", "")),
            raised_by=str(blocker_raw.get("raised_by", "")),
            raised_at=str(blocker_raw.get("raised_at", "")),
            spike_id=str(blocker_raw.get("spike_id", "")),
            resolution=str(blocker_raw.get("resolution", "")),
            resolved_at=str(blocker_raw.get("resolved_at", "")),
            adr_id=str(blocker_raw.get("adr_id", "")),
        )

    return Task(
        id=raw_id,
        title=str(meta.get("title", file_path.stem)),
        status=status,
        dependencies=[str(d) for d in meta.get("dependencies", [])],
        governing_adrs=(
            [str(a) for a in meta.get("governing_adrs", [])]
            if "governing_adrs" in meta
            else ([str(meta["governing_adr"])] if "governing_adr" in meta else [])
        ),
        governing_prds=[str(p) for p in meta.get("governing_prds", [])],
        governing_stories=[str(s) for s in (meta.get("governing_stories") or meta.get("stories") or ([meta["story"]] if "story" in meta else []))],
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
        allows_dependencies=bool(meta.get("allows_dependencies", False)),
        hypothesis=str(meta.get("hypothesis", "")),
        timebox=str(meta.get("timebox", "")),
        signed_off_by=str(meta.get("signed_off_by", "")),
        signed_off_at=str(meta.get("signed_off_at", "")),
        has_signed_commits=meta.get("has_signed_commits"),
        commit_signature_status=str(meta.get("commit_signature_status", "")),
        blocker=blocker_info,
        slice_type=str(meta.get("slice_type") or meta.get("slice") or meta.get("type") or "feat").lower(),
        unblocked=bool(meta.get("unblocked", False)),
        failure_history=list(meta.get("failure_history", []) or []),
        completed_at=str(meta.get("completed_at", "")),
        claimed_at=str(meta.get("claimed_at", "")),
        timestamp=str(meta.get("timestamp", "")),
        pinned=bool(meta.get("pinned", False) or meta.get("priority_pin") is not None),
        priority_pin=(
            int(meta["priority_pin"])
            if meta.get("priority_pin") is not None and str(meta["priority_pin"]).isdigit()
            else (
                meta["pinned"]
                if isinstance(meta.get("pinned"), int) and not isinstance(meta.get("pinned"), bool)
                else None
            )
        ),
        persona=str(meta.get("persona") or meta.get("target_persona") or ""),
        mutation_scope=str(meta.get("mutation_scope", "")),
        expected_lines=int(meta.get("expected_lines", 0) or 0),
    )



def parse_user_story(file_path: Path) -> UserStory:
    """Parses a user story markdown file with YAML frontmatter."""
    content = file_path.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)
    raw_id = str(meta.get("id", file_path.stem.split("-")[0]))
    cid = f"US-{raw_id.zfill(4)}" if raw_id.isdigit() else raw_id
    scenarios = re.findall(r"Scenario:\s*(.+)", content)

    as_a_m = re.search(r"\*\*As an?\*\*\s*([^\n,]+)", content, re.IGNORECASE)
    i_want_m = re.search(r"\*\*I want\*\*\s*([^\n,]+)", content, re.IGNORECASE)
    so_that_m = re.search(r"\*\*So that\*\*\s*([^\n.]+)", content, re.IGNORECASE)

    return UserStory(
        id=cid,
        title=str(meta.get("title", file_path.stem)),
        status=str(meta.get("status", "Accepted")),
        persona=str(meta.get("persona", "")),
        feature=str(meta.get("feature", "")),
        governing_prd=str(meta.get("governing_prd", "")),
        as_a=as_a_m.group(1).strip() if as_a_m else "",
        i_want=i_want_m.group(1).strip() if i_want_m else "",
        so_that=so_that_m.group(1).strip() if so_that_m else "",
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

    prob_m = re.search(r"## What the person cannot do today\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    problem_statement = prob_m.group(1).strip() if prob_m else ""

    outcomes = []
    outcomes_m = re.search(r"## Checkable Outcomes\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if outcomes_m:
        outcomes = [
            re.sub(r"^\s*(?:\d+\.|\*|-)\s*", "", l).strip()
            for l in outcomes_m.group(1).splitlines()
            if l.strip() and (l.strip()[0].isdigit() or l.strip().startswith(("-", "*")))
        ]

    return PRD(
        id=cid,
        title=str(meta.get("title", file_path.stem)),
        status=str(meta.get("status", "Accepted")),
        target_persona=str(meta.get("target_persona", "")),
        problem_statement=problem_statement,
        outcomes=outcomes,
        linked_stories=list(dict.fromkeys(linked_stories)),
        implementing_tasks=list(dict.fromkeys(implementing_tasks)),
        raw_markdown=content,
        file_path=file_path,
    )


def parse_adr(file_path: Path) -> ADR:
    """Parses an ADR markdown file."""
    content = file_path.read_text(encoding="utf-8")
    meta, body = extract_frontmatter(content)
    num_match = re.search(r"adr-(\d+)", file_path.stem, re.IGNORECASE)
    raw_id = f"ADR-{num_match.group(1).zfill(4)}" if num_match else str(meta.get("id", file_path.stem.upper()))
    clean_title = str(meta.get("title", ""))
    if not clean_title:
        title_line = body.strip().splitlines()[0] if body.strip() else (content.splitlines()[0] if content else file_path.stem)
        clean_title = re.sub(r"^#\s*(ADR-\d+:\s*)?", "", title_line).strip()

    status = str(meta.get("status", "Accepted"))
    domain = str(meta.get("domain", "Architecture"))

    ctx_m = re.search(r"## Context\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    dec_m = re.search(r"## Decision\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    con_m = re.search(r"## Consequences\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)

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
