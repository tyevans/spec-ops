"""Team Delivery Velocity Engine and Cognitive Churn Heatmap (US-0052, PRD-0005, ADR-0008)."""

from __future__ import annotations

import html
import json
import math
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.parser import extract_frontmatter


@dataclass
class FileChurnStat:
    file_path: str
    commits: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    total_changes: int = 0
    current_lines: int = 0
    churn_score: float = 0.0
    risk_level: str = "LOW"
    is_warning: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskLeadTimeStat:
    task_id: str
    title: str = ""
    target_bc: str = ""
    lead_time_days: float = 0.0
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VelocityHeatmapReport:
    total_completed_tasks: int = 0
    total_commits: int = 0
    throughput_tasks_per_week: float = 0.0
    avg_lead_time_days: float = 0.0
    median_lead_time_days: float = 0.0
    cadence_commits_per_day: float = 0.0
    time_window_days: float = 1.0
    task_stats: list[TaskLeadTimeStat] = field(default_factory=list)
    churn_stats: list[FileChurnStat] = field(default_factory=list)
    high_churn_files: list[FileChurnStat] = field(default_factory=list)
    complexity_warnings: list[FileChurnStat] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_file_churn(
    file_records: list[dict[str, Any]], repo_dir: Path | None = None
) -> list[FileChurnStat]:
    """Computes file churn scores, complexity thresholds, and risk levels."""
    stats: list[FileChurnStat] = []
    for rec in file_records:
        path = str(rec.get("file_path", "")).strip()
        if not path:
            continue
        commits = max(0, int(rec.get("commits", 0)))
        added = max(0, int(rec.get("lines_added", 0)))
        deleted = max(0, int(rec.get("lines_deleted", 0)))
        changes = added + deleted
        score = round(commits * 2.0 + changes * 0.05, 2)
        cur_lines = 0
        if repo_dir and (repo_dir / path).is_file():
            try:
                cur_lines = sum(1 for _ in (repo_dir / path).open("rb"))
            except Exception:
                cur_lines = 0
        risk = (
            "CRITICAL" if cur_lines >= 500 or score >= 100.0
            else "HIGH" if cur_lines >= 400 or score >= 50.0
            else "MODERATE" if cur_lines >= 250 or score >= 20.0
            else "LOW"
        )
        is_warn = cur_lines >= 400 or risk in ("HIGH", "CRITICAL")
        stats.append(FileChurnStat(path, commits, added, deleted, changes, cur_lines, score, risk, is_warn))
    stats.sort(key=lambda s: (s.churn_score, s.total_changes), reverse=True)
    return stats


