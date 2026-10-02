"""Blackbox frontdoor tests for PRD drawer checkable outcomes markdown rendering."""

import re
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html
from tests.test_visualizer import run_node_test


def _extract_scripts(html: str) -> tuple[str, str]:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    return scripts[0], scripts[1]


def test_render_inline_markdown_unit(tmp_path: Path):
    """Verify inline markdown helper handles backticks, bold, italics, links, and HTML escaping."""
    init_project(tmp_path, name="TestInlineMdProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph";
    location.href = "http://localhost:8080/#tab=graph";
    {project_data_js}
    {app_js}

    assert.strictEqual(typeof window.renderInlineMarkdown, "function");

    // 1. Inline code backticks
    const codeResult = window.renderInlineMarkdown("Running `spec-ops prd lint` flags violations");
    assert(codeResult.includes("<code>spec-ops prd lint</code>"), "Backticks should be converted to <code>");
    assert(!codeResult.includes("`spec-ops"), "Raw backticks should not remain");

    // 2. Bold and italics
    const boldItalicResult = window.renderInlineMarkdown("Flags **zero** violations with *high* confidence");
    assert(boldItalicResult.includes("<strong>zero</strong>"), "Double asterisks should be converted to <strong>");
    assert(boldItalicResult.includes("<em>high</em>"), "Single asterisks should be converted to <em>");

    // 3. HTML entities escaping
    const escapeResult = window.renderInlineMarkdown("Diff in <50ms with A & B params");
    assert(escapeResult.includes("&lt;50ms"), "< should be escaped to &lt;");
    assert(escapeResult.includes("A &amp; B"), "& should be escaped to &amp;");

    // 4. Code containing brackets
    const codeWithBrackets = window.renderInlineMarkdown("Run `spec-ops rescue inspect <task-id>` now");
    assert(codeWithBrackets.includes("<code>spec-ops rescue inspect &lt;task-id&gt;</code>"));

    // 5. Strikethrough and links
    const linkResult = window.renderInlineMarkdown("See [SpecOps Docs](https://spec-ops.dev) for ~~legacy~~ details");
    assert(linkResult.includes('<a href="https://spec-ops.dev"'), "Markdown links should be converted to <a>");
    assert(linkResult.includes("<del>legacy</del>"), "Tildes should be converted to <del>");
    """
    run_node_test(html, test_js)


def test_prd_drawer_checkable_outcomes_render_inline_markdown(tmp_path: Path):
    """Verify clicking/opening a PRD drawer renders checkable outcomes bullet points with inline markdown."""
    init_project(tmp_path, name="TestPrdOutcomesDrawer")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph";
    location.href = "http://localhost:8080/#tab=graph";

    // Prepare synthetic PRD in PROJECT_DATA before app initializes
    {project_data_js}

    const mockPrd = {{
      id: "PRD-9999",
      title: "Self-Service Notification Center",
      status: "Accepted",
      target_persona: "Taylor",
      problem_statement: "Customers cannot customize digests.",
      outcomes: [
        "Running `spec-ops prd studio --open` launches the web UI",
        "Flags **zero** schema violations with *line-level* diagnostics",
        "Executes queries in <50ms latency across bounded contexts",
        "See [online guides](https://spec-ops.dev) for ~~deprecated~~ options"
      ],
      linked_stories: ["US-0001"],
      tasks: ["TASK-0001"],
      raw_markdown: "# PRD-9999\\n## Checkable Outcomes\\n- Running `spec-ops prd studio`\\n"
    }};

    window.PROJECT_DATA.prds = window.PROJECT_DATA.prds || [];
    window.PROJECT_DATA.prds.push(mockPrd);

    {app_js}

    // Render card directly
    const cardHtml = window.renderPrdCard(mockPrd);
    assert(cardHtml.includes("Checkable Outcomes"), "Card must include Checkable Outcomes section");
    assert(cardHtml.includes("<code>spec-ops prd studio --open</code>"), "Outcome code should be formatted as <code>");
    assert(cardHtml.includes("<strong>zero</strong>"), "Outcome bold text should be formatted as <strong>");
    assert(cardHtml.includes("<em>line-level</em>"), "Outcome italic text should be formatted as <em>");
    assert(cardHtml.includes("&lt;50ms"), "Outcome angle bracket should be escaped");
    assert(cardHtml.includes('<a href="https://spec-ops.dev"'), "Outcome link should be rendered as <a>");
    assert(cardHtml.includes("<del>deprecated</del>"), "Outcome strikethrough should be rendered as <del>");

    // Open drawer through public frontdoor
    window.openDrawer("PRD-9999");
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert(elements['drawer-title'].textContent.includes("PRD-9999"));
    const drawerHtml = elements['drawer-body'].innerHTML;
    assert(drawerHtml.includes("<code>spec-ops prd studio --open</code>"));
    assert(drawerHtml.includes("<strong>zero</strong>"));
    assert(drawerHtml.includes("&lt;50ms"));
    """
    run_node_test(html, test_js)
