"""Executive roadmap visualizer and milestone horizon exporter (ADR-0001, ADR-0002, ADR-0009)."""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester


@dataclass
class RoadmapMilestone:
    """Structured milestone with delivery horizon and completion progress."""

    id: str
    display_name: str
    title: str
    status: str
    horizon: str
    tasks: list[str] = field(default_factory=list)
    completed_tasks: list[str] = field(default_factory=list)
    progress_pct: float = 0.0
    task_commits: dict[str, str] = field(default_factory=dict)


def calculate_progress(completed: int, total: int) -> float:
    """Calculates completion percentage rounded to 1 decimal place."""
    if total <= 0 or completed <= 0:
        return 0.0
    return round((completed / total) * 100.0, 1)


def parse_roadmap_file(roadmap_path: Path) -> list[dict[str, Any]]:
    """Parses ROADMAP.md into milestone dictionaries with task IDs and target horizons."""
    if not roadmap_path.exists():
        return []

    lines = roadmap_path.read_text(encoding="utf-8").splitlines()
    milestones: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in lines:
        header_match = re.match(
            r"^##\s+(?:Milestone\s+)?([A-Za-z0-9\-]+)(?::\s*([^(\n]+))?(?:\s*\(([^)]+)\))?",
            line,
            re.IGNORECASE,
        )
        if header_match:
            if current:
                milestones.append(current)
            raw_id = header_match.group(1).strip()
            title = (header_match.group(2) or raw_id).strip()
            status = (header_match.group(3) or "Active").strip()
            m_num = raw_id.upper().replace("MILESTONE", "").replace("-", "").strip()
            display_id = f"M{m_num}" if m_num.isdigit() else raw_id
            current = {
                "id": display_id,
                "display_name": f"{display_id} {title}".strip(),
                "title": title,
                "status": status,
                "tasks": [],
                "horizon": "2026-10-15",
            }
            continue

        if current:
            for tid in re.findall(r"`?(TASK-\d+)`?", line):
                cid = f"TASK-{tid.split('-')[-1].zfill(4)}"
                if cid not in current["tasks"]:
                    current["tasks"].append(cid)

            date_match = re.search(
                r"(?:completion date|target horizon|horizon closed for)[^:]*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
                line,
                re.IGNORECASE,
            )
            if date_match:
                current["horizon"] = date_match.group(1).strip()

    if current:
        milestones.append(current)

    return milestones


def load_roadmap_milestones(config: SpecOpsConfig) -> list[RoadmapMilestone]:
    """Loads roadmap milestones with git commit logs and completed task states."""
    roadmap_path = config.backlog_dir / "ROADMAP.md"
    raw_milestones = parse_roadmap_file(roadmap_path)

    harvester = GitMetadataHarvester(config.root_dir)
    git_map = harvester.harvest()

    completed_dir = config.backlog_dir / "complete"
    completed_disk_ids: set[str] = set()
    if completed_dir.exists():
        for f in completed_dir.glob("*.md"):
            m = re.match(r"^(\d+)-", f.name)
            if m:
                completed_disk_ids.add(f"TASK-{m.group(1).zfill(4)}")

    results: list[RoadmapMilestone] = []
    for raw in raw_milestones:
        tasks = raw["tasks"]
        completed: list[str] = []
        commits: dict[str, str] = {}

        for tid in tasks:
            has_commits = tid in git_map and len(git_map[tid][0]) > 0
            is_complete = tid in completed_disk_ids or has_commits
            if has_commits:
                commits[tid] = git_map[tid][0][0].hash
            elif is_complete:
                commits[tid] = "HEAD"
            if is_complete:
                completed.append(tid)

        pct = calculate_progress(len(completed), len(tasks))
        results.append(
            RoadmapMilestone(
                id=raw["id"],
                display_name=raw["display_name"],
                title=raw["title"],
                status=raw["status"],
                horizon=raw["horizon"],
                tasks=tasks,
                completed_tasks=completed,
                progress_pct=pct,
                task_commits=commits,
            )
        )

    return results


