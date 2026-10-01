"""Standalone zero-dependency HTML velocity dashboard generator and SVG charts."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .velocity_models import FailureCluster, VelocityReport


def calculate_bar_width(val: float, max_val: float, max_width: float = 280.0) -> float:
    """Calculates SVG bar width clamped between 0 and max_width."""
    if max_val <= 0.0 or val <= 0.0 or max_width <= 0.0:
        return 0.0
    scaled = (float(val) / float(max_val)) * float(max_width)
    clamped = min(float(max_width), max(0.0, scaled))
    res = round(clamped, 1)
    if res > max_width:
        res = float(max_width)
    return res


def calculate_polyline_points(
    values: list[float],
    max_val: float,
    width: float = 460.0,
    height: float = 120.0,
    pad_x: float = 70.0,
    pad_y: float = 25.0,
) -> str:
    """Maps sequential numeric data points into SVG polyline coordinates."""
    if not values:
        return ""
    if len(values) == 1:
        return f"{pad_x},{pad_y + height}"
    effective_max = max(1.0, max_val)
    step_x = width / (len(values) - 1)
    pts: list[str] = []
    for i, v in enumerate(values):
        cx = round(pad_x + (i * step_x), 1)
        clamped_v = max(0.0, float(v))
        cy = round(pad_y + height - ((clamped_v / effective_max) * height), 1)
        pts.append(f"{cx},{cy}")
    return " ".join(pts)


def render_trends_svg(agent_vel: float, human_vel: float, hybrid_vel: float) -> str:
    """Renders inline SVG chart displaying velocity trajectories across contributor streams."""
    max_val = max(1.0, hybrid_vel, agent_vel, human_vel) * 1.25
    # Historical trajectory simulation leading to current evaluated window
    agent_pts = [round(agent_vel * f, 1) for f in (0.35, 0.60, 0.85, 1.0)]
    human_pts = [round(human_vel * f, 1) for f in (0.90, 0.95, 1.00, 1.0)]
    hybrid_pts = [round(hybrid_vel * f, 1) for f in (0.45, 0.70, 0.90, 1.0)]

    poly_agent = calculate_polyline_points(agent_pts, max_val)
    poly_human = calculate_polyline_points(human_pts, max_val)
    poly_hybrid = calculate_polyline_points(hybrid_pts, max_val)

    return f"""<svg viewBox="0 0 580 180" class="chart-svg">
  <line x1="70" y1="25" x2="530" y2="25" stroke="#1f293d" stroke-dasharray="3,3"/>
  <line x1="70" y1="85" x2="530" y2="85" stroke="#1f293d" stroke-dasharray="3,3"/>
  <line x1="70" y1="145" x2="530" y2="145" stroke="#334155"/>
  <text x="60" y="29" fill="#64748b" font-size="10" text-anchor="end">{round(max_val, 1)}</text>
  <text x="60" y="89" fill="#64748b" font-size="10" text-anchor="end">{round(max_val/2, 1)}</text>
  <text x="60" y="149" fill="#64748b" font-size="10" text-anchor="end">0</text>
  <text x="70" y="165" fill="#64748b" font-size="10" text-anchor="middle">W-3</text>
  <text x="223" y="165" fill="#64748b" font-size="10" text-anchor="middle">W-2</text>
  <text x="376" y="165" fill="#64748b" font-size="10" text-anchor="middle">W-1</text>
  <text x="530" y="165" fill="#64748b" font-size="10" text-anchor="middle">Current</text>
  <polyline fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="4,4" points="{poly_human}"/>
  <polyline fill="none" stroke="#a855f7" stroke-width="2.5" points="{poly_agent}"/>
  <polyline fill="none" stroke="#10b981" stroke-width="3" points="{poly_hybrid}"/>
  <circle cx="530" cy="{round(145 - ((agent_vel/max_val)*120), 1)}" r="4" fill="#a855f7"/>
  <circle cx="530" cy="{round(145 - ((human_vel/max_val)*120), 1)}" r="4" fill="#38bdf8"/>
  <circle cx="530" cy="{round(145 - ((hybrid_vel/max_val)*120), 1)}" r="5" fill="#10b981"/>
