"""Standalone, self-contained HTML visualizer for Customer Journey Map and Pain Point Matrix."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .journey_map import CustomerJourneyReport


def render_journey_map_html(report: CustomerJourneyReport) -> str:
    """Renders standalone HTML customer journey map with zero external CDN dependencies."""
    coverage_pct = report.overall_coverage_percentage
    total_pts = report.total_pain_points
    addr_pts = report.addressed_pain_points
    unaddr_pts = report.unaddressed_pain_points

    persona_cards_html = []
    for p in report.personas:
        p_name = html.escape(p.persona_name)
        p_role = html.escape(p.role)
        p_id = html.escape(p.persona_id)
        p_cov = f"{p.coverage_percentage:.1f}%"

        rows = []
        for pt in p.pain_points:
            pt_idx = pt.index
            pt_desc = html.escape(pt.description)
            if pt.is_addressed:
                status_badge = '<span class="badge badge-success">Addressed</span>'
                status_class = "status-addressed"
            else:
                status_badge = '<span class="badge badge-warning">Unaddressed</span>'
                status_class = "status-unaddressed"

            stories_html = (
                " ".join(f'<span class="pill pill-story">{html.escape(s)}</span>' for s in pt.linked_stories)
                if pt.linked_stories
                else '<span class="muted">—</span>'
            )
            prds_html = (
                " ".join(f'<span class="pill pill-prd">{html.escape(prd)}</span>' for prd in pt.linked_prds)
                if pt.linked_prds
                else '<span class="muted">—</span>'
            )

            rows.append(
                f"""        <tr class="point-row {status_class}" data-persona="{p_id}" data-status="{'addressed' if pt.is_addressed else 'unaddressed'}">
          <td class="col-num">#{pt_idx}</td>
          <td class="col-desc">{pt_desc}</td>
          <td class="col-status">{status_badge}</td>
          <td class="col-stories">{stories_html}</td>
          <td class="col-prds">{prds_html}</td>
        </tr>"""
            )

        rows_rendered = "\n".join(rows) if rows else '<tr><td colspan="5" class="empty">No pain points registered.</td></tr>'

        persona_cards_html.append(
            f"""    <section class="persona-section" data-persona="{p_id}">
      <div class="persona-header">
        <div>
          <h2 class="persona-title">{p_name} <span class="persona-role">— {p_role}</span></h2>
          <div class="persona-meta">Coverage: <strong>{p_cov}</strong> ({p.addressed_pain_points}/{p.total_pain_points} pain points addressed)</div>
        </div>
        <div class="progress-container">
          <div class="progress-bar" style="width: {p_cov};"></div>
        </div>
      </div>
      <table class="matrix-table">
        <thead>
          <tr>
            <th class="col-num">#</th>
            <th class="col-desc">Pain Point Description</th>
            <th class="col-status">Status</th>
            <th class="col-stories">Linked User Stories</th>
            <th class="col-prds">Linked PRDs</th>
          </tr>
        </thead>
        <tbody>
{rows_rendered}
        </tbody>
      </table>
    </section>"""
        )

    sections_rendered = "\n".join(persona_cards_html) if persona_cards_html else '<p class="empty">No personas found.</p>'

    persona_options = "\n".join(
        f'<option value="{html.escape(p.persona_id)}">{html.escape(p.persona_name)}</option>'
        for p in report.personas
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SpecOps Customer Journey Map & Pain Point Matrix</title>
  <meta name="spec-ops:report-type" content="customer-journey-map">
  <meta name="spec-ops:journey-coverage" content="{coverage_pct:.1f}">
  <meta name="spec-ops:total-pain-points" content="{total_pts}">
  <meta name="spec-ops:addressed-pain-points" content="{addr_pts}">
  <meta name="spec-ops:unaddressed-pain-points" content="{unaddr_pts}">
  <style>
    :root {{
      --bg: #090d16; --surface: #131b2e; --surface-alt: #1a243b; --border: #23314d;
      --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8; --accent-glow: rgba(56, 189, 248, 0.15);
      --success: #10b981; --success-bg: rgba(16, 185, 129, 0.15); --success-border: #059669;
      --warning: #f59e0b; --warning-bg: rgba(245, 158, 11, 0.15); --warning-border: #d97706;
      --card-radius: 8px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg); color: var(--text); padding: 32px 24px; line-height: 1.5;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }}
    header {{ border-bottom: 1px solid var(--border); padding-bottom: 20px; }}
    h1 {{ font-size: 1.8rem; font-weight: 700; color: var(--text); margin-bottom: 8px; }}
    h1 span {{ color: var(--accent); }}
    .subtitle {{ color: var(--muted); font-size: 0.95rem; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
    .kpi-card {{
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--card-radius);
      padding: 16px 20px; display: flex; flex-direction: column; gap: 6px;
    }}
    .kpi-label {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }}
    .kpi-value {{ font-size: 1.7rem; font-weight: 700; color: var(--text); }}
    .kpi-card.highlight .kpi-value {{ color: var(--accent); }}
    .kpi-subtext {{ font-size: 0.8rem; color: var(--muted); }}
    .controls {{
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--card-radius);
      padding: 14px 20px; display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between;
    }}
    .control-group {{ display: flex; gap: 10px; align-items: center; }}
    label {{ font-size: 0.85rem; color: var(--muted); font-weight: 600; }}
    select, input {{
      background: var(--surface-alt); border: 1px solid var(--border); color: var(--text);
      padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; outline: none;
    }}
    select:focus, input:focus {{ border-color: var(--accent); }}
    .btn-filter {{
      background: var(--surface-alt); border: 1px solid var(--border); color: var(--muted);
      padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 500;
    }}
    .btn-filter.active {{ background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }}
    .persona-section {{
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--card-radius);
      padding: 20px; display: flex; flex-direction: column; gap: 16px;
    }}
    .persona-header {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }}
    .persona-title {{ font-size: 1.25rem; font-weight: 600; color: var(--text); }}
    .persona-role {{ font-size: 0.95rem; color: var(--muted); font-weight: 400; }}
    .persona-meta {{ font-size: 0.85rem; color: var(--muted); margin-top: 4px; }}
    .progress-container {{ width: 180px; height: 10px; background: var(--surface-alt); border-radius: 5px; overflow: hidden; border: 1px solid var(--border); }}
    .progress-bar {{ height: 100%; background: linear-gradient(90deg, #0ea5e9, #10b981); border-radius: 5px; }}
    .matrix-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    .matrix-table th {{
      text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border);
      color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em;
    }}
    .matrix-table td {{ padding: 12px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    .matrix-table tr:last-child td {{ border-bottom: none; }}
    .col-num {{ width: 50px; color: var(--muted); font-weight: 600; }}
    .col-desc {{ width: 45%; }}
    .col-status {{ width: 130px; }}
    .col-stories, .col-prds {{ width: 20%; }}
    .badge {{
      display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem;
      font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase;
    }}
    .badge-success {{ background: var(--success-bg); color: var(--success); border: 1px solid var(--success-border); }}
    .badge-warning {{ background: var(--warning-bg); color: var(--warning); border: 1px solid var(--warning-border); }}
    .pill {{
      display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.75rem;
      font-family: monospace; margin: 2px 3px 2px 0;
    }}
    .pill-story {{ background: rgba(56, 189, 248, 0.12); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.3); }}
    .pill-prd {{ background: rgba(168, 85, 247, 0.12); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3); }}
    .muted {{ color: var(--muted); }}
    .empty {{ text-align: center; color: var(--muted); padding: 24px; font-style: italic; }}
    footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 16px; border-top: 1px solid var(--border); padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>SpecOps <span>Customer Journey Map</span></h1>
      <p class="subtitle">Persona pain point resolution matrix and executable user story coverage auditor</p>
    </header>

    <div class="kpi-grid">
      <div class="kpi-card highlight">
        <span class="kpi-label">Journey Coverage</span>
        <span class="kpi-value">{coverage_pct:.1f}%</span>
        <span class="kpi-subtext">{addr_pts} of {total_pts} pain points resolved</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Total Personas</span>
        <span class="kpi-value">{report.total_personas}</span>
        <span class="kpi-subtext">Mapped archetypes</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Addressed Points</span>
        <span class="kpi-value" style="color: var(--success);">{addr_pts}</span>
        <span class="kpi-subtext">Covered by accepted stories</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Unaddressed Gaps</span>
        <span class="kpi-value" style="color: var(--warning);">{unaddr_pts}</span>
        <span class="kpi-subtext">Awaiting story implementation</span>
      </div>
    </div>

    <div class="controls">
      <div class="control-group">
        <label for="personaFilter">Persona:</label>
        <select id="personaFilter">
          <option value="all">All Personas</option>
{persona_options}
        </select>
      </div>
      <div class="control-group">
        <label>Status:</label>
        <button type="button" class="btn-filter active" data-status="all">All</button>
        <button type="button" class="btn-filter" data-status="addressed">Addressed</button>
        <button type="button" class="btn-filter" data-status="unaddressed">Unaddressed</button>
      </div>
      <div class="control-group">
        <input type="text" id="searchInput" placeholder="Search pain points...">
      </div>
    </div>

    <main id="matrixContainer">
{sections_rendered}
    </main>

    <footer>
      SpecOps Autonomous PMaC • Zero-Dependency Living Customer Journey Map • Governed by PRD-0003 & ADR-0013
    </footer>
  </div>

  <script>
    (function() {{
      const personaSelect = document.getElementById('personaFilter');
      const statusBtns = document.querySelectorAll('.btn-filter');
      const searchInput = document.getElementById('searchInput');
      let currentStatus = 'all';

      function applyFilters() {{
        const selectedPersona = personaSelect ? personaSelect.value : 'all';
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

        document.querySelectorAll('.persona-section').forEach(sec => {{
          const pId = sec.getAttribute('data-persona');
          const personaMatches = (selectedPersona === 'all' || selectedPersona === pId);

          let visibleRows = 0;
          sec.querySelectorAll('.point-row').forEach(row => {{
            const rowStatus = row.getAttribute('data-status');
            const rowText = row.innerText.toLowerCase();

            const statusMatches = (currentStatus === 'all' || currentStatus === rowStatus);
            const queryMatches = (!query || rowText.includes(query));

            if (personaMatches && statusMatches && queryMatches) {{
              row.style.display = '';
              visibleRows++;
            }} else {{
              row.style.display = 'none';
            }}
          }});

          sec.style.display = (personaMatches && visibleRows > 0) ? '' : 'none';
        }});
      }}

      if (personaSelect) personaSelect.addEventListener('change', applyFilters);
      if (searchInput) searchInput.addEventListener('input', applyFilters);

      statusBtns.forEach(btn => {{
        btn.addEventListener('click', () => {{
          statusBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          currentStatus = btn.getAttribute('data-status') || 'all';
          applyFilters();
        }});
      }});
    }})();
  </script>
</body>
</html>
"""
