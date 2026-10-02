"""PRD Lint user interface renderer, component stories, and interactive client dashboard."""

from __future__ import annotations

import json
from typing import Any

LINT_COMPONENT_STORIES: dict[str, dict[str, Any]] = {
    "PRDLintSummaryCard": {
        "title": "PRD Quality & Lint Summary Card",
        "description": "Executive dashboard card detailing valid PRDs, falsifiable vs unfalsifiable outcomes, and total diagnostic issues.",
        "props": ["is_valid", "total_files", "valid_files", "total_errors", "total_warnings", "falsifiable_count", "unfalsifiable_count"],
        "default_state": {
            "is_valid": False,
            "total_files": 4,
            "valid_files": 2,
            "total_errors": 3,
            "total_warnings": 1,
            "falsifiable_count": 8,
            "unfalsifiable_count": 3,
        },
    },
    "PRDDiagnosticItem": {
        "title": "Diagnostic Issue Item",
        "description": "Granular diagnostic entry displaying rule code, severity badge, line number, message, and target text.",
        "props": ["rule_id", "severity", "line", "message", "suggestion"],
        "default_state": {
            "rule_id": "PRD-LINT-002",
            "severity": "error",
            "line": 42,
            "message": "Unfalsifiable subjective term 'ultra fast' detected in checkable outcome.",
            "suggestion": {
                "line": 42,
                "original_text": "- The system is ultra fast",
                "suggested_text": "- The system executes in <200ms",
                "remediation_hint": "Replace subjective adjectives with falsifiable thresholds.",
            },
        },
    },
    "LineLevelSuggestionCard": {
        "title": "Line-Level Suggestion & Rewrite Card",
        "description": "Interactive diff card previewing original vs suggested line rewrites with remediation rationale.",
        "props": ["line", "original_text", "suggested_text", "remediation_hint", "on_apply"],
        "default_state": {
            "line": 5,
            "original_text": "target_persona: unknown",
            "suggested_text": "target_persona: Taylor",
            "remediation_hint": "Select an authorized persona: Alex, Jordan, Taylor, Morgan, Sam, Casey, Riley, Devon.",
        },
    },
    "RemediationDiffModal": {
        "title": "One-Click Remediation Diff Modal",
        "description": "Modal dialog previewing automated rewrites across all diagnostics before writing to disk.",
        "props": ["file_path", "applied_count", "remediated_content", "on_confirm"],
        "default_state": {
            "file_path": "docs/project/product/idea/prd-0003.md",
            "applied_count": 2,
            "remediated_content": "---\nid: PRD-0003\ntitle: Studio\n---\n...",
        },
    },
    "LintFilterToolbar": {
        "title": "Quality Filter Toolbar",
        "description": "Toolbar providing filters by severity (All, Errors, Warnings) and rule code search.",
        "props": ["active_severity", "rule_search", "on_filter_change"],
        "default_state": {
            "active_severity": "all",
            "rule_search": "",
        },
    },
}


