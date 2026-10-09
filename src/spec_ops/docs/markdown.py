"""Lightweight markdown to semantic HTML converter for Diataxis documentation."""

from __future__ import annotations

import html
import re


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
    """Lightweight markdown to semantic HTML converter for static documentation.

    Properly buffers consecutive paragraph text and list continuation lines to avoid
    fragmenting text into isolated paragraphs or split lists.
    """
    md = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, flags=re.DOTALL)

    lines = md.splitlines()
    html_lines: list[str] = []
    in_code_block = False
    in_mermaid = False
    in_ul = False
    in_ol = False
    in_table = False
    in_blockquote = False

    current_p: list[str] = []
    current_li: list[str] = []
    current_quote: list[str] = []

    def flush_p() -> None:
        nonlocal current_p
        if current_p:
            html_lines.append(f"<p>{_format_inline(' '.join(current_p))}</p>")
            current_p = []

    def flush_li() -> None:
        nonlocal current_li
        if current_li:
            html_lines.append(f"<li>{_format_inline(' '.join(current_li))}</li>")
            current_li = []

    def flush_quote() -> None:
        nonlocal current_quote
        if current_quote:
            html_lines.append(f"<p>{_format_inline(' '.join(current_quote))}</p>")
            current_quote = []

    def close_blocks() -> None:
        nonlocal in_ul, in_ol, in_table, in_blockquote
        flush_p()
        flush_li()
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
            flush_quote()
            html_lines.append("</blockquote>")
            in_blockquote = False

    for i, line in enumerate(lines):
        if line.startswith("```"):
            close_blocks()
            if in_code_block:
                html_lines.append("</pre>" if in_mermaid else "</code></pre>")
                in_code_block = False
                in_mermaid = False
            else:
                lang = line[3:].strip().lower()
                in_mermaid = lang == "mermaid"
                html_lines.append('<pre class="mermaid">' if in_mermaid else f'<pre><code class="language-{lang}">')
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
            if quote_text == "":
                flush_quote()
            else:
                current_quote.append(quote_text)
            continue
        elif in_blockquote:
            flush_quote()
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

        m_heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m_heading:
            close_blocks()
            level = len(m_heading.group(1))
            html_lines.append(f"<h{level}>{html.escape(m_heading.group(2).strip())}</h{level}>")
            continue

        if stripped in ("---", "***"):
            close_blocks()
            html_lines.append("<hr />")
            continue

        if stripped.startswith(("- ", "* ")):
            flush_p()
            if in_ol:
                flush_li()
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                close_blocks()
                html_lines.append("<ul>")
                in_ul = True
            else:
                flush_li()
            current_li = [stripped[2:].strip()]
            continue

        m_ol = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m_ol:
            flush_p()
            if in_ul:
                flush_li()
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                close_blocks()
                html_lines.append("<ol>")
                in_ol = True
            else:
                flush_li()
            current_li = [m_ol.group(2).strip()]
            continue

        if (in_ul or in_ol) and current_li and (line.startswith("  ") or line.startswith("\t")):
            current_li.append(stripped)
            continue

        if stripped.startswith("<!--") and stripped.endswith("-->"):
            close_blocks()
            html_lines.append(stripped)
            continue

        if stripped == "":
            flush_p()
            if in_ul or in_ol:
                next_item = None
                for j in range(i + 1, len(lines)):
                    s = lines[j].strip()
                    if s:
                        next_item = s
                        break
                is_next_ul = next_item and (next_item.startswith("- ") or next_item.startswith("* "))
                is_next_ol = next_item and bool(re.match(r"^\d+\.\s+", next_item))
                if (in_ul and is_next_ul) or (in_ol and is_next_ol):
                    flush_li()
                else:
                    close_blocks()
            else:
                close_blocks()
            continue

        if in_ul or in_ol:
            close_blocks()

        current_p.append(stripped)

    close_blocks()
    if in_code_block:
        html_lines.append("</pre>" if in_mermaid else "</code></pre>")

    return "\n".join(html_lines)
