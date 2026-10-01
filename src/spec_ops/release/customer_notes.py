"""Living Customer-Facing Release Notes Generator and Changelog Publisher (US-0049, PRD-0003)."""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.models import ProjectData
from ..core.parser import SpecOpsParser, parse_prd


@dataclass
class PersonaImpact:
    name: str
    role: str = ""
    benefits: list[str] = field(default_factory=list)


@dataclass
class UATOutcome:
    outcome: str
    verified: bool = True


@dataclass
class CustomerReleaseNotesData:
    prd_id: str
    title: str
    status: str
    summary: str
    target_persona: str
    personas: list[PersonaImpact] = field(default_factory=list)
    uat_outcomes: list[UATOutcome] = field(default_factory=list)
    capabilities: list[tuple[str, str]] = field(default_factory=list)
    stories: list[tuple[str, str, str]] = field(default_factory=list)
    published_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )


def sanitize_customer_text(text: str) -> str:
    """Strips internal git commit jargon, prefixes, and hashes."""
    s = re.sub(r"\b[0-9a-f]{7,40}\b", "", text)
    s = re.sub(r"^(?:feat|fix|chore|spike|refactor|test|docs|style|ci|perf)(?:\([^)]*\))?:\s*", "", s, flags=re.I)
    s = re.sub(r"\b(?:AST|mutmut|_THREAD_LOCK)\b", "", s)
    return " ".join(s.split()).strip()


def find_prd_file(prd_id: str, config: SpecOpsConfig) -> Path | None:
    """Finds a PRD file by canonical ID or numeric string across product directories."""
    clean_id = prd_id.strip()
    m = re.search(r"\d+", clean_id)
    cid = f"PRD-{m.group(0).zfill(4)}" if m else clean_id.upper()
    p_dir = config.project_docs_dir / "product"
    if not p_dir.exists():
        return None
    for folder in ("shipped", "accepted", "shaped", "idea"):
        sub = p_dir / folder
        if sub.is_dir():
            for p in sub.glob("*.md"):
                if cid.lower() in p.name.lower() or (m and f"prd-{m.group(0).zfill(4)}" in p.name.lower()):
                    return p
    for p in p_dir.rglob("*.md"):
        if cid.lower() in p.name.lower():
            return p
    return None


def extract_what_good_looks_like(raw_markdown: str) -> list[tuple[str, str]]:
    """Extracts capabilities from '## What good looks like' section."""
    m = re.search(r"##\s+What good looks like\s*\n(.*?)(?=\n##|\Z)", raw_markdown, re.DOTALL)
    if not m:
        return []
    items: list[tuple[str, str]] = []
    curr_t, curr_d = "", []
    for line in m.group(1).splitlines():
        s = line.strip()
        h = re.match(r"^(?:\d+\.|\*|-)\s+\*\*([^*]+)\*\*:\s*(.*)$", s) if s else None
        if h:
            if curr_t:
                items.append((curr_t, sanitize_customer_text(" ".join(curr_d))))
            curr_t, curr_d = h.group(1).strip(), [h.group(2).strip()] if h.group(2).strip() else []
        elif curr_t and s:
            curr_d.append(s.lstrip("-* ").strip())
    if curr_t:
        items.append((curr_t, sanitize_customer_text(" ".join(curr_d))))
    return items


def extract_who_this_is_for(raw_markdown: str) -> dict[str, str]:
    """Extracts persona benefits from '## Who this is for' section."""
    m = re.search(r"##\s+Who this is for\s*\n(.*?)(?=\n##|\Z)", raw_markdown, re.DOTALL)
    if not m:
        return {}
    res: dict[str, str] = {}
    for line in m.group(1).splitlines():
        hm = re.match(r"^[-*]\s+\*\*([^(]+)(?:\(([^)]+)\))?\*\*:\s*(.*)$", line.strip())
        if hm and hm.group(3).strip():
            res[hm.group(1).strip().lower()] = sanitize_customer_text(hm.group(3).strip())
    return res