def render_lint_html(
    reports: list[dict[str, Any]] | None = None,
    stories: dict[str, dict[str, Any]] | None = None,
    title: str = "SpecOps PRD Quality & Lint Dashboard",
) -> str:
    """Renders a standalone zero-dependency web interface for PRD quality auditing and component stories."""
    active_reports = reports if reports is not None else []
    active_stories = stories if stories is not None else LINT_COMPONENT_STORIES

    serialized_reports = json.dumps(active_reports)
    serialized_stories = json.dumps(active_stories)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #090d16;
      --surface: #111726;
      --surface-border: #1e293b;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --success: #10b981;
      --error: #ef4444;
      --warning: #f59e0b;
      --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1rem 2rem;
      background: var(--surface);
      border-bottom: 1px solid var(--surface-border);
    }}
    .brand {{ font-size: 1.15rem; font-weight: 700; color: var(--accent); }}
    .nav-tabs {{ display: flex; gap: 0.5rem; }}
    .nav-btn {{
      background: transparent;
      border: 1px solid var(--surface-border);
      color: var(--text-muted);
      padding: 0.4rem 0.85rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.875rem;
    }}
    .nav-btn.active {{
      background: var(--accent);
      color: #000;
      border-color: var(--accent);
      font-weight: 600;
    }}
    main {{ flex: 1; padding: 2rem; max-width: 1200px; margin: 0 auto; width: 100%; }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 8px;
      padding: 1.25rem;
    }}
    .card-title {{ font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.5rem; }}
    .card-value {{ font-size: 1.75rem; font-weight: 700; }}
    .card-value.success {{ color: var(--success); }}
    .card-value.error {{ color: var(--error); }}
    .card-value.warning {{ color: var(--warning); }}
    .diagnostic-card {{
      margin-bottom: 1rem;
      border-left: 4px solid var(--surface-border);
      transition: border-color 0.2s;
    }}
    .diagnostic-card.error {{ border-left-color: var(--error); }}
    .diagnostic-card.warning {{ border-left-color: var(--warning); }}
    .diag-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
    .badge {{
      display: inline-block;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .badge.error {{ background: rgba(239, 68, 68, 0.2); color: var(--error); }}
    .badge.warning {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); }}
    .suggestion-box {{
      margin-top: 0.75rem;
      background: rgba(0, 0, 0, 0.3);
      padding: 0.75rem;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 0.85rem;
    }}
    .diff-del {{ color: var(--error); text-decoration: line-through; }}
    .diff-add {{ color: var(--success); }}
    .remediation-hint {{ margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-muted); font-style: italic; }}
    .btn {{
      background: var(--accent);
      color: #000;
      border: none;
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.85rem;
      margin-top: 0.5rem;
    }}
    .btn:hover {{ background: var(--accent-hover); }}
    .story-card {{ margin-bottom: 1.5rem; }}
    .story-props {{ margin: 0.5rem 0; font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted); }}
    .empty-state {{ text-align: center; padding: 4rem 1rem; color: var(--text-muted); }}
  </style>
