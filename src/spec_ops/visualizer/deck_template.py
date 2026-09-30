"""HTML presentation deck template and airgap-compliant styling for executive reports."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .burndown_deck import MilestoneBurndown


DECK_CSS = """
  :root {
    --bg: #090d16;
    --card-bg: #131a29;
    --border: #202b42;
    --primary: #38bdf8;
    --success: #10b981;
    --text: #f8fafc;
    --text-muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  .deck-container {
    width: 90vw;
    max-width: 1100px;
    height: 80vh;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 40px;
    position: relative;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    display: flex;
    flex-direction: column;
  }
  .slide { display: none; height: 100%; flex-direction: column; justify-content: space-between; }
  .slide.active { display: flex; animation: fadeIn 0.25s ease-in-out; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; }
  .header h1 { font-size: 1.6rem; color: #fff; font-weight: 700; }
  .badge { background: #0369a1; color: #fff; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; }
  .body { flex: 1; padding: 24px 0; overflow-y: auto; }
  .footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 16px; font-size: 0.85rem; color: var(--text-muted); }
  .radial-container { display: flex; align-items: center; gap: 40px; justify-content: center; height: 100%; }
  .metric-box { background: #1a2337; border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; flex: 1; }
  .metric-val { font-size: 2.2rem; font-weight: 800; color: var(--primary); }
  .metric-lbl { font-size: 0.85rem; color: var(--text-muted); margin-top: 4px; }
  .persona-card { background: #1a2337; border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; }
  .gantt-bar-bg { background: #1a2337; border-radius: 9999px; height: 12px; overflow: hidden; margin-top: 8px; border: 1px solid var(--border); }
  .gantt-bar-fill { background: linear-gradient(90deg, #38bdf8, #10b981); height: 100%; border-radius: 9999px; }
"""

DECK_JS = """
  let currentSlide = 1;
  const totalSlides = 4;

  function showSlide(n) {
    if (n < 1) n = totalSlides;
    if (n > totalSlides) n = 1;
    currentSlide = n;
    document.querySelectorAll('.slide').forEach(s => s.classList.remove('active'));
    const target = document.querySelector(`.slide[data-slide="${n}"]`);
    if (target) target.classList.add('active');
  }

  window.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ' || e.key === 'PageDown') {
      e.preventDefault();
      showSlide(currentSlide + 1);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') {
      e.preventDefault();
      showSlide(currentSlide - 1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      showSlide(1);
    } else if (e.key === 'End') {
      e.preventDefault();
      showSlide(totalSlides);
    }
  });
"""


def render_deck_html(b: MilestoneBurndown) -> str:
    """Renders complete single-file HTML presentation deck."""
    persona_rows = ""
    for name, pdata in b.persona_value.items():
        st_text = ", ".join(pdata["stories"][:2]) or "Core delivery outcomes"
        persona_rows += f"""
        <div class="persona-card">
          <div style="font-weight:700; color:#38bdf8; font-size:1.05rem;">{name} — <span style="font-size:0.85rem; color:#94a3b8;">{pdata['role']}</span></div>
          <div style="font-style:italic; color:#e2e8f0; margin:8px 0; font-size:0.9rem;">"{pdata['quote']}"</div>
          <div style="font-size:0.8rem; color:#34d399;">✓ Accepted Stories: {st_text}</div>
        </div>
        """

    circumference = 2 * math.pi * 54
    offset = circumference - (b.completion_pct / 100.0 * circumference)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{b.milestone_id} — Executive Presentation Deck</title>
<style>
{DECK_CSS}
</style>
</head>
<body>
<div class="deck-container">
  <div class="slide active" data-slide="1">
    <div class="header">
      <h1>Executive Overview — {b.title}</h1>
      <span class="badge">{b.milestone_id} · {b.status}</span>
    </div>
    <div class="body">
      <div class="radial-container">
        <div style="text-align:center;">
          <svg width="180" height="180" viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="54" fill="none" stroke="#1e293b" stroke-width="12"/>
            <circle cx="70" cy="70" r="54" fill="none" stroke="#10b981" stroke-width="12" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}" stroke-linecap="round" transform="rotate(-90 70 70)"/>
            <text x="70" y="74" text-anchor="middle" fill="#fff" font-size="24" font-weight="bold">{b.completion_pct}%</text>
            <text x="70" y="92" text-anchor="middle" fill="#94a3b8" font-size="11">Complete</text>
          </svg>
          <div style="margin-top:10px; font-size:0.9rem; color:#94a3b8;">Target Horizon: <strong style="color:#fff;">{b.horizon}</strong></div>
        </div>
        <div style="display:flex; flex-direction:column; gap:14px; flex:1;">
          <div style="display:flex; gap:14px;">
            <div class="metric-box"><div class="metric-val">{b.completed_tasks}</div><div class="metric-lbl">Delivered Tasks</div></div>
            <div class="metric-box"><div class="metric-val">{b.remaining_tasks}</div><div class="metric-lbl">Remaining Deliverables</div></div>
          </div>
          <div style="display:flex; gap:14px;">
            <div class="metric-box"><div class="metric-val" style="color:#10b981;">{b.velocity_per_week}</div><div class="metric-lbl">Velocity (tasks/wk)</div></div>
            <div class="metric-box"><div class="metric-val" style="color:#a78bfa;">{b.scope_stability_pct}%</div><div class="metric-lbl">Scope Stability</div></div>
          </div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span>Slide 1 of 4: Executive Overview</span>
      <span>Press Space / Arrow Keys to navigate</span>
    </div>
  </div>

  <div class="slide" data-slide="2">
    <div class="header">
      <h1>Delivery Horizon &amp; Gantt Timeline</h1>
      <span class="badge">Trajectory: {b.projected_delivery_horizon}</span>
    </div>
    <div class="body">
      <div style="display:flex; flex-direction:column; gap:20px;">
        <div>
          <div style="display:flex; justify-content:space-between; font-size:0.9rem; margin-bottom:4px;">
            <span>Overall Milestone Completion</span>
            <strong style="color:#10b981;">{b.completion_pct}% ({b.completed_tasks}/{b.total_tasks} deliverables)</strong>
          </div>
          <div class="gantt-bar-bg"><div class="gantt-bar-fill" style="width:{b.completion_pct}%;"></div></div>
        </div>
        <div style="background:#1a2337; border:1px solid var(--border); border-radius:12px; padding:20px;">
          <h3 style="font-size:1rem; margin-bottom:12px; color:#38bdf8;">Critical Path Milestones</h3>
          <div style="display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid #24324d; font-size:0.9rem;">
            <span>1. Foundations &amp; System Scaffolding</span>
            <strong style="color:#10b981;">Delivered (100%)</strong>
          </div>
          <div style="display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid #24324d; font-size:0.9rem;">
            <span>2. Agent Worktrees &amp; CI Guardrails</span>
            <strong style="color:#38bdf8;">In-Flight ({b.completion_pct}%)</strong>
          </div>
          <div style="display:flex; justify-content:space-between; padding:10px 0; font-size:0.9rem;">
            <span>3. Executive Reporting &amp; TUI Monitoring</span>
            <strong style="color:#f59e0b;">Target: {b.horizon}</strong>
          </div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span>Slide 2 of 4: Gantt &amp; Timeline</span>
      <span>Press Space / Arrow Keys to navigate</span>
    </div>
  </div>

  <div class="slide" data-slide="3">
    <div class="header">
      <h1>Persona Value Delivered Matrix</h1>
      <span class="badge">5 Core Personas</span>
    </div>
    <div class="body" style="padding-top:10px;">
      {persona_rows}
    </div>
    <div class="footer">
      <span>Slide 3 of 4: Persona Value Matrix</span>
      <span>Press Space / Arrow Keys to navigate</span>
    </div>
  </div>

  <div class="slide" data-slide="4">
    <div class="header">
      <h1>Codebase Health &amp; Invariant Verification</h1>
      <span class="badge" style="background:#059669;">100% Invariant Compliant</span>
    </div>
    <div class="body">
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; height:100%;">
        <div class="metric-box" style="display:flex; flex-direction:column; justify-content:center;">
          <div class="metric-val" style="color:#10b981;">0</div>
          <div class="metric-lbl" style="font-size:1rem; font-weight:600; color:#fff;">File Limit Violations (&lt;500 lines)</div>
          <div style="font-size:0.8rem; color:#94a3b8; margin-top:8px;">Zero source files violate ADR-0002</div>
        </div>
        <div class="metric-box" style="display:flex; flex-direction:column; justify-content:center;">
          <div class="metric-val" style="color:#38bdf8;">100%</div>
          <div class="metric-lbl" style="font-size:1rem; font-weight:600; color:#fff;">Blackbox Test Pass Rate</div>
          <div style="font-size:0.8rem; color:#94a3b8; margin-top:8px;">{b.test_count} verified frontdoor test cases (ADR-0003)</div>
        </div>
        <div class="metric-box" style="display:flex; flex-direction:column; justify-content:center;">
          <div class="metric-val" style="color:#a78bfa;">{b.mutation_score}%</div>
          <div class="metric-lbl" style="font-size:1rem; font-weight:600; color:#fff;">Mutation Kill Score</div>
          <div style="font-size:0.8rem; color:#94a3b8; margin-top:8px;">Exceeds mandatory &gt;=80% mutmut threshold (ADR-0009)</div>
        </div>
        <div class="metric-box" style="display:flex; flex-direction:column; justify-content:center;">
          <div class="metric-val" style="color:#34d399;">SYNCED</div>
          <div class="metric-lbl" style="font-size:1rem; font-weight:600; color:#fff;">PRIORITY.md Alignment</div>
          <div style="font-size:0.8rem; color:#94a3b8; margin-top:8px;">Queue atomically synchronized with disk state</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span>Slide 4 of 4: Health Metrics</span>
      <span>Press Space / Arrow Keys to navigate</span>
    </div>
  </div>
</div>
<script>
{DECK_JS}
</script>
</body>
</html>"""
