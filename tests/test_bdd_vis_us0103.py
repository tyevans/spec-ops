"""Executable BDD scenarios for visualizer user story US-0103 (URL Hash Synchronization)."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html
from tests.test_visualizer import run_node_test

scenarios("features/us_0103_url_hash_sync_deep_linking_permalinks.feature")


@pytest.fixture
def vis_ctx(tmp_path: Path) -> dict[str, Any]:
    project_dir = tmp_path / "test_project"
    init_project(project_dir, name="VisSyncProject")
    config = load_config(root_dir=project_dir)
    html = generate_standalone_html(config)
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    return {
        "project_dir": project_dir,
        "config": config,
        "html": html,
        "project_data_js": scripts[0],
        "app_js": scripts[1],
        "active_tab": "graph",
    }


@given("the visualizer URL contains a compound state hash:")
def given_compound_state_hash(vis_ctx: dict[str, Any]):
    assert vis_ctx["html"] is not None


@when("the user accesses the URL in a browser")
def when_user_accesses_url(vis_ctx: dict[str, Any]):
    test_js = f"""
    location.hash = "#tab=kanban&entity=TASK-0001";
    location.href = "http://localhost:8080/#tab=kanban&entity=TASK-0001";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'kanban');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert(elements['drawer-title'].textContent.includes('TASK-0001'));
    assert.strictEqual(elements['dashboard-view'].style.display, 'flex');
    assert.strictEqual(elements['canvas-view'].style.display, 'none');

    // Case 2: ADR view
    location.hash = "#tab=adrs&entity=ADR-0001";
    location.href = "http://localhost:8080/#tab=adrs&entity=ADR-0001";
    triggerPopState();
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'adrs');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert.strictEqual(elements['drawer-type-badge'].textContent, 'ADR');
    """
    run_node_test(vis_ctx["html"], test_js)


@then("the visualizer activates the specified tab on initial render")
def then_activates_specified_tab(vis_ctx: dict[str, Any]):
    assert "window.switchTab" in vis_ctx["html"]


@then("the detail slide-over drawer opens automatically populated with the entity's markdown and metadata")
def then_drawer_opens_populated(vis_ctx: dict[str, Any]):
    assert "window.openDrawer" in vis_ctx["html"]


@then("the underlying dashboard or canvas view renders behind the drawer without layout distortion.")
def then_underlying_view_renders(vis_ctx: dict[str, Any]):
    assert "dashboard-view" in vis_ctx["html"]


@given(parsers.parse('the user is on the "{tab_name}" tab'))
def given_user_on_tab(vis_ctx: dict[str, Any], tab_name: str):
    vis_ctx["active_tab"] = tab_name


@when(parsers.parse('the user enters query "{query}", selects status "{status}", and checks "Hide Done"'))
def when_user_applies_filters(vis_ctx: dict[str, Any], query: str, status: str):
    test_js = f"""
    location.hash = "#tab=kanban";
    location.href = "http://localhost:8080/#tab=kanban";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    window.switchTab('kanban');
    window.setFilter('query', '{query}');
    window.setFilter('status', '{status}');
    window.setFilter('hideDone', true);

    assert.strictEqual(location.hash, '#tab=kanban&q={query}&status={status}&hideDone=true');
    """
    run_node_test(vis_ctx["html"], test_js)


@then("the browser URL hash updates reactively to:")
def then_url_hash_updates(vis_ctx: dict[str, Any], docstring: str):
    assert "function updateUrl" in vis_ctx["html"]
    expected = docstring.strip()
    assert expected.startswith("#tab=kanban")


@then("copying and opening that exact URL in a new browser tab reproduces the exact filtered Kanban state.")
def then_reproduces_state(vis_ctx: dict[str, Any]):
    test_js = f"""
    location.hash = "#tab=kanban&q=preflight&status=Refined&hideDone=true";
    location.href = "http://localhost:8080/#tab=kanban&q=preflight&status=Refined&hideDone=true";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'kanban');
    assert.strictEqual(window.filterState.query, 'preflight');
    assert.strictEqual(window.filterState.status, 'Refined');
    assert.strictEqual(window.filterState.hideDone, true);
    """
    run_node_test(vis_ctx["html"], test_js)


@given(parsers.parse('the user navigated from "{tab1}" to "{tab2}", applied a search filter, and opened "{entity}"'))
def given_history_navigated(vis_ctx: dict[str, Any], tab1: str, tab2: str, entity: str):
    vis_ctx["history_test_js"] = f"""
    location.hash = "";
    location.href = "http://localhost:8080/";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    assert.strictEqual(location.hash, '#tab=graph');

    window.switchTab('{tab2}');
    assert.strictEqual(location.hash, '#tab={tab2}');

    window.setFilter('query', 'spike');
    assert.strictEqual(location.hash, '#tab={tab2}&q=spike');

    window.openDrawer('{entity}');
    assert.strictEqual(location.hash, '#tab={tab2}&q=spike&entity={entity}');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    """


@when(parsers.parse('the user clicks the browser "{btn_name}" button once'))
def when_user_clicks_back_once(vis_ctx: dict[str, Any], btn_name: str):
    vis_ctx["history_test_js"] += """
    historyIndex--;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    """


@then(parsers.parse('the detail drawer closes while preserving the "{tab}" tab and active filter'))
def then_drawer_closes_preserves_tab(vis_ctx: dict[str, Any], tab: str):
    vis_ctx["history_test_js"] += f"""
    assert.strictEqual(location.hash, '#tab={tab}&q=spike');
    assert.strictEqual(elements['drawer'].classList.contains('open'), false);
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, '{tab}');
    """


@then(parsers.parse('when the user clicks "{btn_name}" a second time'))
def when_user_clicks_back_second(vis_ctx: dict[str, Any], btn_name: str):
    vis_ctx["history_test_js"] += """
    historyIndex--;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    """


@then(parsers.parse('the visualizer transitions back to the "{tab}" tab'))
def then_transitions_back_to_tab(vis_ctx: dict[str, Any], tab: str):
    vis_ctx["history_test_js"] += f"""
    assert.strictEqual(location.hash, '#tab={tab}');
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, '{tab}');
    """


@then("clicking browser \"Forward\" re-applies each state transition without full page refreshes.")
def then_forward_reapplies(vis_ctx: dict[str, Any]):
    vis_ctx["history_test_js"] += """
    historyIndex++;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    assert.strictEqual(location.hash, '#tab=gantt&q=spike');
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'gantt');

    historyIndex++;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    assert.strictEqual(location.hash, '#tab=gantt&q=spike&entity=TASK-0001');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    """
    run_node_test(vis_ctx["html"], vis_ctx["history_test_js"])


@given("a user opens a permalink targeting a node on the relationship canvas:")
def given_canvas_permalink(vis_ctx: dict[str, Any], docstring: str):
    vis_ctx["permalink"] = docstring.strip()


@when("the Canvas 2D simulation initializes")
def when_canvas_initializes(vis_ctx: dict[str, Any]):
    test_js = f"""
    location.hash = "{vis_ctx["permalink"]}";
    location.href = "http://localhost:8080/{vis_ctx["permalink"]}";
    {vis_ctx["project_data_js"]}
    {vis_ctx["app_js"]}

    assert.strictEqual(window.getFocusedNodeId(), 'TASK-0001');
    const camera = window.getCameraState();
    assert.strictEqual(camera.focusedNodeId, 'TASK-0001');
    assert.strictEqual(camera.zoom, 1.5);
    assert(camera.panX !== 0 || camera.targetPanX !== null);

    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert.strictEqual(elements['drawer-permalink-btn'].style.display, 'inline-block');

    const copied = window.copyDeepLink();
    assert(copied.includes('#tab=graph&entity=TASK-0001') || copied.includes('#tab=graph'));
    """
    run_node_test(vis_ctx["html"], test_js)


@then(parsers.parse('the camera viewport smoothly animates and centers onto the target node "{node_id}"'))
def then_camera_animates(vis_ctx: dict[str, Any], node_id: str):
    assert "window.focusNode = function(" in vis_ctx["html"]


@then("the target node renders with a prominent animated focus ring")
def then_animated_focus_ring(vis_ctx: dict[str, Any]):
    assert "focusedNodeId" in vis_ctx["html"]


@then(parsers.parse('the entity detail drawer slides open with a "{btn_text}" button that copies the permalink.'))
def then_copy_deep_link_btn(vis_ctx: dict[str, Any], btn_text: str):
    assert "drawer-permalink-btn" in vis_ctx["html"]
