"""HTML templates and styles for SpecOps Diataxis documentation."""

from __future__ import annotations

DOCS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — {project_name} Documentation</title>
  <style>
    :root {{
      --bg: #090d16;
      --surface: #131a29;
      --border: #1e293b;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --primary: #3b82f6;
      --accent: #10b981;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      display: flex;
      min-height: 100vh;
    }}
    nav.sidebar {{
      width: 290px;
      background: var(--surface);
      border-right: 1px solid var(--border);
      padding: 1.5rem;
      flex-shrink: 0;
      height: 100vh;
      position: sticky;
      top: 0;
      overflow-y: auto;
    }}
    nav.sidebar h2 {{ font-size: 0.95rem; color: #fff; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 1.25rem; margin-bottom: 0.5rem; }}
    nav.sidebar h2:first-of-type {{ margin-top: 0; }}
    nav.sidebar .logo {{ font-weight: 800; font-size: 1.25rem; color: var(--primary); margin-bottom: 1.5rem; display: block; text-decoration: none; }}
    nav.sidebar ul {{ list-style: none; margin-bottom: 1rem; }}
    nav.sidebar li {{ margin-bottom: 0.35rem; }}
    nav.sidebar a {{ color: var(--muted); text-decoration: none; font-size: 0.88rem; transition: color 0.15s; }}
    nav.sidebar a:hover, nav.sidebar a.active {{ color: var(--primary); font-weight: 600; }}
    main.content {{
      flex: 1;
      padding: 3rem 4rem;
      max-width: 960px;
    }}
    h1 {{ font-size: 2.2rem; color: #fff; margin-bottom: 1.2rem; border-bottom: 1px solid var(--border); padding-bottom: 0.6rem; }}
    h2 {{ font-size: 1.5rem; color: #f1f5f9; margin-top: 2rem; margin-bottom: 0.75rem; }}
    h3 {{ font-size: 1.2rem; color: #cbd5e1; margin-top: 1.5rem; margin-bottom: 0.5rem; }}
    p {{ margin-bottom: 1rem; color: #cbd5e1; }}
    ul, ol {{ margin-left: 1.75rem; margin-bottom: 1.25rem; color: #cbd5e1; }}
    li {{ margin-bottom: 0.35rem; }}
    hr {{ border: none; border-top: 1px solid var(--border); margin: 2rem 0; }}
    blockquote {{ border-left: 4px solid var(--primary); background: #111827; padding: 0.75rem 1.25rem; margin-bottom: 1.25rem; border-radius: 0 6px 6px 0; color: #94a3b8; }}
    blockquote p {{ margin-bottom: 0; }}
    code {{ background: #1e293b; padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.85em; color: #38bdf8; }}
    pre {{ background: #0f172a; border: 1px solid var(--border); border-radius: 6px; padding: 1rem; overflow-x: auto; margin-bottom: 1.5rem; }}
    pre code {{ background: none; padding: 0; color: #e2e8f0; }}
    a {{ color: var(--primary); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .table-wrapper {{ overflow-x: auto; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }}
    th, td {{ padding: 0.75rem 1rem; border: 1px solid var(--border); }}
    th {{ background: #1e293b; color: #f8fafc; font-weight: 600; }}
    tr:nth-child(even) {{ background: rgba(255, 255, 255, 0.02); }}
    header.doc-header {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      margin-bottom: 1.5rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border);
    }}
    .visualizer-header-link {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: rgba(59, 130, 246, 0.1);
      color: var(--primary);
      border: 1px solid rgba(59, 130, 246, 0.3);
      padding: 0.35rem 0.75rem;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 500;
      text-decoration: none;
      transition: all 0.15s;
    }}
    .visualizer-header-link:hover {{
      background: var(--primary);
      color: #fff;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <nav class="sidebar">
    <a href="{base_url}" class="logo">⚡ {project_name}</a>
    {sidebar_nav}
  </nav>
  <main class="content">
    <header class="doc-header">
      <nav class="header-nav">
        <a href="{base_url}visualizer/" class="visualizer-header-link">🌐 2D Graph Visualizer</a>
      </nav>
    </header>
    {content}
  </main>
</body>
</html>
"""
