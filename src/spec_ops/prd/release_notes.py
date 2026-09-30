"""Automated customer-facing release notes and business value changelog generator (US-0049, PRD-0003)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester
from ..core.models import Persona, ProjectData, Task, UserStory
from ..core.parser import SpecOpsParser


@dataclass
class CapabilityItem:
    prd_id: str
    prd_title: str
    title: str
    description: str = ""
    doc_url: str = ""
    visualizer_permalink: str = ""


@dataclass
class StorySummary:
    id: str
    title: str
    persona: str = ""
    scenarios: list[str] = field(default_factory=list)


@dataclass
class PersonaBenefit:
    name: str
    role: str
    benefits: list[str] = field(default_factory=list)


@dataclass
class ReleaseNotesData:
    milestone_id: str
    milestone_title: str
    capabilities: list[CapabilityItem] = field(default_factory=list)
    stories: list[StorySummary] = field(default_factory=list)
    personas: list[PersonaBenefit] = field(default_factory=list)
    excluded_tasks: list[str] = field(default_factory=list)
    excluded_commits: list[str] = field(default_factory=list)


def milestone_slug(milestone_id: str) -> str:
    m = re.search(r"\d+", milestone_id)
    if m:
        return f"m{m.group(0)}"
    return re.sub(r"[^a-zA-Z0-9]+", "-", milestone_id.strip()).strip("-").lower() or "m1"


def is_chore_or_spike_task(task: Any) -> bool:
    slice_type = str(getattr(task, "slice_type", "")).lower()
    if slice_type in ("chore", "spike", "refactor", "internal", "test"):
        return True
    cid = str(getattr(task, "canonical_id", getattr(task, "id", ""))).upper()
    if cid.startswith("SPIKE") or getattr(task, "hypothesis", ""):
        return True
    return bool(re.search(r"\b(chore|spike|refactor)\b", str(getattr(task, "title", "")).lower()))


def is_chore_or_spike_commit(commit: Any) -> bool:
    subj = str(getattr(commit, "subject", "")).lower()
    if re.search(r"^(chore|spike|refactor|test)(\(.*\))?:", subj) or re.search(r"\b(chore|spike|refactor)\b", subj):
        return True
    trailers = getattr(commit, "trailers", {}) or {}
    return str(trailers.get("SpecOps-Slice", "")).lower() in ("chore", "spike", "refactor", "test")


def extract_what_good_looks_like(raw_markdown: str) -> list[tuple[str, str]]:
    match = re.search(r"##\s+What good looks like\s*\n(.*?)(?=\n##|\Z)", raw_markdown, re.DOTALL)
    if not match:
        return []
    items: list[tuple[str, str]] = []
    curr_title, curr_desc = "", []
    for line in match.group(1).splitlines():
        s = line.strip()
        if not s:
            continue
        h = re.match(r"^(?:\d+\.|\*|-)\s+\*\*([^*]+)\*\*:\s*(.*)$", s)
        if h:
            if curr_title:
                items.append((curr_title, " ".join(curr_desc).strip()))
            curr_title, curr_desc = h.group(1).strip(), [h.group(2).strip()] if h.group(2).strip() else []
        elif curr_title:
            curr_desc.append(s.lstrip("-* ").strip())
    if curr_title:
        items.append((curr_title, " ".join(curr_desc).strip()))
    return items


def extract_persona_benefits(persona: Persona) -> list[str]:
    raw_benefits = persona.goals
    if not raw_benefits:
        m = re.search(r"- \*\*Goals.*?\*\*:(.*?)(?=- \*\*|\Z)", persona.raw_markdown, re.DOTALL)
        raw_benefits = [re.sub(r"^\s*-\s*", "", l).strip() for l in m.group(1).splitlines() if l.strip().startswith("-")] if m else []
    return [b.strip() for b in raw_benefits if b.strip() and not b.strip().startswith("-") and b.strip() not in ("--", "---")]


def extract_story_scenarios(story: UserStory) -> list[str]:
    scs = list(story.scenarios)
    if not scs and story.raw_markdown:
        for line in story.raw_markdown.splitlines():
            m = re.search(r"^(?:#+\s*)?Scenario(?:\s+\d+)?:?\s*(.+)$", line.strip(), re.IGNORECASE)
            if m:
                s_name = m.group(1).strip()
                if s_name and s_name not in scs:
                    scs.append(s_name)
    if not scs and story.i_want:
        scs.append(f"As a {story.as_a}, I want {story.i_want}".strip())
    return scs


def build_release_notes_data(milestone_id: str, config: SpecOpsConfig, data: ProjectData | None = None) -> ReleaseNotesData:
    if data is None:
        data = SpecOpsParser(config.project_docs_dir).parse_all()

    roadmap = config.backlog_dir / "ROADMAP.md"
    milestone_title, ms_task_ids, ms_prd_ids = f"Milestone {milestone_id}", [], []

    if roadmap.exists():
        q_num = re.search(r"\d+", milestone_id)
        clean_q = milestone_id.strip().lower().replace("milestone", "").replace("-", "").replace(" ", "")
        in_sec = False
        for line in roadmap.read_text(encoding="utf-8").splitlines():
            hm = re.match(r"^##\s+(?:Milestone\s+)?([A-Za-z0-9\-]+)(?::\s*([^(\n]+))?", line, re.IGNORECASE)
            if hm:
                mid, mtitle = hm.group(1).strip(), (hm.group(2) or hm.group(1)).strip()
                m_num = re.search(r"\d+", mid) or re.search(r"\d+", mtitle)
                num_match = bool(q_num and m_num and q_num.group(0) == m_num.group(0))
                key_match = clean_q in mid.lower().replace("-", "") or clean_q in mtitle.lower().replace("-", "")
                in_sec = num_match or key_match
                if in_sec:
                    milestone_title = f"{mid}: {mtitle}" if mid not in mtitle else mtitle
                continue
            if in_sec:
                ms_task_ids.extend(f"TASK-{t.split('-')[-1].zfill(4)}" for t in re.findall(r"`?(TASK-\d+)`?", line, re.I))
                ms_prd_ids.extend(f"PRD-{p.split('-')[-1].zfill(4)}" for p in re.findall(r"`?(PRD-\d+)`?", line, re.I))

    git_map = GitMetadataHarvester(config.root_dir).harvest()
    tasks = [t for t in data.tasks if t.canonical_id in ms_task_ids] or [t for t in data.tasks if milestone_id.lower() in str(t.target_release or "").lower()]
    valuable_tasks, excl_tasks, excl_commits = [], [], []

    for t in tasks:
        if is_chore_or_spike_task(t):
            excl_tasks.append(t.canonical_id)
            continue
        valuable_tasks.append(t)
        for c in (t.commits or git_map.get(t.canonical_id, ([], []))[0]):
            if is_chore_or_spike_commit(c):
                excl_commits.append(getattr(c, "hash", "")[:7] or "commit")

    target_prds = set(ms_prd_ids)
    for t in valuable_tasks:
        target_prds.update(f"PRD-{re.search(r'\d+', p).group(0).zfill(4)}" for p in t.governing_prds if re.search(r"\d+", p))

    capabilities, seen_caps = [], set()
    for prd in data.prds:
        c_pid = f"PRD-{re.search(r'\d+', prd.id).group(0).zfill(4)}" if re.search(r"\d+", prd.id) else prd.id
        if target_prds and c_pid not in target_prds:
            continue
        good = extract_what_good_looks_like(prd.raw_markdown) or [(f"Outcome {i+1}", o) for i, o in enumerate(prd.outcomes)]
        for cap_t, cap_d in good:
            if f"{c_pid}:{cap_t}" not in seen_caps:
                seen_caps.add(f"{c_pid}:{cap_t}")
                capabilities.append(CapabilityItem(
                    prd_id=c_pid, prd_title=prd.title, title=cap_t, description=cap_d,
                    doc_url=f"https://specops.github.io/spec-ops/docs/{c_pid.lower()}",
                    visualizer_permalink=f"https://specops.github.io/spec-ops/visualizer/#tab=prds&entity={c_pid}",
                ))

    story_ids = {f"US-{re.search(r'\d+', s).group(0).zfill(4)}" for t in valuable_tasks for s in t.governing_stories if re.search(r"\d+", s)}
    for p in data.prds:
        if target_prds and p.id in target_prds:
            story_ids.update(f"US-{re.search(r'\d+', s).group(0).zfill(4)}" for s in p.linked_stories if re.search(r"\d+", s))

    stories, seen_st = [], set()
    for st in data.stories:
        cid = f"US-{re.search(r'\d+', st.id).group(0).zfill(4)}" if re.search(r"\d+", st.id) else st.id
        if (not story_ids or cid in story_ids) and cid not in seen_st:
            seen_st.add(cid)
            stories.append(StorySummary(id=cid, title=st.title, persona=st.persona, scenarios=extract_story_scenarios(st)))

    active_p = {st.persona.split("(")[0].strip().lower() for st in stories if st.persona}
    active_p.update(prd.target_persona.split("(")[0].strip().lower() for prd in data.prds if target_prds and prd.id in target_prds and prd.target_persona)

    personas = []
    for p in data.personas:
        p_first = p.name.split("—")[0].split("-")[0].strip().lower().split()[0]
        if not active_p or p_first in active_p or p.id.lower() in active_p:
            b = extract_persona_benefits(p)
            if b:
                personas.append(PersonaBenefit(name=p.name, role=p.role, benefits=b))

    return ReleaseNotesData(
        milestone_id=milestone_id, milestone_title=milestone_title,
        capabilities=capabilities, stories=stories, personas=personas,
        excluded_tasks=excl_tasks, excluded_commits=excl_commits,
    )


def render_markdown_release_notes(notes: ReleaseNotesData) -> str:
    lines = [f"# Release Notes: {notes.milestone_title}", "", "## New Capabilities", ""]
    if notes.capabilities:
        curr_prd = ""
        for c in notes.capabilities:
            if c.prd_id != curr_prd:
                curr_prd = c.prd_id
                lines.extend([f"### {c.prd_id}: {c.prd_title}", ""])
            lines.append(f"- **{c.title}**: {c.description}")
        lines.append("")
    else:
        lines.extend(["- Foundations and baseline stability enhancements.", ""])

    lines.extend(["## User Scenarios Added", ""])
    if notes.stories:
        for st in notes.stories:
            lines.append(f"### {st.id}: {st.title}")
            lines.extend(f"- Scenario: {sc}" for sc in st.scenarios)
            lines.append("")
    else:
        lines.extend(["- Core system verification scenarios.", ""])

    lines.extend(["## Persona Impacts", ""])
    if notes.personas:
        for p in notes.personas:
            lines.append(f"### {p.name}" + (f" — {p.role}" if p.role else ""))
            lines.extend(f"- {b}" for b in p.benefits)
            lines.append("")
    else:
        lines.extend(["- Accelerated autonomous delivery loops for hybrid engineering teams.", ""])

    return "\n".join(lines).rstrip() + "\n"


def render_html_release_notes(notes: ReleaseNotesData, branded: bool = False) -> str:
    accent = "#38bdf8"
    if branded:
        brand_hdr = (
            '<div style="text-align:center; padding-bottom:20px; border-bottom:1px solid #334155; margin-bottom:24px;">'
            '<span style="background:#0284c7; color:#fff; font-size:12px; font-weight:700; padding:4px 10px; border-radius:12px; text-transform:uppercase;">SpecOps Release</span>'
            f'<h1 style="color:#f8fafc; font-size:26px; margin:12px 0 6px 0;">{html.escape(notes.milestone_title)}</h1>'
            '<p style="color:#94a3b8; font-size:14px; margin:0;">Customer-Facing Business Value &amp; Capability Changelog</p>'
            '</div>'
        )
    else:
        brand_hdr = f'<h1 style="color:#0f172a; font-size:24px; margin-bottom:20px;">Release Notes: {html.escape(notes.milestone_title)}</h1>'

    cap_cards = []
    for c in notes.capabilities:
        e_t, e_d = html.escape(c.title), html.escape(c.description)
        e_prd = html.escape(f"{c.prd_id}: {c.prd_title}")
        d_link = f'<a href="{html.escape(c.doc_url)}" style="color:{accent}; font-weight:600; text-decoration:none; margin-right:12px;">Live GitHub Pages Documentation &rarr;</a>'
        v_link = f'<a href="{html.escape(c.visualizer_permalink)}" style="color:#10b981; font-weight:600; text-decoration:none;">Visualizer Permalink &rarr;</a>'
        cap_cards.append(
            f'<div style="background:#1e293b; border:1px solid #334155; border-radius:10px; padding:16px; margin-bottom:12px;">'
            f'<div style="font-size:12px; color:#94a3b8; font-weight:700; text-transform:uppercase; margin-bottom:4px;">{e_prd}</div>'
            f'<h3 style="color:#f8fafc; font-size:16px; margin:0 0 6px 0;">{e_t}</h3>'
            f'<p style="color:#cbd5e1; font-size:14px; margin:0 0 12px 0;">{e_d}</p>'
            f'<div>{d_link}{v_link}</div></div>'
        )

    st_cards = [
        f'<div style="background:#1e293b; border:1px solid #334155; border-radius:10px; padding:14px; margin-bottom:10px;">'
        f'<h4 style="color:#f8fafc; font-size:15px; margin:0 0 6px 0;">{html.escape(f"{st.id}: {st.title}")}</h4>'
        f'<ul style="color:#94a3b8; font-size:13px; margin:0; padding-left:18px;">{"".join(f"<li>{html.escape(sc)}</li>" for sc in st.scenarios)}</ul></div>'
        for st in notes.stories
    ]
    p_cards = [
        f'<div style="background:#1e293b; border:1px solid #334155; border-radius:10px; padding:14px; margin-bottom:10px;">'
        f'<h4 style="color:#f8fafc; font-size:15px; margin:0 0 6px 0;">{html.escape(f"{p.name} — {p.role}" if p.role else p.name)}</h4>'
        f'<ul style="color:#94a3b8; font-size:13px; margin:0; padding-left:18px;">{"".join(f"<li>{html.escape(b)}</li>" for b in p.benefits)}</ul></div>'
        for p in notes.personas
    ]

    bg, c_bg = ("#0f172a", "#090d16") if branded else ("#ffffff", "#f8fafc")
    c_bdr = "border:1px solid #1e293b;" if branded else "border:1px solid #e2e8f0;"
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Release Notes: {html.escape(notes.milestone_title)}</title>'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>'
        f'<body style="background:{bg}; margin:0; padding:24px 12px; font-family:-apple-system,BlinkMacSystemFont,sans-serif;">'
        f'<div style="max-width:680px; margin:0 auto; background:{c_bg}; border-radius:14px; {c_bdr} padding:28px;">'
        f'{brand_hdr}'
        f'<h2 style="color:{accent}; font-size:17px; margin:20px 0 12px 0; text-transform:uppercase;">New Capabilities</h2>'
        f'{"".join(cap_cards) or "<p style=\'color:#94a3b8;\'>No new capabilities recorded.</p>"}'
        f'<h2 style="color:{accent}; font-size:17px; margin:24px 0 12px 0; text-transform:uppercase;">User Scenarios Added</h2>'
        f'{"".join(st_cards) or "<p style=\'color:#94a3b8;\'>No new user scenarios recorded.</p>"}'
        f'<h2 style="color:{accent}; font-size:17px; margin:24px 0 12px 0; text-transform:uppercase;">Persona Impacts</h2>'
        f'{"".join(p_cards) or "<p style=\'color:#94a3b8;\'>No persona impacts recorded.</p>"}'
        '</div></body></html>\n'
    )


def generate_release_notes(
    milestone_id: str,
    config: SpecOpsConfig,
    format_type: str = "markdown",
    branded: bool = False,
    output_path: str | Path | None = None,
    data: ProjectData | None = None,
) -> tuple[Path, str]:
    notes = build_release_notes_data(milestone_id, config, data=data)
    slug = milestone_slug(milestone_id)
    is_html = format_type.lower() == "html"
    content = render_html_release_notes(notes, branded=branded) if is_html else render_markdown_release_notes(notes)
    ext = "html" if is_html else "md"

    if output_path:
        dest = Path(output_path)
        if not dest.is_absolute():
            dest = config.root_dir / dest
    else:
        dest = config.docs_dir / "reference" / f"release-notes-{slug}.{ext}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest, content