def render_roadmap_svg(milestones: list[RoadmapMilestone], project_name: str = "SpecOps") -> str:
    """Generates a high-resolution, self-contained SVG roadmap graphic grouped by horizon."""
    card_h, header_h, spacing, margin, width = 140, 120, 25, 40, 960
    total_height = header_h + (max(1, len(milestones)) * (card_h + spacing)) + margin

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_height}" width="{width}" height="{total_height}">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0b0f19"/><stop offset="100%" stop-color="#111827"/></linearGradient>',
        '<linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#10b981"/></linearGradient></defs>',
        f'<rect width="{width}" height="{total_height}" fill="url(#bg)"/>',
        f'<text x="{margin}" y="50" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="24" font-weight="700">Executive Delivery Roadmap — {html.escape(project_name)}</text>',
        f'<text x="{margin}" y="76" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="13">Milestone delivery horizons and task completion progress based on git commit history</text>',
    ]

    curr_y = header_h
    for ms in milestones:
        card_w = width - (margin * 2)
        bar_w = card_w - 60
        fill_w = max(0.0, round((ms.progress_pct / 100.0) * bar_w, 1))
        status_color = "#10b981" if ms.progress_pct >= 100.0 or ms.status.lower() == "complete" else "#38bdf8"
        disp_title = html.escape(ms.display_name)
        stats_txt = html.escape(f"{ms.progress_pct}% · {len(ms.completed_tasks)}/{len(ms.tasks)} tasks completed")

        svg_parts.extend([
            f'<g class="milestone-card" transform="translate({margin}, {curr_y})">',
            f'<rect width="{card_w}" height="{card_h}" rx="12" fill="#131a29" stroke="#202b42" stroke-width="1.5"/>',
            f'<text x="30" y="38" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700">{disp_title}</text>',
            f'<rect x="{card_w - 130}" y="20" width="100" height="24" rx="12" fill="#1e293b" stroke="{status_color}" stroke-width="1"/>',
            f'<text x="{card_w - 80}" y="36" fill="{status_color}" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600" text-anchor="middle">{html.escape(ms.status)}</text>',
            f'<text x="30" y="62" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="12">Target Horizon: {html.escape(ms.horizon)}</text>',
            f'<text x="{card_w - 30}" y="62" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="12" text-anchor="end">{stats_txt}</text>',
            f'<rect x="30" y="78" width="{bar_w}" height="14" rx="7" fill="#1a2337"/>',
            f'<rect x="30" y="78" width="{fill_w}" height="14" rx="7" fill="url(#bar)"/>',
        ])

        chip_x = 30
        for tid in ms.tasks[:6]:
            chip_color = "#10b981" if tid in ms.completed_tasks else "#64748b"
            commit_lbl = ms.task_commits.get(tid, "")
            lbl = f"{tid} ({commit_lbl[:7]})" if commit_lbl and commit_lbl != "HEAD" else tid
            svg_parts.extend([
                f'<rect x="{chip_x}" y="104" width="90" height="18" rx="4" fill="#1e293b" stroke="{chip_color}" stroke-width="1"/>',
                f'<text x="{chip_x + 45}" y="117" fill="{chip_color}" font-family="monospace" font-size="9" text-anchor="middle">{html.escape(lbl)}</text>',
            ])
            chip_x += 98

        svg_parts.append("</g>")
        curr_y += card_h + spacing

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Executive Delivery Roadmap &amp; Milestone Horizons</title>
<style>
:root {{ --bg: #090d16; --card: #131a29; --border: #202b42; --primary: #38bdf8; --success: #10b981; --text: #f8fafc; --muted: #94a3b8; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; height: 100vh; display: flex; align-items: center; justify-content: center; overflow: hidden; }}
.deck-container {{ width: 90vw; max-width: 1100px; height: 82vh; background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 36px; display: flex; flex-direction: column; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.7); }}
.slide {{ display: none; height: 100%; flex-direction: column; justify-content: space-between; }}
.slide.active {{ display: flex; }}
.header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; }}
.header h1 {{ font-size: 1.5rem; color: #fff; }}
.badges {{ display: flex; gap: 8px; }}
.badge {{ background: #0369a1; color: #fff; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; }}
.body {{ flex: 1; padding: 20px 0; overflow-y: auto; }}
.footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 16px; font-size: 0.85rem; color: var(--muted); }}
.metric-box {{ background: #1a2337; border: 1px solid var(--border); border-radius: 12px; padding: 18px; text-align: center; }}
.horizon-card {{ background: #1a2337; border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; margin-bottom: 14px; }}
.horizon-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
.bar-bg {{ background: #0f172a; border-radius: 9999px; height: 10px; overflow: hidden; margin: 8px 0; border: 1px solid var(--border); }}
.bar-fill {{ background: linear-gradient(90deg, #38bdf8, #10b981); height: 100%; border-radius: 9999px; }}
.tasks-grid {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
.task-pill {{ font-family: monospace; font-size: 0.72rem; padding: 3px 8px; border-radius: 4px; border: 1px solid var(--border); }}
.task-pill.done {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }}
.task-pill.todo {{ background: rgba(148, 163, 184, 0.1); color: var(--muted); }}
.persona-card {{ background: #1a2337; border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; }}
</style>
</head>
<body>
<div class="deck-container">
  <div class="slide active" data-slide="1">
    <div class="header">
      <h1>Executive Overview &amp; Milestone Horizons</h1>
      <div class="badges"><span class="badge">{audience}</span><span class="badge">{granularity}</span></div>
    </div>
    <div class="body" style="display:flex; align-items:center; gap:40px;">
      <div style="text-align:center;">
        <svg width="180" height="180" viewBox="0 0 140 140">
          <circle cx="70" cy="70" r="54" fill="none" stroke="#1e293b" stroke-width="12"/>
          <circle cx="70" cy="70" r="54" fill="none" stroke="#10b981" stroke-width="12" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}" stroke-linecap="round" transform="rotate(-90 70 70)"/>
          <text x="70" y="74" text-anchor="middle" fill="#fff" font-size="24" font-weight="bold">{overall_pct}%</text>
          <text x="70" y="92" text-anchor="middle" fill="#94a3b8" font-size="11">Overall Progress</text>
        </svg>
      </div>
      <div style="flex:1; display:grid; grid-template-columns:1fr 1fr; gap:16px;">
        <div class="metric-box"><div style="font-size:2rem; font-weight:800; color:#38bdf8;">{completed_tasks}</div><div style="color:var(--muted); font-size:0.85rem;">Completed Deliverables</div></div>
        <div class="metric-box"><div style="font-size:2rem; font-weight:800; color:#10b981;">{remaining_tasks}</div><div style="color:var(--muted); font-size:0.85rem;">Remaining Deliverables</div></div>
        <div class="metric-box"><div style="font-size:2rem; font-weight:800; color:#a78bfa;">{total_milestones}</div><div style="color:var(--muted); font-size:0.85rem;">Milestone Horizons</div></div>
        <div class="metric-box"><div style="font-size:2rem; font-weight:800; color:#34d399;">100%</div><div style="color:var(--muted); font-size:0.85rem;">Git Commit Ground Truth</div></div>
      </div>
    </div>
    <div class="footer"><span>Slide 1 of 3: Executive Overview</span><span>Press Space / Arrow Keys to navigate</span></div>
  </div>
  <div class="slide" data-slide="2">
    <div class="header"><h1>Milestone Delivery Horizons &amp; Progress</h1><span class="badge">{total_milestones} Horizons</span></div>
    <div class="body">{milestones_html}</div>
    <div class="footer"><span>Slide 2 of 3: Horizon Milestones</span><span>Press Space / Arrow Keys to navigate</span></div>
  </div>
  <div class="slide" data-slide="3">
    <div class="header"><h1>Stakeholder Impact &amp; Persona Value Matrix</h1><span class="badge">Persona Alignment</span></div>
    <div class="body">{personas_html}</div>
    <div class="footer"><span>Slide 3 of 3: Persona Value Matrix</span><span>Press Space / Arrow Keys to navigate</span></div>
  </div>
</div>
<script>
let cur = 1;
function setSlide(n) {{ cur = n < 1 ? 3 : (n > 3 ? 1 : n); document.querySelectorAll('.slide').forEach(s => s.classList.remove('active')); const t = document.querySelector('.slide[data-slide="' + cur + '"]'); if (t) t.classList.add('active'); }}
window.addEventListener('keydown', (e) => {{ if (['ArrowRight','ArrowDown',' ','PageDown'].includes(e.key)) {{ e.preventDefault(); setSlide(cur + 1); }} else if (['ArrowLeft','ArrowUp','PageUp'].includes(e.key)) {{ e.preventDefault(); setSlide(cur - 1); }} }});
</script>
</body>
</html>"""


def render_roadmap_html(
    milestones: list[RoadmapMilestone],
    config: SpecOpsConfig | None = None,
    audience: str = "Leadership / Non-Technical",
    granularity: str = "Milestones & PRD Outcomes",
) -> str:
    """Renders a standalone, airgap-compliant single-file HTML presentation for stakeholders."""
    total_tasks = sum(len(m.tasks) for m in milestones)
    completed_tasks = sum(len(m.completed_tasks) for m in milestones)
    overall_pct = calculate_progress(completed_tasks, total_tasks)
    circumference = 2 * math.pi * 54
    offset = circumference - (overall_pct / 100.0 * circumference)

    ms_html = []
    for ms in milestones:
        pills = "".join(f'<div class="task-pill {"done" if tid in ms.completed_tasks else "todo"}">{html.escape(tid)}</div>' for tid in ms.tasks[:12])
        ms_html.append(f"""<div class="horizon-card"><div class="horizon-header"><div><div style="font-weight:700; font-size:1.1rem; color:#fff;">{html.escape(ms.display_name)}</div>
        <div style="font-size:0.8rem; color:var(--muted); margin-top:2px;">Target Horizon: {html.escape(ms.horizon)} · {len(ms.completed_tasks)}/{len(ms.tasks)} deliverables</div></div>
        <span class="badge">{html.escape(ms.status)}</span></div><div class="bar-bg"><div class="bar-fill" style="width:{ms.progress_pct}%;"></div></div><div class="tasks-grid">{pills}</div></div>""")

    personas = [
        ("Taylor", "Product Manager & Technical Writer", "Direct traceability from business outcomes to executable Gherkin scenarios without raw code."),
        ("Alex", "Agentic Systems Architect", "Context rot occurs when specs drift from git code; version-locking eliminates drift."),
        ("Jordan", "AI-Native Engineering Lead", "Blackbox frontdoor testing rules ensure agents verify software like real external users."),
        ("Morgan", "Autonomous Coding Agent", "Strict worktree isolation keeps git history clean and pull requests conflict-free."),
        ("Riley", "Human IC Developer", "Seamless worktree takeover and ergonomic keybindings reduce claiming friction to seconds."),
    ]
    p_html = [f"""<div class="persona-card"><div style="font-weight:700; color:#38bdf8; font-size:0.95rem;">{html.escape(n)} — <span style="font-weight:400; color:var(--muted); font-size:0.85rem;">{html.escape(r)}</span></div><div style="font-style:italic; color:#e2e8f0; font-size:0.85rem; margin-top:4px;">"{html.escape(q)}"</div></div>""" for n, r, q in personas]

    return HTML_TEMPLATE.format(
        audience=html.escape(audience),
        granularity=html.escape(granularity),
        circumference=circumference,
        offset=offset,
        overall_pct=overall_pct,
        completed_tasks=completed_tasks,
        remaining_tasks=total_tasks - completed_tasks,
        total_milestones=len(milestones),
        milestones_html="".join(ms_html),
        personas_html="".join(p_html),
    )


def export_roadmap(
    config: SpecOpsConfig,
    format: str = "svg",
    output_path: str | Path | None = None,
    audience: str = "Leadership / Non-Technical",
    granularity: str = "Milestones & PRD Outcomes",
) -> Path:
    """Exports executive roadmap vector SVG or standalone HTML presentation."""
    milestones = load_roadmap_milestones(config)
    fmt = format.lower().strip()
    if not output_path:
        ext = "html" if fmt == "html" else "svg"
        dest = config.root_dir / "dist" / f"roadmap.{ext}"
    else:
        dest = Path(output_path)
        if not dest.is_absolute():
            dest = config.root_dir / dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "html":
        content = render_roadmap_html(milestones, config, audience=audience, granularity=granularity)
    else:
        content = render_roadmap_svg(milestones, project_name=config.project.name)

    dest.write_text(content, encoding="utf-8")
    return dest
