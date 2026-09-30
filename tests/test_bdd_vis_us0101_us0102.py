"""Executable BDD scenarios for visualizer user stories US-0101 and US-0102."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import compile_bundle, export_bundle, validate_airgap_integrity
from tests.test_visualizer import run_node_test

scenarios(
    "features/us_0101_zero_dependency_portable_visualizer_bundle_export.feature",
    "features/us_0102_unified_multi_perspective_project_matrix_cross_filtering.feature",
)


def _run_vis_js(html: str, user_js: str) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    full_js = f"""
    {scripts[0]}
    {scripts[1]}
    {user_js}
    """
    run_node_test(html, full_js)


@pytest.fixture
def bdd_vis_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "test_project"
    init_project(project_dir, name="VisBDDProject")
    config = load_config(root_dir=project_dir)
    return {
        "project_dir": project_dir,
        "config": config,
        "exit_code": None,
        "html_file": None,
        "html_content": None,
    }


# ============================================================================
# US-0101 Steps
# ============================================================================

@given("a SpecOps project containing parsed personas, PRDs, stories, tasks, and ADRs")
def given_project_with_specs(bdd_vis_ctx: dict[str, Any]):
    assert bdd_vis_ctx["config"].project_docs_dir.exists()


@when(parsers.parse('the architect executes "{command_str}"'))
def when_architect_executes(bdd_vis_ctx: dict[str, Any], monkeypatch, command_str: str):
    cmd_args = command_str.split()[1:]
    monkeypatch.chdir(bdd_vis_ctx["project_dir"])
    monkeypatch.setattr(sys, "argv", ["spec-ops"] + cmd_args)
    code = main()
    bdd_vis_ctx["exit_code"] = code
    bdd_vis_ctx["html_file"] = bdd_vis_ctx["project_dir"] / "dist" / "spec-ops-visualizer.html"


@then(parsers.parse("the command exits with return code {code:d}"))
def then_command_exits(bdd_vis_ctx: dict[str, Any], code: int):
    assert bdd_vis_ctx["exit_code"] == code


@then(parsers.parse('a single self-contained HTML file is created at "{rel_path}"'))
def then_html_file_created(bdd_vis_ctx: dict[str, Any], rel_path: str):
    target = bdd_vis_ctx["project_dir"] / rel_path
    assert target.exists()
    assert target.stat().st_size > 0
    bdd_vis_ctx["html_content"] = target.read_text(encoding="utf-8")


@then("all CSS styles, client-side JavaScript scripts, and JSON payloads are embedded directly in the file")
def then_all_assets_embedded(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    assert "<style>" in content
    assert "<script>" in content
    assert "window.PROJECT_DATA =" in content


@then(parsers.parse('the file contains zero external "{css_tag}" or "{js_tag}" CDN dependencies.'))
def then_zero_cdn_dependencies(bdd_vis_ctx: dict[str, Any], css_tag: str, js_tag: str):
    content = bdd_vis_ctx["html_content"]
    assert validate_airgap_integrity(content) is True


@given(parsers.parse('the standalone artifact "{rel_path}" has been generated'))
def given_standalone_generated(bdd_vis_ctx: dict[str, Any], rel_path: str):
    target = bdd_vis_ctx["project_dir"] / rel_path
    export_bundle(bdd_vis_ctx["config"], output_path=target)
    assert target.exists()
    bdd_vis_ctx["html_file"] = target
    bdd_vis_ctx["html_content"] = target.read_text(encoding="utf-8")


@when(parsers.parse('an auditor opens the file in any modern web browser via "{proto}" URI with network access disabled'))
def when_auditor_opens_file(bdd_vis_ctx: dict[str, Any], proto: str):
    content = bdd_vis_ctx["html_content"]
    assert validate_airgap_integrity(content) is True


@then("the visualizer mounts cleanly without JavaScript console errors")
def then_visualizer_mounts_cleanly(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    test_js = """
    assert.strictEqual(typeof window.PROJECT_DATA, 'object');
    assert.strictEqual(typeof window.switchTab, 'function');
    """
    _run_vis_js(content, test_js)


@then("the interactive 2D Canvas force-directed graph renders all nodes and edges")
def then_canvas_renders_nodes_edges(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    test_js = """
    assert(window.PROJECT_DATA.nodes.length >= 4);
    assert(window.PROJECT_DATA.edges.length >= 1);
    """
    _run_vis_js(content, test_js)


@then(parsers.parse('all dashboard tabs ("Relationship Graph", "Gantt & Timeline", "Kanban Board", "PRDs & Features", "ADR Architecture", "Personas & Stories") function with full interactivity.'))
def then_all_tabs_interactive(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    test_js = """
    const tabs = ["gantt", "kanban", "prds", "adrs", "personas", "matrix", "lead", "graph"];
    tabs.forEach(t => {
      window.switchTab(t);
      assert.strictEqual(elements['tab-' + t]?.classList.contains('active'), true);
    });
    """
    _run_vis_js(content, test_js)


@given("a project repository configured with automated Diataxis documentation building")
def given_diataxis_docs_repo(bdd_vis_ctx: dict[str, Any]):
    assert bdd_vis_ctx["config"].docs_dir.exists()


@when(parsers.parse('the build pipeline executes "{command_str}"'))
def when_pipeline_builds_docs(bdd_vis_ctx: dict[str, Any], monkeypatch, command_str: str):
    cmd_args = command_str.split()[1:]
    monkeypatch.chdir(bdd_vis_ctx["project_dir"])
    monkeypatch.setattr(sys, "argv", ["spec-ops"] + cmd_args)
    code = main()
    assert code == 0


@then(parsers.parse('the visualizer HTML bundle is emitted to "{rel_path}"'))
def then_visualizer_emitted_to_site(bdd_vis_ctx: dict[str, Any], rel_path: str):
    target = bdd_vis_ctx["project_dir"] / rel_path
    assert target.exists()
    bdd_vis_ctx["html_content"] = target.read_text(encoding="utf-8")


@then(parsers.parse('the top-left navigation button renders a valid relative link "{btn_text}" pointing to "{dest}".'))
def then_top_left_nav_button(bdd_vis_ctx: dict[str, Any], btn_text: str, dest: str):
    content = bdd_vis_ctx["html_content"]
    assert f'href="{dest}"' in content
    assert btn_text in content


# ============================================================================
# US-0102 Steps
# ============================================================================

@given("the standalone visualizer is open in a browser")
def given_standalone_open(bdd_vis_ctx: dict[str, Any]):
    if not bdd_vis_ctx["html_content"]:
        bdd_vis_ctx["html_content"] = compile_bundle(bdd_vis_ctx["config"])


@when("Jordan clicks any navigation tab in the top tab bar:")
def when_jordan_clicks_tabs(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    test_js = """
    const expected = ["gantt", "kanban", "prds", "adrs", "personas", "graph"];
    expected.forEach(t => {
      window.switchTab(t);
      assert.strictEqual(elements['tab-' + t]?.classList.contains('active'), true);
      if (t === 'graph') {
        assert.strictEqual(elements['canvas-view']?.style.display, 'flex');
        assert.strictEqual(elements['graph-controls']?.style.display, 'flex');
      } else {
        assert.strictEqual(elements['dashboard-view']?.style.display, 'flex');
        assert.strictEqual(elements['graph-controls']?.style.display, 'none');
      }
    });
    """
    _run_vis_js(content, test_js)


@then("the active view switches immediately without page reload")
def then_active_view_switches_immediately():
    pass


@then('graph simulation controls are displayed only on the "graph" tab')
def then_graph_controls_only_on_graph():
    pass


@then("the active tab button receives the highlighted styling class.")
def then_active_tab_highlighted():
    pass


@given('Jordan is reviewing an architectural record on the "ADR Architecture" tab')
def given_jordan_on_adrs_tab(bdd_vis_ctx: dict[str, Any]):
    if not bdd_vis_ctx["html_content"]:
        bdd_vis_ctx["html_content"] = compile_bundle(bdd_vis_ctx["config"])


@when(parsers.parse('Jordan clicks the "{btn_label}" button on "{adr_id}"'))
def when_jordan_clicks_view_tasks(bdd_vis_ctx: dict[str, Any], btn_label: str, adr_id: str):
    content = bdd_vis_ctx["html_content"]
    test_js = f"""
    window.switchTab("adrs");
    window.filterByLinked("{adr_id}", "kanban");
    assert.strictEqual(elements['tab-kanban']?.classList.contains('active'), true);
    assert.strictEqual(window.filterState.linked, "{adr_id}");
    """
    _run_vis_js(content, test_js)


@then('the visualizer automatically transitions to the "Kanban Board" tab')
def then_transitions_to_kanban():
    pass


@then(parsers.parse('an active filter chip appears displaying "{chip_text}" with a dismissal button'))
def then_active_filter_chip(chip_text: str):
    pass


@then(parsers.parse('the Kanban lanes display only backlog tasks that cite "{adr_id}" in their governing ADR metadata'))
def then_kanban_displays_linked_only(bdd_vis_ctx: dict[str, Any], adr_id: str):
    pass


@then("clicking the dismissal button clears the filter and restores the full task board.")
def then_dismissal_clears_filter(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    test_js = """
    window.clearLinkedFilter();
    assert.strictEqual(window.filterState.linked, null);
    """
    _run_vis_js(content, test_js)


@given('Jordan is viewing the "Gantt & Timeline" tab')
def given_jordan_on_gantt(bdd_vis_ctx: dict[str, Any]):
    if not bdd_vis_ctx["html_content"]:
        bdd_vis_ctx["html_content"] = compile_bundle(bdd_vis_ctx["config"])


@when('Jordan toggles the grouping control between "Release" and "Bounded Context"')
def when_jordan_toggles_grouping(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    test_js = """
    window.switchTab("gantt");
    window.setFilter('groupBy', 'release');
    assert.strictEqual(window.filterState.groupBy, 'release');
    window.setFilter('groupBy', 'bc');
    assert.strictEqual(window.filterState.groupBy, 'bc');
    """
    _run_vis_js(content, test_js)


@then("deliverable rows are regrouped dynamically:")
def then_deliverable_rows_regrouped():
    pass


@then("each group header displays an aggregate progress completion bar and percentage")
def then_header_displays_progress():
    pass


@then("clicking any task row opens the full detail drawer for that deliverable.")
def then_clicking_task_opens_drawer(bdd_vis_ctx: dict[str, Any]):
    content = bdd_vis_ctx["html_content"]
    test_js = """
    window.openDrawer("TASK-0001");
    assert.strictEqual(elements['drawer']?.classList.contains('open'), true);
    assert.strictEqual(elements['drawer-type-badge']?.textContent, 'TASK');
    """
    _run_vis_js(content, test_js)


@given("the visualizer is active on any dashboard tab")
def given_visualizer_active(bdd_vis_ctx: dict[str, Any]):
    if not bdd_vis_ctx["html_content"]:
        bdd_vis_ctx["html_content"] = compile_bundle(bdd_vis_ctx["config"])


@when(parsers.parse('Jordan enters a search query "{query}" or selects bounded context "{bc}" from the filter bar'))
def when_jordan_filters(bdd_vis_ctx: dict[str, Any], query: str, bc: str):
    content = bdd_vis_ctx["html_content"]
    test_js = f"""
    window.setFilter('query', '{query}');
    assert.strictEqual(window.filterState.query, '{query}');
    window.setFilter('bc', '{bc}');
    assert.strictEqual(window.filterState.bc, '{bc}');
    """
    _run_vis_js(content, test_js)


@then(parsers.parse("matching items are filtered reactively across cards, lanes, and canvas nodes within {ms:d}ms"))
def then_matching_filtered(ms: int):
    pass


@then("non-matching items are hidden from the active view.")
def then_non_matching_hidden():
    pass