</head>
<body>
  <header>
    <div class="brand">⚡ {title}</div>
    <div class="nav-tabs">
      <button class="nav-btn active" id="tab-audit" onclick="switchView('audit')">Quality Audit</button>
      <button class="nav-btn" id="tab-stories" onclick="switchView('stories')">Component Stories</button>
    </div>
  </header>

  <main>
    <section id="view-audit">
      <div class="summary-grid" id="summary-cards"></div>
      <div id="diagnostics-container"></div>
    </section>

    <section id="view-stories" style="display: none;">
      <h2 style="margin-bottom: 1rem; font-size: 1.25rem;">PRD Quality UI Component Catalog</h2>
      <div id="stories-container"></div>
    </section>
  </main>

  <script>
    const REPORTS = {serialized_reports};
    const STORIES = {serialized_stories};

    function renderSummary() {{
      const container = document.getElementById('summary-cards');
      if (!container) return;
      let totalFiles = REPORTS.length;
      let validFiles = REPORTS.filter(r => r.is_valid).length;
      let totalErrors = REPORTS.reduce((sum, r) => sum + (r.error_count || 0), 0);
      let totalWarnings = REPORTS.reduce((sum, r) => sum + (r.warning_count || 0), 0);
      let falsifiable = REPORTS.reduce((sum, r) => sum + (r.falsifiable_count || 0), 0);
      let unfalsifiable = REPORTS.reduce((sum, r) => sum + (r.unfalsifiable_count || 0), 0);

      container.innerHTML = `
        <div class="card"><div class="card-title">Audited PRDs</div><div class="card-value">${{totalFiles}}</div></div>
        <div class="card"><div class="card-title">Fully Valid PRDs</div><div class="card-value ${{validFiles === totalFiles && totalFiles > 0 ? 'success' : ''}}">${{validFiles}}/${{totalFiles}}</div></div>
        <div class="card"><div class="card-title">Errors</div><div class="card-value ${{totalErrors > 0 ? 'error' : 'success'}}">${{totalErrors}}</div></div>
        <div class="card"><div class="card-title">Warnings</div><div class="card-value ${{totalWarnings > 0 ? 'warning' : 'success'}}">${{totalWarnings}}</div></div>
        <div class="card"><div class="card-title">Falsifiable Outcomes</div><div class="card-value success">${{falsifiable}}</div></div>
        <div class="card"><div class="card-title">Subjective Outcomes</div><div class="card-value ${{unfalsifiable > 0 ? 'error' : 'success'}}">${{unfalsifiable}}</div></div>
      `;
    }}

    function renderDiagnostics() {{
      const container = document.getElementById('diagnostics-container');
      if (!container) return;

      if (!REPORTS.length) {{
        container.innerHTML = `<div class="card empty-state"><h3>All PRDs are clean and valid</h3><p>Zero quality violations or unfalsifiable outcomes detected.</p></div>`;
        return;
      }}

      let html = '';
      REPORTS.forEach(rep => {{
        if (!rep.diagnostics || !rep.diagnostics.length) {{
          html += `<div class="card diagnostic-card" style="border-left-color: var(--success);"><div class="diag-header"><strong>${{rep.file_path}}</strong><span class="badge" style="background: rgba(16,185,129,0.2); color: var(--success);">VALID</span></div><p style="color: var(--text-muted); font-size: 0.9rem;">0 errors, ${{rep.falsifiable_count || 0}} checkable outcomes verified.</p></div>`;
          return;
        }}

        rep.diagnostics.forEach(diag => {{
          const isErr = diag.severity === 'error';
          html += `
            <div class="card diagnostic-card ${{isErr ? 'error' : 'warning'}}">
              <div class="diag-header">
                <div>
                  <span class="badge ${{diag.severity}}">${{diag.rule_id}}</span>
                  <strong style="margin-left: 0.5rem; font-family: var(--font-mono); font-size: 0.85rem;">Line ${{diag.line}}: ${{rep.file_path}}</strong>
                </div>
                <span class="badge ${{diag.severity}}">${{diag.severity}}</span>
              </div>
              <p style="margin: 0.5rem 0; font-size: 0.95rem;">${{diag.message}}</p>
              ${{diag.suggestion ? `
                <div class="suggestion-box">
                  <div class="diff-del">- ${{diag.suggestion.original_text}}</div>
                  <div class="diff-add">+ ${{diag.suggestion.suggested_text}}</div>
                  <div class="remediation-hint">💡 ${{diag.suggestion.remediation_hint}}</div>
                  <button class="btn" onclick="applySuggestion('${{rep.file_path}}', ${{diag.line}})">Apply Remediation</button>
                </div>
              ` : ''}}
            </div>
          `;
        }});
      }});
      container.innerHTML = html;
    }}

    function renderStories() {{
      const container = document.getElementById('stories-container');
      if (!container) return;
      let html = '';
      for (const [key, story] of Object.entries(STORIES)) {{
        html += `
          <div class="card story-card">
            <h3 style="color: var(--accent); margin-bottom: 0.25rem;">${{story.title}} (${{key}})</h3>
            <p style="color: var(--text-muted); font-size: 0.9rem;">${{story.description}}</p>
            <div class="story-props"><strong>Props:</strong> ${{story.props.join(', ')}}</div>
            <pre style="background: rgba(0,0,0,0.4); padding: 0.75rem; border-radius: 6px; font-size: 0.8rem; overflow-x: auto; color: #a5f3fc;">${{JSON.stringify(story.default_state, null, 2)}}</pre>
          </div>
        `;
      }}
      container.innerHTML = html;
    }}

    function switchView(view) {{
      const auditSec = document.getElementById('view-audit');
      const storiesSec = document.getElementById('view-stories');
      const btnAudit = document.getElementById('tab-audit');
      const btnStories = document.getElementById('tab-stories');

      if (view === 'stories') {{
        auditSec.style.display = 'none';
        storiesSec.style.display = 'block';
        btnAudit.classList.remove('active');
        btnStories.classList.add('active');
      }} else {{
        auditSec.style.display = 'block';
        storiesSec.style.display = 'none';
        btnAudit.classList.add('active');
        btnStories.classList.remove('active');
      }}
    }}

    async function applySuggestion(filePath, line) {{
      try {{
        const resp = await fetch('/api/prd/lint/remediate', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ file_path: filePath, line: line }})
        }});
        if (resp.ok) {{
          alert('Remediation applied successfully. Refreshing dashboard.');
          window.location.reload();
        }}
      }} catch (err) {{
        console.error('Failed to apply suggestion:', err);
      }}
    }}

    document.addEventListener('DOMContentLoaded', () => {{
      renderSummary();
      renderDiagnostics();
      renderStories();
    }});
  </script>
</body>
</html>"""
