#!/usr/bin/env python3
"""SpecOps Documentation & Project Visualizer Site Builder.

Compiles Diataxis documentation into a clean static site, embeds the standalone
2D project visualizer, exports project graph metadata, and prepares artifacts
for deployment to GitHub Pages.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"
DIST_DIR = ROOT_DIR / "dist"
SITE_DIR = ROOT_DIR / "site"


def sync_operating_manual() -> None:
    """Synchronize docs/operating-manual.md from root AGENTS.md."""
    agents_path = ROOT_DIR / "AGENTS.md"
    target_path = DOCS_DIR / "operating-manual.md"
    if not agents_path.exists():
        return
    content = agents_path.read_text(encoding="utf-8")
    content = re.sub(r"\]\(docs/", "](", content)
    target_path.write_text(content, encoding="utf-8")


def simple_markdown_to_html(md: str) -> str:
    """Lightweight markdown to semantic HTML converter for static documentation."""
    # Strip YAML frontmatter if present
    md = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, flags=re.DOTALL)

    lines = md.splitlines()
    html_lines: list[str] = []
    in_code_block = False
    in_list = False

    for line in lines:
        if line.startswith("```"):
            if in_code_block:
                html_lines.append("</code></pre>")
                in_code_block = False
            else:
                lang = line[3:].strip()
                html_lines.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            continue

        if in_code_block:
            html_lines.append(html.escape(line))
            continue

        # Headers
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
            continue

        # Horizontal rule
        if line.strip() in ("---", "***"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr />")
            continue

        # Lists
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item_text = line.strip()[2:]
            # Bold & code inline
            item_text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", item_text)
            item_text = re.sub(r"`([^`]+)`", r"<code>\1</code>", item_text)
            item_text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', item_text)
            html_lines.append(f"<li>{item_text}</li>")
            continue
        elif in_list and line.strip() == "":
            html_lines.append("</ul>")
            in_list = False

        if line.strip() == "":
            continue

        # Paragraph
        p_text = line
        p_text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p_text)
        p_text = re.sub(r"`([^`]+)`", r"<code>\1</code>", p_text)
        p_text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', p_text)
        html_lines.append(f"<p>{p_text}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code_block:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SpecOps Documentation</title>
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
      width: 280px;
      background: var(--surface);
      border-right: 1px solid var(--border);
      padding: 1.5rem;
      flex-shrink: 0;
      height: 100vh;
      position: sticky;
      top: 0;
      overflow-y: auto;
    }}
    nav.sidebar h2 {{ font-size: 1.1rem; color: #fff; margin-bottom: 0.5rem; }}
    nav.sidebar .logo {{ font-weight: 800; font-size: 1.3rem; color: var(--primary); margin-bottom: 1.5rem; display: block; text-decoration: none; }}
    nav.sidebar ul {{ list-style: none; margin-bottom: 1.5rem; }}
    nav.sidebar li {{ margin-bottom: 0.4rem; }}
    nav.sidebar a {{ color: var(--muted); text-decoration: none; font-size: 0.9rem; transition: color 0.15s; }}
    nav.sidebar a:hover, nav.sidebar a.active {{ color: var(--primary); font-weight: 600; }}
    main.content {{
      flex: 1;
      padding: 3rem 4rem;
      max-width: 900px;
    }}
    h1 {{ font-size: 2.2rem; color: #fff; margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    h2 {{ font-size: 1.5rem; color: #f1f5f9; margin-top: 2rem; margin-bottom: 0.75rem; }}
    h3 {{ font-size: 1.2rem; color: #cbd5e1; margin-top: 1.5rem; margin-bottom: 0.5rem; }}
    p {{ margin-bottom: 1rem; color: #cbd5e1; }}
    ul {{ margin-left: 1.5rem; margin-bottom: 1rem; color: #cbd5e1; }}
    li {{ margin-bottom: 0.25rem; }}
    hr {{ border: none; border-top: 1px solid var(--border); margin: 2rem 0; }}
    code {{ background: #1e293b; padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.85em; color: #38bdf8; }}
    pre {{ background: #0f172a; border: 1px solid var(--border); border-radius: 6px; padding: 1rem; overflow-x: auto; margin-bottom: 1.5rem; }}
    pre code {{ background: none; padding: 0; color: #e2e8f0; }}
    a {{ color: var(--primary); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{ display: inline-block; padding: 0.2rem 0.5rem; background: rgba(59, 130, 246, 0.15); color: var(--primary); border-radius: 4px; font-size: 0.8rem; font-weight: 600; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <nav class="sidebar">
    <a href="/spec-ops/" class="logo">⚡ SpecOps</a>
    <h2>Overview</h2>
    <ul>
      <li><a href="/spec-ops/">Home</a></li>
      <li><a href="/spec-ops/operating-manual.html">Operating Manual</a></li>
      <li><a href="/spec-ops/visualizer/">🌐 2D Graph Visualizer</a></li>
    </ul>
    <h2>Architecture Treatise</h2>
    <ul>
      <li><a href="/spec-ops/delivering-real-value.html">🔥 Delivering Real Value</a></li>
    </ul>
    <h2>Tutorials</h2>
    <ul>
      <li><a href="/spec-ops/tutorials/01-getting-started.html">Getting Started</a></li>
    </ul>
    <h2>How-To Guides</h2>
    <ul>
      <li><a href="/spec-ops/how-to/bootstrap-project.html">Bootstrap a Project</a></li>
      <li><a href="/spec-ops/how-to/check-health.html">Verify Health & Invariants</a></li>
      <li><a href="/spec-ops/how-to/decompose-prds.html">Decompose PRDs & Curate</a></li>
    </ul>
    <h2>Technical Reference</h2>
    <ul>
      <li><a href="/spec-ops/reference/cli.html">CLI Reference</a></li>
      <li><a href="/spec-ops/reference/baseline-adrs.html">Baseline ADRs</a></li>
    </ul>
    <h2>Explanation</h2>
    <ul>
      <li><a href="/spec-ops/explanation/project-management-as-code.html">Project Management as Code</a></li>
      <li><a href="/spec-ops/explanation/hard-invariants.html">Hard Invariants & Anti-Rot</a></li>
      <li><a href="/spec-ops/explanation/project-lifecycle.html">Project & Product Lifecycle</a></li>
      <li><a href="/spec-ops/explanation/delivering-integrated-value.html">Delivering Integrated Value</a></li>
    </ul>
  </nav>
  <main class="content">
    {content}
  </main>
</body>
</html>
"""