def compute_velocity_metrics(
    completed_task_count: int,
    lead_times_days: list[float],
    commit_count: int,
    time_span_days: float,
) -> tuple[float, float, float, float, float]:
    """Computes throughput, lead times, and cadence ensuring non-negative mathematical validity."""
    valid_leads = [max(0.0, float(t)) for t in lead_times_days if isinstance(t, (int, float)) and math.isfinite(t)]
    avg_lead = round(sum(valid_leads) / len(valid_leads), 2) if valid_leads else 0.0
    sorted_leads = sorted(valid_leads)
    n = len(sorted_leads)
    med_lead = 0.0 if n == 0 else (round(sorted_leads[n // 2], 2) if n % 2 == 1 else round((sorted_leads[n // 2 - 1] + sorted_leads[n // 2]) / 2.0, 2))
    span = max(0.14, float(time_span_days)) if isinstance(time_span_days, (int, float)) and math.isfinite(time_span_days) else 1.0
    throughput = round(max(0, int(completed_task_count)) / (span / 7.0), 2)
    cadence = round(max(0, int(commit_count)) / max(1.0, span), 2)
    return avg_lead, med_lead, throughput, cadence, round(span, 2)


def to_utc_dt(val: str) -> datetime | None:
    """Parses ISO string to timezone-aware UTC datetime."""
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.fromisoformat(val[:10])
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None


def parse_git_history(
    repo_dir: Path | str, max_commits: int = 1000
) -> tuple[dict[str, dict[str, int]], int, list[datetime]]:
    """Harvests commit history, numstat modifications, and date ranges."""
    repo = Path(repo_dir).resolve()
    if not ((repo / ".git").exists() or (repo / ".git").is_file()):
        return {}, 0, []
    cmd = ["git", "log", f"-n{max_commits}", "--numstat", "--format=COMMIT:%H|%aI"]
    try:
        res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
    except Exception:
        return {}, 0, []
    if res.returncode != 0 or not res.stdout:
        return {}, 0, []

    file_map: dict[str, dict[str, int]] = {}
    commit_dates: list[datetime] = []
    total_commits = 0
    current_files: set[str] = set()
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("COMMIT:"):
            total_commits += 1
            current_files = set()
            parts = line.split("|")
            if len(parts) >= 2:
                dt = to_utc_dt(parts[1])
                if dt:
                    commit_dates.append(dt)
            continue
        m = re.match(r"^(\d+|-)\s+(\d+|-)\s+(.+)$", line)
        if m:
            raw_add, raw_del, raw_path = m.groups()
            path = re.sub(r"=>\s+", "", re.sub(r"\{.*? => (.*?)\}", r"\1", raw_path)).strip()
            add = int(raw_add) if raw_add.isdigit() else 0
            del_cnt = int(raw_del) if raw_del.isdigit() else 0
            if path not in file_map:
                file_map[path] = {"commits": 0, "lines_added": 0, "lines_deleted": 0}
            if path not in current_files:
                file_map[path]["commits"] += 1
                current_files.add(path)
            file_map[path]["lines_added"] += add
            file_map[path]["lines_deleted"] += del_cnt
    return file_map, total_commits, commit_dates


def extract_completed_tasks(repo_dir: Path, config: SpecOpsConfig | None = None) -> list[TaskLeadTimeStat]:
    """Extracts completed tasks and lead times from repository backlog."""
    c_dir = config.backlog_dir / "complete" if config else repo_dir / "docs" / "project" / "backlog" / "complete"
    if not c_dir.is_dir():
        return []
    stats: list[TaskLeadTimeStat] = []
    for p in sorted(c_dir.glob("*.md")):
        try:
            meta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        tid = str(meta.get("id", p.stem.split("-")[0]))
        c_raw = str(meta.get("created", "") or meta.get("created_at", "")).strip()
        d_raw = str(meta.get("completed", "") or meta.get("completed_at", "") or meta.get("signed_off_at", "")).strip()
        lead_days = 0.0
        c_dt, d_dt = to_utc_dt(c_raw), to_utc_dt(d_raw)
        if c_dt and d_dt:
            lead_days = max(0.0, float((d_dt - c_dt).days))
        elif d_raw or c_raw:
            lead_days = 1.0
        stats.append(TaskLeadTimeStat(tid, str(meta.get("title", p.stem)), str(meta.get("target_bc", "")), lead_days, d_raw))
    return stats


def analyze_velocity_and_churn(repo_dir: Path | str, config: SpecOpsConfig | None = None) -> VelocityHeatmapReport:
    """Orchestrates delivery velocity metrics calculation and file churn heatmap."""
    repo = Path(repo_dir).resolve()
    file_map, commit_count, commit_dates = parse_git_history(repo)
    task_stats = extract_completed_tasks(repo, config=config)
    file_records = [
        {"file_path": f, "commits": d["commits"], "lines_added": d["lines_added"], "lines_deleted": d["lines_deleted"]}
        for f, d in file_map.items()
    ]
    churn_stats = compute_file_churn(file_records, repo_dir=repo)
    all_dates = list(commit_dates)
    for t in task_stats:
        if t.completed_at:
            t_dt = to_utc_dt(t.completed_at)
            if t_dt:
                all_dates.append(t_dt)
    span_days = max(1.0, (max(all_dates) - min(all_dates)).total_seconds() / 86400.0) if len(all_dates) >= 2 else 1.0
    leads = [t.lead_time_days for t in task_stats]
    avg_l, med_l, throughput, cadence, final_span = compute_velocity_metrics(
        len(task_stats), leads, commit_count, span_days
    )

    return VelocityHeatmapReport(
        total_completed_tasks=len(task_stats), total_commits=commit_count, throughput_tasks_per_week=throughput,
        avg_lead_time_days=avg_l, median_lead_time_days=med_l, cadence_commits_per_day=cadence,
        time_window_days=final_span, task_stats=task_stats, churn_stats=churn_stats,
        high_churn_files=[f for f in churn_stats[:10] if f.churn_score > 0],
        complexity_warnings=[f for f in churn_stats if f.is_warning],
    )


def render_velocity_markdown(report: VelocityHeatmapReport) -> str:
    """Formats velocity report and churn heatmap in GitHub Markdown."""
    lines = [
        "# Team Delivery Velocity & Cognitive Churn Heatmap", "",
        f"**Generated:** {report.generated_at}  ", f"**Time Horizon:** {report.time_window_days} days", "",
        "## Delivery Velocity Metrics", "",
        "| Metric | Value |", "|---|---|",
        f"| Task Completion Rates (Delivered) | {report.total_completed_tasks} tasks |",
        f"| Delivery Throughput | {report.throughput_tasks_per_week} tasks/week |",
        f"| Total Commits Analyzed | {report.total_commits} commits |",
        f"| Average Lead Time | {report.avg_lead_time_days} days |",
        f"| Median Lead Time | {report.median_lead_time_days} days |",
        f"| Completion Cadence | {report.cadence_commits_per_day} commits/day |", "",
        "## Cognitive Churn Heatmap (High-Churn Source Files)", "",
    ]
    if report.high_churn_files:
        lines.extend(["| File | Commits | Additions | Deletions | Changes | Lines | Churn Score | Risk |", "|---|---|---|---|---|---|---|---|"])
        for f in report.high_churn_files:
            lines.append(f"| `{f.file_path}` | {f.commits} | +{f.lines_added} | -{f.lines_deleted} | {f.total_changes} | {f.current_lines} | {f.churn_score} | {f.risk_level} |")
    else:
        lines.append("_No file modification churn recorded._")
    lines.extend(["", "## Complexity Threshold Warnings", ""])
    if report.complexity_warnings:
        for w in report.complexity_warnings:
            lines.append(f"- ⚠️ **`{w.file_path}`**: {w.current_lines} lines (Churn: {w.churn_score}, Risk: {w.risk_level})")
    else:
        lines.append("✅ All modules conform to complexity thresholds (<400 lines).")
    return "\n".join(lines).rstrip() + "\n"


def render_velocity_html(report: VelocityHeatmapReport) -> str:
    """Renders standalone, zero-external-CDN HTML delivery velocity and churn heatmap."""
    max_churn = max((f.churn_score for f in report.churn_stats), default=1.0) or 1.0
    rows = []
    for f in report.churn_stats[:25]:
        pct = min(100, int((f.churn_score / max_churn) * 100))
        c = "#ef4444" if f.risk_level == "CRITICAL" else "#f59e0b" if f.risk_level == "HIGH" else "#38bdf8" if f.risk_level == "MODERATE" else "#10b981"
        bar = f'<div style="background:#334155;border-radius:4px;height:10px;width:80px;display:inline-block;overflow:hidden;vertical-align:middle;margin-right:8px;"><div style="background:{c};height:100%;width:{pct}%;"></div></div>'
        rows.append(
            f'<tr><td><code>{html.escape(f.file_path)}</code></td><td>{f.commits}</td>'
            f'<td style="color:#10b981;">+{f.lines_added}</td><td style="color:#ef4444;">-{f.lines_deleted}</td>'
            f'<td>{f.total_changes}</td><td>{f.current_lines}</td><td>{bar}{f.churn_score}</td>'
            f'<td><span style="background:{c}22;color:{c};padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600;">{f.risk_level}</span></td></tr>'
        )
    warn_items = "".join(f'<li><strong>{html.escape(w.file_path)}</strong>: {w.current_lines} lines ({w.risk_level})</li>' for w in report.complexity_warnings) if report.complexity_warnings else "<li>All monitored modules conform to ADR-0002 (<400 lines).</li>"

    css = "body{font-family:sans-serif;background:#0f172a;color:#f8fafc;margin:0;padding:24px}.container{max-width:1100px;margin:0 auto}h1,h2{color:#38bdf8}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:18px 0}.card{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px;text-align:center}.card-val{font-size:26px;font-weight:700;color:#f8fafc;margin-top:4px}.card-lbl{font-size:12px;color:#94a3b8;text-transform:uppercase}table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;margin:18px 0;border:1px solid #334155}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #334155;font-size:13px}th{background:#090d16;color:#94a3b8;text-transform:uppercase;font-size:11px}code{font-family:monospace;color:#38bdf8}.warn-box{background:rgba(245,158,11,0.1);border:1px solid #f59e0b;border-radius:8px;padding:14px;margin:18px 0}"
    tbody = "".join(rows) if rows else '<tr><td colspan="8">No commit activity detected.</td></tr>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Team Delivery Velocity &amp; Cognitive Churn Heatmap</title><style>{css}</style></head>
<body><div class="container">
<h1>Team Delivery Velocity &amp; Cognitive Churn Heatmap</h1>
<p style="color:#94a3b8;">Generated: {html.escape(report.generated_at)} • Horizon: {report.time_window_days} days</p>
<div class="cards">
  <div class="card"><div class="card-lbl">Completed Tasks</div><div class="card-val">{report.total_completed_tasks}</div></div>
  <div class="card"><div class="card-lbl">Throughput</div><div class="card-val">{report.throughput_tasks_per_week}<span style="font-size:13px;color:#94a3b8;">/wk</span></div></div>
  <div class="card"><div class="card-lbl">Avg Lead Time</div><div class="card-val">{report.avg_lead_time_days}<span style="font-size:13px;color:#94a3b8;">d</span></div></div>
  <div class="card"><div class="card-lbl">Median Lead Time</div><div class="card-val">{report.median_lead_time_days}<span style="font-size:13px;color:#94a3b8;">d</span></div></div>
  <div class="card"><div class="card-lbl">Commits</div><div class="card-val">{report.total_commits}</div></div>
  <div class="card"><div class="card-lbl">Cadence</div><div class="card-val">{report.cadence_commits_per_day}<span style="font-size:13px;color:#94a3b8;">/d</span></div></div>
</div>
<h2>Cognitive Churn Heatmap</h2>
<table><thead><tr><th>File</th><th>Commits</th><th>+</th><th>-</th><th>Changes</th><th>Lines</th><th>Churn Score</th><th>Risk</th></tr></thead>
<tbody>{tbody}</tbody></table>
<div class="warn-box"><h3 style="color:#f59e0b;margin-top:0;">Complexity Threshold Alerts (ADR-0002)</h3><ul>{warn_items}</ul></div>
</div></body></html>
"""


def render_velocity_json(report: VelocityHeatmapReport) -> str:
    """Renders structured JSON report."""
    return json.dumps(report.to_dict(), indent=2)


def generate_velocity_heatmap(
    config: SpecOpsConfig,
    format_type: str = "markdown",
    output_path: str | Path | None = None,
) -> tuple[Path, str]:
    """Generates delivery velocity and churn heatmap report and writes to output target."""
    report = analyze_velocity_and_churn(config.root_dir, config=config)
    fmt = format_type.lower()
    if fmt == "html":
        content, ext = render_velocity_html(report), "html"
    elif fmt == "json":
        content, ext = render_velocity_json(report), "json"
    else:
        content, ext = render_velocity_markdown(report), "md"

    if output_path:
        dest = Path(output_path)
        if not dest.is_absolute():
            dest = config.root_dir / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    else:
        dest = config.root_dir / "dist" / f"velocity-heatmap.{ext}"

    return dest, content