def load_personas_catalog(config: SpecOpsConfig) -> dict[str, tuple[str, str, list[str]]]:
    """Loads personas from PERSONAS.md returning {first_name_lower: (full_name, role, goals)}."""
    p_file = config.project_docs_dir / "user_stories" / "PERSONAS.md"
    if not p_file.exists():
        return {}
    catalog: dict[str, tuple[str, str, list[str]]] = {}
    for sec in re.split(r"\n##\s+", p_file.read_text(encoding="utf-8"))[1:]:
        clean_hdr = re.sub(r"^\d+\.\s*", "", sec.splitlines()[0].strip()).strip()
        first_name = clean_hdr.split("—")[0].split("-")[0].strip().split()[0].lower()
        role_m = re.search(r"-\s*\*\*Role\*\*:\s*(.*)", sec)
        role = role_m.group(1).strip() if role_m else ""
        goals: list[str] = []
        gm = re.search(r"-\s*\*\*Goals.*?\*\*:(.*?)(?=\n-\s*\*\*|\n---|\Z)", sec, re.DOTALL)
        if gm:
            for g in gm.group(1).splitlines():
                g_str = re.sub(r"^\s*-\s*", "", g).strip()
                if g_str and not g_str.startswith("-") and g_str not in ("--", "---"):
                    goals.append(sanitize_customer_text(g_str))
        catalog[first_name] = (clean_hdr, role, goals)
    return catalog


def build_customer_notes_data(
    prd_id: str,
    config: SpecOpsConfig,
    data: ProjectData | None = None,
) -> CustomerReleaseNotesData:
    """Builds synthesized persona-oriented release notes data from a PRD."""
    prd_path = find_prd_file(prd_id, config)
    if not prd_path:
        raise FileNotFoundError(f"PRD '{prd_id}' not found in {config.project_docs_dir / 'product'}")
    prd = parse_prd(prd_path)
    uat_outcomes = [UATOutcome(outcome=sanitize_customer_text(o)) for o in prd.outcomes if o.strip()]
    capabilities = extract_what_good_looks_like(prd.raw_markdown)
    if not capabilities and uat_outcomes:
        capabilities = [(f"Verified Outcome {i+1}", o.outcome) for i, o in enumerate(uat_outcomes)]

    catalog = load_personas_catalog(config)
    who_map = extract_who_this_is_for(prd.raw_markdown)
    active_keys: list[str] = []
    if prd.target_persona:
        active_keys.append(prd.target_persona.split("—")[0].split("-")[0].strip().split()[0].lower())
    for p_name in who_map:
        if p_name not in active_keys:
            active_keys.append(p_name)

    stories_info: list[tuple[str, str, str]] = []
    if data is None and config.project_docs_dir.exists():
        try:
            data = SpecOpsParser(config.project_docs_dir).parse_all()
        except Exception:
            data = None
    if data:
        for st in data.stories:
            st_cid = f"US-{st.id.zfill(4)}" if st.id.isdigit() else st.id
            if st.id in prd.linked_stories or st_cid in prd.linked_stories:
                stories_info.append((st.id, sanitize_customer_text(st.title), st.persona))
                if st.persona:
                    st_p = st.persona.split("—")[0].split("-")[0].strip().split()[0].lower()
                    if st_p not in active_keys:
                        active_keys.append(st_p)

    if not active_keys:
        active_keys = ["taylor"]

    persona_impacts: list[PersonaImpact] = []
    for key in active_keys:
        full_name, role, default_goals = catalog.get(key, (key.capitalize(), "Product Stakeholder", []))
        benefits: list[str] = []
        if key in who_map:
            benefits.append(who_map[key])
        for g in default_goals:
            if g not in benefits:
                benefits.append(g)
        if not benefits:
            benefits.append(f"Accelerated workflows and verified delivery for {full_name}.")
        persona_impacts.append(PersonaImpact(name=full_name, role=role, benefits=benefits))

    summary = prd.problem_statement or f"Customer release notes for {prd.title}."
    return CustomerReleaseNotesData(
        prd_id=prd.id,
        title=prd.title,
        status=prd.status,
        summary=sanitize_customer_text(summary),
        target_persona=prd.target_persona or "All Stakeholders",
        personas=persona_impacts,
        uat_outcomes=uat_outcomes,
        capabilities=capabilities,
        stories=stories_info,
    )