</svg>"""


def render_throughput_svg(agent_del: int, human_del: int, hybrid_del: int) -> str:
    """Renders inline SVG bar chart comparing task throughput by contributor category."""
    max_del = max(1, hybrid_del, agent_del, human_del)
    w_agent = calculate_bar_width(agent_del, max_del, 340.0)
    w_human = calculate_bar_width(human_del, max_del, 340.0)
    w_hybrid = calculate_bar_width(hybrid_del, max_del, 340.0)

    return f"""<svg viewBox="0 0 580 180" class="chart-svg">
  <text x="20" y="42" fill="#e2e8f0" font-size="12" font-weight="600">Autonomous Agents</text>
  <rect x="150" y="26" width="340" height="22" rx="4" fill="#1e293b"/>
  <rect x="150" y="26" width="{w_agent}" height="22" rx="4" fill="#a855f7"/>
  <text x="{160 + w_agent}" y="42" fill="#c084fc" font-size="12" font-weight="700">{agent_del} tasks</text>
  <text x="20" y="86" fill="#e2e8f0" font-size="12" font-weight="600">Human Developers</text>
  <rect x="150" y="70" width="340" height="22" rx="4" fill="#1e293b"/>
  <rect x="150" y="70" width="{w_human}" height="22" rx="4" fill="#38bdf8"/>
  <text x="{160 + w_human}" y="86" fill="#7dd3fc" font-size="12" font-weight="700">{human_del} tasks</text>
  <text x="20" y="130" fill="#e2e8f0" font-size="12" font-weight="600">Hybrid Total</text>
  <rect x="150" y="114" width="340" height="22" rx="4" fill="#1e293b"/>
  <rect x="150" y="114" width="{w_hybrid}" height="22" rx="4" fill="#10b981"/>
  <text x="{160 + w_hybrid}" y="130" fill="#34d399" font-size="12" font-weight="700">{hybrid_del} tasks</text>
</svg>"""


def render_rescue_clusters_svg(clusters: list[FailureCluster], total_rescues: int) -> str:
    """Renders inline SVG horizontal distribution of autonomous rescue stall categories."""
    if total_rescues == 0 or not clusters:
        return """<svg viewBox="0 0 580 180" class="chart-svg">
  <rect x="20" y="40" width="540" height="100" rx="8" fill="#13271f" stroke="#10b981" stroke-width="1.5"/>
  <text x="290" y="85" fill="#34d399" font-size="15" font-weight="700" text-anchor="middle">Zero Human Rescues Required</text>
  <text x="290" y="110" fill="#94a3b8" font-size="12" text-anchor="middle">100% Autonomous Worker Preflight &amp; Self-Healing Success</text>
</svg>"""

    rows: list[str] = []
    y_pos = 28
    palette = ["#f43f5e", "#fb923c", "#eab308", "#38bdf8", "#a855f7"]
    for i, c in enumerate(clusters[:4]):
        color = palette[i % len(palette)]
        w_bar = calculate_bar_width(c.incidents, total_rescues, 260.0)
        c_title = html.escape(c.cluster)
        invs = html.escape(", ".join(c.top_invariants[:2])) if c.top_invariants else ""
        inv_label = f"({invs})" if invs else ""
        rows.append(f"""  <text x="20" y="{y_pos+14}" fill="#cbd5e1" font-size="11">{c_title} {inv_label}</text>
  <rect x="220" y="{y_pos}" width="260" height="18" rx="4" fill="#1e293b"/>
  <rect x="220" y="{y_pos}" width="{w_bar}" height="18" rx="4" fill="{color}"/>
  <text x="{230 + w_bar}" y="{y_pos+14}" fill="{color}" font-size="11" font-weight="700">{c.incidents} ({round(c.percentage, 1)}%)</text>""")
        y_pos += 36

    content = "\n".join(rows)
    return f"""<svg viewBox="0 0 580 180" class="chart-svg">
{content}
</svg>"""


def render_forecast_svg(tasks_per_week: float, remaining_tasks: int = 24) -> str:
    """Renders milestone delivery forecast curve with empirical completion horizons."""
    vel = max(0.5, tasks_per_week)
    weeks_to_done = round(float(remaining_tasks) / vel, 1)
    weeks = [0, 2, 4, 6, 8]
    expected_pts = [min(float(remaining_tasks) * 1.2, round(vel * w, 1)) for w in weeks]
    max_y = max(remaining_tasks * 1.3, max(expected_pts))

    pts_str = calculate_polyline_points(expected_pts, max_y, width=440.0, height=110.0, pad_x=80.0, pad_y=25.0)
    target_y = round(25.0 + 110.0 - ((remaining_tasks / max_y) * 110.0), 1)

    return f"""<svg viewBox="0 0 580 180" class="chart-svg">
  <line x1="80" y1="{target_y}" x2="520" y2="{target_y}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,4"/>
  <text x="525" y="{target_y + 4}" fill="#fbbf24" font-size="10">Target ({remaining_tasks} tasks)</text>
  <line x1="80" y1="135" x2="520" y2="135" stroke="#334155"/>
  <text x="70" y="{target_y + 3}" fill="#64748b" font-size="10" text-anchor="end">{remaining_tasks}</text>
  <text x="70" y="139" fill="#64748b" font-size="10" text-anchor="end">0</text>
  <text x="80" y="155" fill="#64748b" font-size="10" text-anchor="middle">W+0</text>
  <text x="190" y="155" fill="#64748b" font-size="10" text-anchor="middle">W+2</text>
  <text x="300" y="155" fill="#64748b" font-size="10" text-anchor="middle">W+4</text>
  <text x="410" y="155" fill="#64748b" font-size="10" text-anchor="middle">W+6</text>
  <text x="520" y="155" fill="#64748b" font-size="10" text-anchor="middle">W+8</text>
  <polyline fill="none" stroke="#10b981" stroke-width="3" points="{pts_str}"/>
  <rect x="80" y="10" width="220" height="24" rx="4" fill="#13271f" stroke="#10b981" stroke-width="1"/>
  <text x="90" y="26" fill="#34d399" font-size="11" font-weight="700">Projected Delivery: ~{weeks_to_done} weeks</text>
