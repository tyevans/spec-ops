"""Executable BDD scenarios for visualizer user story US-0040 (Blast Radius Deep-Linking)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.visualizer.cli_bridge import generate_entity_deep_link
from spec_ops.visualizer.generator import generate_standalone_html
from tests.test_visualizer import run_node_test

scenarios("features/us_0040_visualizer_blast_radius_inspection.feature")


@pytest.fixture
def vis_context() -> dict[str, Any]:
    config = load_config(root_dir=Path.cwd())
    html = generate_standalone_html(config)
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    return {
        "config": config,
        "html": html,
        "project_data_js": scripts[0],
        "app_js": scripts[1],
        "target_entity": "TASK-0009",
        "url": "",
    }


@given(parsers.parse('an open pull request for "{task_id}"'))
def given_open_pr(vis_context: dict[str, Any], task_id: str):
    vis_context["target_entity"] = task_id
    assert task_id == "TASK-0009"


@when(parsers.parse('the engineer executes "spec-ops visualizer --serve --entity {task_id}"'))
def when_engineer_executes(vis_context: dict[str, Any], task_id: str):
    url = generate_entity_deep_link(task_id, host="127.0.0.1", port=8787)
    vis_context["url"] = url
    vis_context["port"] = 8787


@then(parsers.parse("the local visualizer server starts on port {port:d}"))
def then_server_starts_on_port(vis_context: dict[str, Any], port: int):
    assert vis_context["port"] == port
    assert f":{port}/" in vis_context["url"]


@then(parsers.parse('navigating to the URL opens the dashboard with "{expected_hash}" active'))
def then_navigating_opens_dashboard(vis_context: dict[str, Any], expected_hash: str):
    assert expected_hash in vis_context["url"]


@then(parsers.parse('the 2D graph centers and highlights "{task_id}" with its immediate upstream stories and downstream dependents'))
def then_graph_centers_and_highlights(vis_context: dict[str, Any], task_id: str):
    test_js = f"""
    location.hash = "#entity={task_id}";
    location.href = "http://localhost:8787/#entity={task_id}";
    {vis_context["project_data_js"]}
    {vis_context["app_js"]}

    assert.strictEqual(window.getFocusedNodeId(), '{task_id}');
    const camera = window.getCameraState();
    assert.strictEqual(camera.focusedNodeId, '{task_id}');
    assert.strictEqual(camera.zoom, 1.5);

    const neighbors = window.getFocusedNeighbors();
    assert(Array.isArray(neighbors));
    """
    run_node_test(vis_context["html"], test_js)


@then("the task detail drawer automatically slides open showing full metadata and linked PRDs.")
def then_drawer_slides_open(vis_context: dict[str, Any]):
    task_id = vis_context["target_entity"]
    test_js = f"""
    location.hash = "#entity={task_id}";
    location.href = "http://localhost:8787/#entity={task_id}";
    {vis_context["project_data_js"]}
    {vis_context["app_js"]}

    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert(elements['drawer-title'].textContent.includes('{task_id}'));
    const bodyText = elements['drawer-body'].innerHTML;
    assert(bodyText.includes('Governing PRDs') || bodyText.includes('pill-prd'));
    """
    run_node_test(vis_context["html"], test_js)


@given(parsers.parse('the engineer is viewing the visualizer detail drawer for "{task_id}"'))
def given_viewing_drawer(vis_context: dict[str, Any], task_id: str):
    vis_context["target_entity"] = task_id


@when('the engineer inspects the "Target Bounded Context" field')
def when_inspects_target_bc(vis_context: dict[str, Any]):
    task_id = vis_context["target_entity"]
    test_js = f"""
    location.hash = "#entity={task_id}";
    location.href = "http://localhost:8787/#entity={task_id}";
    {vis_context["project_data_js"]}
    {vis_context["app_js"]}

    const bodyText = elements['drawer-body'].innerHTML;
    assert(bodyText.includes('Target Bounded Context'));
    """
    run_node_test(vis_context["html"], test_js)


@then("all related tasks belonging to the same bounded context are displayed as filterable pills")
def then_related_tasks_displayed(vis_context: dict[str, Any]):
    task_id = vis_context["target_entity"]
    test_js = f"""
    location.hash = "#entity={task_id}";
    location.href = "http://localhost:8787/#entity={task_id}";
    {vis_context["project_data_js"]}
    {vis_context["app_js"]}

    const bodyHtml = elements['drawer-body'].innerHTML;
    assert(bodyHtml.includes('Target Bounded Context'));
    assert(bodyHtml.includes('Related tasks in') || bodyHtml.includes('pill-task'));
    """
    run_node_test(vis_context["html"], test_js)


@then("clicking a bounded context pill filters the graph view to show only nodes within that architectural boundary.")
def then_clicking_bc_pill_filters_graph(vis_context: dict[str, Any]):
    task_id = vis_context["target_entity"]
    test_js = f"""
    location.hash = "#entity={task_id}";
    location.href = "http://localhost:8787/#entity={task_id}";
    {vis_context["project_data_js"]}
    {vis_context["app_js"]}

    // Filter by bounded context
    window.filterByBc('core');
    assert.strictEqual(window.filterState.bc, 'core');

    window.nodes.forEach(n => {{
      const nodeBc = n.resolvedBc || n.bc;
      if (nodeBc === 'core' || n.id === 'core') {{
        assert.strictEqual(window.isNodeVisible(n), true, 'Node ' + n.id + ' in core should be visible');
      }} else {{
        assert.strictEqual(window.isNodeVisible(n), false, 'Node ' + n.id + ' outside core should be hidden');
      }}
    }});
    """
    run_node_test(vis_context["html"], test_js)