def build_docs_site() -> None:
    """Builds the complete static site in site/."""
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    sync_operating_manual()

    # 1. Compile visualizer bundle
    visualizer_bundle = DIST_DIR / "visualizer.html"
    from spec_ops.config.loader import load_config
    from spec_ops.visualizer.generator import generate_standalone_html, serialize_project_data

    config = load_config(ROOT_DIR)
    html_content = generate_standalone_html(config)
    visualizer_bundle.write_text(html_content, encoding="utf-8")

    # 2. Embed visualizer in site/visualizer/index.html
    vis_dir = SITE_DIR / "visualizer"
    vis_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(visualizer_bundle, vis_dir / "index.html")

    # 3. Export project JSON data
    payload = serialize_project_data(config)
    (SITE_DIR / "project-data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 4. Render markdown docs to HTML
    doc_sources = [
        (DOCS_DIR / "index.md", SITE_DIR / "index.html", "Welcome"),
        (DOCS_DIR / "delivering-real-value.md", SITE_DIR / "delivering-real-value.html", "Delivering Real Integrated Value"),
        (DOCS_DIR / "operating-manual.md", SITE_DIR / "operating-manual.html", "Operating Manual"),
        (DOCS_DIR / "tutorials" / "01-getting-started.md", SITE_DIR / "tutorials" / "01-getting-started.html", "Getting Started"),
        (DOCS_DIR / "how-to" / "bootstrap-project.md", SITE_DIR / "how-to" / "bootstrap-project.html", "Bootstrap Project"),
        (DOCS_DIR / "how-to" / "check-health.md", SITE_DIR / "how-to" / "check-health.html", "Verify Health"),
        (DOCS_DIR / "how-to" / "decompose-prds.md", SITE_DIR / "how-to" / "decompose-prds.html", "Decompose PRDs"),
        (DOCS_DIR / "reference" / "cli.md", SITE_DIR / "reference" / "cli.html", "CLI Reference"),
        (DOCS_DIR / "reference" / "baseline-adrs.md", SITE_DIR / "reference" / "baseline-adrs.html", "Baseline ADRs"),
        (DOCS_DIR / "explanation" / "project-management-as-code.md", SITE_DIR / "explanation" / "project-management-as-code.html", "Project Management as Code"),
        (DOCS_DIR / "explanation" / "hard-invariants.md", SITE_DIR / "explanation" / "hard-invariants.html", "Hard Invariants"),
        (DOCS_DIR / "explanation" / "project-lifecycle.md", SITE_DIR / "explanation" / "project-lifecycle.html", "Project & Product Lifecycle"),
        (DOCS_DIR / "explanation" / "delivering-integrated-value.md", SITE_DIR / "explanation" / "delivering-integrated-value.html", "Delivering Integrated Value"),
    ]

    for src, dst, title in doc_sources:
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        md_text = src.read_text(encoding="utf-8")
        body_html = simple_markdown_to_html(md_text)
        page_html = HTML_TEMPLATE.format(title=title, content=body_html)
        dst.write_text(page_html, encoding="utf-8")

    # 5. Add .nojekyll for GitHub Pages
    (SITE_DIR / ".nojekyll").touch()

    print(f"🎉 SpecOps Documentation Site generated in {SITE_DIR}")
    print(f"🌐 Visualizer available at {vis_dir / 'index.html'}")


if __name__ == "__main__":
    build_docs_site()