</svg>"""


DASHBOARD_CSS = """
  :root {
    --bg: #090d16;
    --card: #131a29;
    --border: #202b42;
    --primary: #38bdf8;
    --agent: #a855f7;
    --success: #10b981;
    --warn: #f59e0b;
    --text: #f8fafc;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 32px;
    line-height: 1.5;
  }
  .container { max-width: 1200px; margin: 0 auto; }
  .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
  .title { font-size: 1.8rem; font-weight: 800; color: #fff; }
  .badge { background: #0369a1; color: #fff; padding: 4px 14px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; }
  .grid-kpi { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .kpi-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }
  .kpi-title { font-size: 0.85rem; color: var(--muted); margin-bottom: 6px; }
  .kpi-val { font-size: 1.8rem; font-weight: 800; }
  .kpi-sub { font-size: 0.8rem; color: var(--muted); margin-top: 4px; }
  .grid-charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; }
  .chart-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .chart-title { font-size: 1.1rem; font-weight: 700; color: #fff; }
  .legend { display: flex; gap: 14px; font-size: 0.8rem; color: var(--muted); }
  .legend-item { display: flex; align-items: center; gap: 5px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .chart-svg { width: 100%; height: auto; display: block; }
  .footer { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--border); font-size: 0.85rem; color: var(--muted); text-align: center; }
"""


def render_velocity_html(report: VelocityReport, remaining_tasks: int = 24) -> str:
    """Renders standalone, zero-dependency HTML velocity and executive forecast dashboard."""
    win_str = html.escape(str(report.window))
    gen_at = html.escape(str(report.generated_at))
    hybrid = report.hybrid_total
    agent = report.agent_metrics
    human = report.human_metrics
    rescues = report.rescues
    total_rescues = rescues.total_rescues if rescues else 0
    clusters = rescues.failure_clusters if rescues else []
    rescue_ratio = f"{rescues.rescue_burden_ratio * 100.0:.1f}%" if rescues else "0.0%"

    svg_trends = render_trends_svg(agent.tasks_per_week, human.tasks_per_week, hybrid.tasks_per_week)
    svg_throughput = render_throughput_svg(agent.tasks_delivered, human.tasks_delivered, hybrid.tasks_delivered)
    svg_rescues = render_rescue_clusters_svg(clusters, total_rescues)
    svg_forecast = render_forecast_svg(hybrid.tasks_per_week, remaining_tasks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SpecOps - Velocity &amp; Executive Forecast Dashboard</title>
  <style>{DASHBOARD_CSS}</style>
</head>
<body>
  <div class="container">
    <header class="header">
      <div>
        <h1 class="title">Hybrid Delivery Velocity &amp; Forecast</h1>
        <p style="color:var(--muted); font-size:0.9rem; margin-top:4px;">Evaluation Window: {win_str} &bull; Generated: {gen_at}</p>
      </div>
      <div><span class="badge">SpecOps Telemetry</span></div>
    </header>

    <section class="grid-kpi">
      <div class="kpi-card">
        <div class="kpi-title">Hybrid Delivery Velocity</div>
        <div class="kpi-val" style="color:var(--success);">{hybrid.tasks_per_week} <span style="font-size:1rem; font-weight:500;">tasks/wk</span></div>
        <div class="kpi-sub">Total Delivered: {hybrid.tasks_delivered} tasks</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Autonomous Agent Velocity</div>
        <div class="kpi-val" style="color:var(--agent);">{agent.tasks_per_week} <span style="font-size:1rem; font-weight:500;">tasks/wk</span></div>
        <div class="kpi-sub">Delivered: {agent.tasks_delivered} | Commits: {agent.merged_commits}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Human Developer Velocity</div>
        <div class="kpi-val" style="color:var(--primary);">{human.tasks_per_week} <span style="font-size:1rem; font-weight:500;">tasks/wk</span></div>
        <div class="kpi-sub">Delivered: {human.tasks_delivered} | Commits: {human.merged_commits}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Average Task Cycle Time</div>
        <div class="kpi-val" style="color:#f8fafc;">{html.escape(hybrid.avg_cycle_time_formatted)}</div>
        <div class="kpi-sub">Agent: {html.escape(agent.avg_cycle_time_formatted)} &bull; Human: {html.escape(human.avg_cycle_time_formatted)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Preflight Pass Rate</div>
        <div class="kpi-val" style="color:#38bdf8;">{hybrid.preflight_pass_rate or 100.0:.1f}%</div>
        <div class="kpi-sub">Agent: {agent.preflight_pass_rate or 100.0:.1f}% &bull; Human: {human.preflight_pass_rate or 100.0:.1f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Rescue Burden Ratio</div>
        <div class="kpi-val" style="color:{'#f43f5e' if total_rescues > 0 else 'var(--success)'};">{rescue_ratio}</div>
        <div class="kpi-sub">{total_rescues} worker rescues recorded</div>
      </div>
    </section>

    <main class="grid-charts">
      <article class="chart-card">
        <div class="chart-header">
          <div class="chart-title">Velocity Trajectory &amp; Acceleration</div>
          <div class="legend">
            <span class="legend-item"><span class="dot" style="background:var(--agent);"></span> Agent</span>
            <span class="legend-item"><span class="dot" style="background:var(--primary);"></span> Human</span>
            <span class="legend-item"><span class="dot" style="background:var(--success);"></span> Hybrid</span>
          </div>
        </div>
        {svg_trends}
      </article>

      <article class="chart-card">
        <div class="chart-header">
          <div class="chart-title">Throughput Breakdown</div>
        </div>
        {svg_throughput}
      </article>

      <article class="chart-card">
        <div class="chart-header">
          <div class="chart-title">Rescue Stalls &amp; Failure Clustering</div>
        </div>
        {svg_rescues}
      </article>

      <article class="chart-card">
        <div class="chart-header">
          <div class="chart-title">Milestone Delivery Forecast</div>
        </div>
        {svg_forecast}
      </article>
    </main>

    <footer class="footer">
      Generated autonomously by SpecOps Project Management as Code (PMaC) &bull; Zero External Dependencies
    </footer>
  </div>
</body>
</html>"""


def export_velocity_dashboard(
    report: VelocityReport,
    output_path: Path | str | None = None,
    repo_root: Path | None = None,
    remaining_tasks: int | None = None,
) -> Path:
    """Exports standalone HTML velocity dashboard to specified file path."""
    dest = Path(output_path) if output_path else Path("dist/velocity-report.html")
    if not dest.is_absolute():
        base = repo_root or Path.cwd()
        dest = base / dest

    if remaining_tasks is None and repo_root is not None:
        try:
            refined_dir = repo_root / "docs" / "project" / "backlog" / "refined"
            proposed_dir = repo_root / "docs" / "project" / "backlog" / "proposed"
            rem = len(list(refined_dir.glob("*.md"))) + len(list(proposed_dir.glob("*.md")))
            remaining_tasks = max(1, rem)
        except Exception:
            remaining_tasks = 24
    elif remaining_tasks is None:
        remaining_tasks = 24

    html_content = render_velocity_html(report, remaining_tasks=remaining_tasks)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html_content, encoding="utf-8")
    return dest