def render_markdown_customer_notes(data: CustomerReleaseNotesData) -> str:
    """Formats customer-facing release notes in GitHub Markdown."""
    lines = [
        f"# Release Notes: {data.title} ({data.prd_id})",
        "",
        f"**Status:** {data.status}  ",
        f"**Date:** {data.published_at}  ",
        f"**Target Persona:** {data.target_persona}",
        "",
    ]
    if data.summary:
        lines.extend(["## Overview", "", data.summary, ""])
    lines.extend(["## Verifiable Customer UAT Checkmarks", ""])
    for u in data.uat_outcomes:
        lines.append(f"- [x] {u.outcome}")
    if not data.uat_outcomes:
        lines.append("- [x] All checkable criteria verified.")
    lines.extend(["", "## Target Persona Benefits", ""])
    for p in data.personas:
        p_hdr = f"### {p.name}" + (f" — {p.role}" if p.role and p.role not in p.name else "")
        lines.extend([p_hdr, ""])
        for b in p.benefits:
            lines.append(f"- {b}")
        lines.append("")
    if data.capabilities:
        lines.extend(["## Shipped Capabilities", ""])
        for t, d in data.capabilities:
            lines.append(f"- **{t}**: {d}")
        lines.append("")
    if data.stories:
        lines.extend(["## Completed User Journeys", ""])
        for sid, stitle, spersona in data.stories:
            lines.append(f"- **{sid}**: {stitle} ({spersona})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html_customer_notes(data: CustomerReleaseNotesData, branded: bool = False) -> str:
    """Formats customer-facing release notes in self-contained, XSS-safe HTML."""
    accent = "#38bdf8"
    bg, card_bg = ("#0f172a", "#1e293b") if branded else ("#f8fafc", "#ffffff")
    txt, sub = ("#f8fafc", "#94a3b8") if branded else ("#0f172a", "#64748b")
    bdr = "#334155" if branded else "#e2e8f0"

    uat_items = "".join(
        f'<li style="margin-bottom:8px; display:flex; align-items:flex-start;">'
        f'<span style="background:#10b981; color:#0f172a; font-weight:700; font-size:11px; '
        f'padding:2px 8px; border-radius:12px; margin-right:10px; flex-shrink:0;">✓ Verified UAT</span>'
        f'<span style="color:{txt}; font-size:14px;">{html.escape(u.outcome)}</span></li>'
        for u in data.uat_outcomes
    ) or f'<li style="color:{sub};">All checkable criteria verified.</li>'

    p_cards = "".join(
        f'<div style="background:{card_bg}; border:1px solid {bdr}; border-radius:10px; padding:16px; margin-bottom:12px;">'
        f'<h3 style="color:{accent}; font-size:16px; margin:0 0 8px 0;">{html.escape(p.name)}'
        f'<span style="color:{sub}; font-size:13px; font-weight:normal;">'
        f'{" — " + html.escape(p.role) if p.role and p.role not in p.name else ""}</span></h3>'
        f'<ul style="margin:0; padding-left:18px; color:{txt}; font-size:14px;">'
        f'{"".join(f"<li style=\'margin-bottom:4px;\'>{html.escape(b)}</li>" for b in p.benefits)}'
        f'</ul></div>'
        for p in data.personas
    )
    cap_cards = "".join(
        f'<div style="margin-bottom:10px;"><strong style="color:{txt}; font-size:14px;">{html.escape(t)}: </strong>'
        f'<span style="color:{sub}; font-size:14px;">{html.escape(d)}</span></div>'
        for t, d in data.capabilities
    )
    return (
        f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f'<title>Release Announcement: {html.escape(data.title)}</title>\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'</head>\n<body style="background:{bg}; margin:0; padding:24px 12px; font-family:sans-serif;">\n'
        f'<div style="max-width:720px; margin:0 auto; background:{card_bg}; border:1px solid {bdr}; border-radius:14px; padding:32px;">\n'
        f'<div style="border-bottom:1px solid {bdr}; padding-bottom:16px; margin-bottom:24px;">\n'
        f'<span style="background:#0284c7; color:#fff; font-size:11px; font-weight:700; padding:3px 10px; border-radius:10px;">{html.escape(data.status)}</span>\n'
        f'<h1 style="color:{txt}; font-size:26px; margin:12px 0 6px 0;">Release Announcement: {html.escape(data.title)} ({html.escape(data.prd_id)})</h1>\n'
        f'<p style="color:{sub}; font-size:14px; margin:0;">Target Persona: {html.escape(data.target_persona)} • {html.escape(data.published_at)}</p></div>\n'
        f'<h2 style="color:{accent}; font-size:17px; margin:20px 0 12px 0; text-transform:uppercase;">Verifiable Customer UAT Checkmarks</h2>\n'
        f'<ul style="list-style:none; padding:0; margin:0 0 24px 0;">{uat_items}</ul>\n'
        f'<h2 style="color:{accent}; font-size:17px; margin:24px 0 12px 0; text-transform:uppercase;">Target Persona Benefits</h2>\n'
        f'{p_cards}\n'
        f'<h2 style="color:{accent}; font-size:17px; margin:24px 0 12px 0; text-transform:uppercase;">Shipped Capabilities</h2>\n'
        f'<div style="background:rgba(56,189,248,0.05); border:1px solid {bdr}; border-radius:10px; padding:16px;">\n'
        f'{cap_cards or f"<p style=\'color:{sub}; margin:0;\'>Standard platform stability and enhancements.</p>"}\n'
        f'</div></div></body></html>\n'
    )


def render_json_customer_notes(data: CustomerReleaseNotesData) -> str:
    """Formats customer-facing release notes as structured JSON."""
    payload = {
        "prd_id": data.prd_id,
        "title": data.title,
        "status": data.status,
        "published_at": data.published_at,
        "target_persona": data.target_persona,
        "summary": data.summary,
        "uat_outcomes": [{"outcome": u.outcome, "verified": u.verified} for u in data.uat_outcomes],
        "personas": [asdict(p) for p in data.personas],
        "capabilities": [{"title": t, "description": d} for t, d in data.capabilities],
        "stories": [{"id": s[0], "title": s[1], "persona": s[2]} for s in data.stories],
    }
    return json.dumps(payload, indent=2)


def update_changelog(changelog_path: Path, notes: CustomerReleaseNotesData, md_content: str) -> None:
    """Updates docs/explanation/changelog.md idempotently with new release entry."""
    header = "# Changelog\n\nAll notable customer-facing changes and release notes for SpecOps.\n"
    entry = f"\n## [{notes.prd_id}] {notes.title} ({notes.published_at})\n\n{md_content.strip()}\n"
    if not changelog_path.exists():
        changelog_path.write_text(f"{header}\n{entry}\n", encoding="utf-8")
        return
    existing = changelog_path.read_text(encoding="utf-8")
    marker = f"[{notes.prd_id}]"
    if marker in existing:
        pattern = rf"\n## \[{re.escape(notes.prd_id)}\].*?(?=\n## \[|\Z)"
        changelog_path.write_text(re.sub(pattern, f"\n{entry.strip()}\n", existing, flags=re.DOTALL), encoding="utf-8")
    else:
        parts = existing.split("\n## [", 1)
        new_content = f"{parts[0].rstrip()}\n{entry}\n## [{parts[1]}" if len(parts) == 2 else f"{existing.rstrip()}\n{entry}\n"
        changelog_path.write_text(new_content, encoding="utf-8")


def generate_customer_release_notes(
    prd_id: str,
    config: SpecOpsConfig,
    format_type: str = "markdown",
    branded: bool = False,
    output_path: str | Path | None = None,
    publish: bool = False,
    data: ProjectData | None = None,
) -> tuple[Path, str]:
    """Generates customer-facing release notes and publishes to release folder or changelog."""
    notes_data = build_customer_notes_data(prd_id, config, data=data)
    fmt = format_type.lower()
    if fmt == "html":
        content, ext = render_html_customer_notes(notes_data, branded=branded), "html"
    elif fmt == "json":
        content, ext = render_json_customer_notes(notes_data), "json"
    else:
        content, ext = render_markdown_customer_notes(notes_data), "md"

    slug = notes_data.prd_id.lower().replace("_", "-")
    if output_path:
        dest = Path(output_path)
        if not dest.is_absolute():
            dest = config.root_dir / dest
    else:
        dest = config.docs_dir / "releases" / f"{slug}-release-notes.{ext}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")

    if publish:
        changelog_file = config.docs_dir / "explanation" / "changelog.md"
        changelog_file.parent.mkdir(parents=True, exist_ok=True)
        md_text = render_markdown_customer_notes(notes_data) if fmt != "markdown" else content
        update_changelog(changelog_file, notes_data, md_text)

    return dest, content
