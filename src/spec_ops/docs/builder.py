"""Diataxis documentation compiler and static site builder for SpecOps."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from .templates import DOCS_HTML_TEMPLATE


@dataclass
class DocPage:
    title: str
    rel_path: Path
    category: str
    html_rel_path: Path
    content_md: str


def sync_operating_manual(root_dir: Path, docs_dir: Path) -> Path | None:
    """Synchronize docs/operating-manual.md from root AGENTS.md."""
    agents_path = root_dir / "AGENTS.md"
    target_path = docs_dir / "operating-manual.md"
    if not agents_path.exists():
        return None
    content = agents_path.read_text(encoding="utf-8")
    content = re.sub(r"\]\(docs/", "](", content)
    docs_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return target_path


def _extract_title(md_text: str, default: str) -> str:
    """Extracts first H1 title from markdown text or fallback to default."""
    clean = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md_text, flags=re.DOTALL)
    for line in clean.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return default.replace("-", " ").replace("_", " ").title()


def _format_inline(text: str) -> str:
    """Formats inline markdown elements (bold, italic, code, links)."""
    text = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    def _link_sub(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("mailto:"):
            url = re.sub(r"\.md(#.*)?$", r".html\1", url)
        return f'<a href="{url}">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_sub, text)


def simple_markdown_to_html(md: str) -> str:
    """Lightweight markdown to semantic HTML converter for static documentation."""
    md = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, flags=re.DOTALL)

    lines = md.splitlines()
    html_lines: list[str] = []
    in_code_block = False
    in_ul = False
    in_ol = False
    in_table = False
    in_blockquote = False

    def close_blocks() -> None:
        nonlocal in_ul, in_ol, in_table, in_blockquote
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False
        if in_table:
            html_lines.append("</tbody></table></div>")
            in_table = False
        if in_blockquote:
            html_lines.append("</blockquote>")
            in_blockquote = False

    for line in lines:
        if line.startswith("```"):
            close_blocks()
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

        stripped = line.strip()

        if stripped.startswith(">"):
            if not in_blockquote:
                close_blocks()
                html_lines.append("<blockquote>")
                in_blockquote = True
            quote_text = stripped[1:].strip()
            html_lines.append(f"<p>{_format_inline(quote_text)}</p>")
            continue
        elif in_blockquote:
            html_lines.append("</blockquote>")
            in_blockquote = False

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= {"-", ":", " "} for c in cells):
                continue
            if not in_table:
                close_blocks()
                html_lines.append('<div class="table-wrapper"><table><thead><tr>')
                for c in cells:
                    html_lines.append(f"<th>{_format_inline(c)}</th>")
                html_lines.append("</tr></thead><tbody>")
                in_table = True
            else:
                html_lines.append("<tr>")
                for c in cells:
                    html_lines.append(f"<td>{_format_inline(c)}</td>")
                html_lines.append("</tr>")
            continue
        elif in_table:
            html_lines.append("</tbody></table></div>")
            in_table = False

        if line.startswith("# "):
            close_blocks()
            html_lines.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            close_blocks()
            html_lines.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            close_blocks()
            html_lines.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
            continue
        if line.startswith("#### "):
            close_blocks()
            html_lines.append(f"<h4>{html.escape(line[5:].strip())}</h4>")
            continue

        if stripped in ("---", "***"):
            close_blocks()
            html_lines.append("<hr />")
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                close_blocks()
                html_lines.append("<ul>")
                in_ul = True
            item_text = _format_inline(stripped[2:])
            html_lines.append(f"<li>{item_text}</li>")
            continue

        m_ol = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m_ol:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                close_blocks()
                html_lines.append("<ol>")
                in_ol = True
            item_text = _format_inline(m_ol.group(2))
            html_lines.append(f"<li>{item_text}</li>")
            continue

        if stripped == "":
            close_blocks()
            continue

        close_blocks()
        html_lines.append(f"<p>{_format_inline(line)}</p>")

    close_blocks()
    if in_code_block:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines)


def _generate_sidebar(pages: list[DocPage], current_html: str, base_url: str) -> str:
    """Generates structured Diataxis sidebar navigation HTML."""
    categories: dict[str, list[DocPage]] = {
        "overview": [],
        "tutorials": [],
        "how-to": [],
        "reference": [],
        "explanation": [],
        "other": [],
    }

    for p in pages:
        cat = p.category
        if cat in categories:
            categories[cat].append(p)
        else:
            categories["other"].append(p)

    sections: list[str] = []

    def make_section(title: str, items: list[DocPage], extra_links: list[tuple[str, str]] | None = None) -> None:
        if not items and not extra_links:
            return
        lines = [f"<h2>{title}</h2><ul>"]
        if extra_links:
            for l_title, l_url in extra_links:
                lines.append(f'<li><a href="{l_url}">{l_title}</a></li>')
        for it in items:
            href = f"{base_url.rstrip('/')}/{it.html_rel_path.as_posix()}"
            active = ' class="active"' if it.html_rel_path.as_posix() == current_html else ""
            lines.append(f'<li><a href="{href}"{active}>{it.title}</a></li>')
        lines.append("</ul>")
        sections.append("\n".join(lines))

    overview_links = [
        ("Home", f"{base_url.rstrip('/')}/index.html"),
        ("🌐 2D Graph Visualizer", f"{base_url.rstrip('/')}/visualizer/"),
    ]
    make_section("Overview", categories["overview"], overview_links)
    make_section("Tutorials", categories["tutorials"])
    make_section("How-To Guides", categories["how-to"])
    make_section("Reference", categories["reference"])
    make_section("Explanation", categories["explanation"])
    make_section("Additional Guides", categories["other"])

    return "\n".join(sections)


_DEFAULT_ROADMAP_EXPORTER: Any = None
_DEFAULT_VISUALIZER_GENERATOR: Any = None
_DEFAULT_PROJECT_SERIALIZER: Any = None


def register_default_roadmap_exporter(exporter: Any) -> None:
    """Registers an external roadmap exporter callback (e.g. from prd or app context)."""
    global _DEFAULT_ROADMAP_EXPORTER
    _DEFAULT_ROADMAP_EXPORTER = exporter


def register_default_visualizer_generator(generator: Any) -> None:
    """Registers an external visualizer generator callback."""
    global _DEFAULT_VISUALIZER_GENERATOR
    _DEFAULT_VISUALIZER_GENERATOR = generator


def register_default_project_serializer(serializer: Any) -> None:
    """Registers an external project data serializer callback."""
    global _DEFAULT_PROJECT_SERIALIZER
    _DEFAULT_PROJECT_SERIALIZER = serializer


def build_docs_site(
    config: SpecOpsConfig,
    out_dir: Path | None = None,
    base_url: str = "/spec-ops/",
    include_visualizer: bool = True,
    roadmap_exporter: Any = None,
    visualizer_generator: Any = None,
    project_serializer: Any = None,
) -> Path:
    """Compiles Diataxis documentation into a clean static site with embedded visualizer."""
    root_dir = config.root_dir
    docs_dir = config.docs_dir
    site_dir = out_dir or (root_dir / "site")
    dist_dir = root_dir / "dist"

    site_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 1. Sync AGENTS.md -> docs/operating-manual.md
    sync_operating_manual(root_dir, docs_dir)

    # 2. Compile standalone visualizer bundle
    if include_visualizer:
        gen = visualizer_generator or _DEFAULT_VISUALIZER_GENERATOR
        if gen is None:
            try:
                import importlib
                viz_gen_mod = importlib.import_module("spec_ops.visualizer.generator")
                gen = getattr(viz_gen_mod, "generate_standalone_html", None)
            except Exception:
                gen = None

        if gen:
            visualizer_html = gen(config, back_link="../index.html")
            (dist_dir / "visualizer.html").write_text(visualizer_html, encoding="utf-8")

            vis_dir = site_dir / "visualizer"
            vis_dir.mkdir(parents=True, exist_ok=True)
            (vis_dir / "index.html").write_text(visualizer_html, encoding="utf-8")

    # 3. Export project JSON data and roadmap SVG artifacts
    serializer = project_serializer or _DEFAULT_PROJECT_SERIALIZER
    if serializer is None:
        try:
            import importlib
            viz_gen_mod = importlib.import_module("spec_ops.visualizer.generator")
            serializer = getattr(viz_gen_mod, "serialize_project_data", None)
        except Exception:
            serializer = None

    if serializer:
        payload = serializer(config)
        (site_dir / "project-data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    exporter = roadmap_exporter or _DEFAULT_ROADMAP_EXPORTER
    if exporter is None:
        try:
            import importlib
            prd_exporter_mod = importlib.import_module("spec_ops.prd.exporter")
            exporter = getattr(prd_exporter_mod, "export_roadmap", None)
        except Exception:
            exporter = None

    if exporter:
        assets_dir = site_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        try:
            exporter(config, format="svg", output_path=assets_dir / "roadmap.svg")
        except TypeError:
            exporter(config, output_path=assets_dir / "roadmap.svg")

    # 4. Discover all Markdown docs in docs/ (excluding docs/project/)
    pages: list[DocPage] = []
    if docs_dir.exists():
        for md_path in sorted(docs_dir.rglob("*.md")):
            if "project" in md_path.relative_to(docs_dir).parts:
                continue

            rel_to_docs = md_path.relative_to(docs_dir)
            cat = "other"
            if len(rel_to_docs.parts) > 1:
                top_part = rel_to_docs.parts[0].lower()
                if top_part in ("tutorials", "how-to", "reference", "explanation"):
                    cat = top_part
            elif rel_to_docs.name in ("index.md", "operating-manual.md"):
                cat = "overview"

            content = md_path.read_text(encoding="utf-8")
            title = _extract_title(content, md_path.stem)
            html_rel = rel_to_docs.with_suffix(".html")
            pages.append(DocPage(title=title, rel_path=rel_to_docs, category=cat, html_rel_path=html_rel, content_md=content))

    # 5. Render HTML pages with Diataxis navigation
    search_index: list[dict[str, Any]] = []

    for page in pages:
        target_html_path = site_dir / page.html_rel_path
        target_html_path.parent.mkdir(parents=True, exist_ok=True)

        body_html = simple_markdown_to_html(page.content_md)
        sidebar_html = _generate_sidebar(pages, page.html_rel_path.as_posix(), base_url)
        full_html = DOCS_HTML_TEMPLATE.format(
            title=page.title,
            project_name=config.project.name,
            base_url=base_url,
            sidebar_nav=sidebar_html,
            content=body_html,
        )
        target_html_path.write_text(full_html, encoding="utf-8")

        plain_text = re.sub(r"<[^>]+>", " ", body_html)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        search_index.append({
            "title": page.title,
            "category": page.category,
            "url": f"{base_url.rstrip('/')}/{page.html_rel_path.as_posix()}",
            "snippet": plain_text[:200] + "..." if len(plain_text) > 200 else plain_text,
        })

    # 6. Write search index and .nojekyll
    (site_dir / "search-index.json").write_text(json.dumps(search_index, indent=2), encoding="utf-8")
    (site_dir / ".nojekyll").touch()

    return site_dir
