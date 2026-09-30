"""Blackbox frontdoor tests for Relationship Graph filtering, BC clustering, and presets."""

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


def test_group_by_bc_clustering_and_hulls(tmp_path: Path):
    """Verify #tab=graph&groupBy=bc activates BC clustering, centroids, and hull rendering."""
    init_project(tmp_path, name="TestBcClusterProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph&groupBy=bc";
    location.href = "http://localhost:8080/#tab=graph&groupBy=bc";
    {project_data_js}
    {app_js}

    assert.strictEqual(window.filterState.groupBy, 'bc');
    const clusterBtn = elements['btn-cluster-bc'];
    assert(clusterBtn.classList.contains('active'));

    const centroids = window.getBcCentroids();
    assert(Object.keys(centroids).length >= 1, "Should have computed BC centroids");

    // Toggle clustering off and on
    window.toggleBcClustering();
    assert.strictEqual(window.filterState.groupBy, 'release');
    assert.strictEqual(clusterBtn.classList.contains('active'), false);
    assert(location.hash.includes('tab=graph'));
    assert(!location.hash.includes('groupBy=bc'));

    window.toggleBcClustering();
    assert.strictEqual(window.filterState.groupBy, 'bc');
    assert(clusterBtn.classList.contains('active'));
    assert(location.hash.includes('groupBy=bc'));
    """
    run_node_test(html, test_js)


def test_graph_bounded_context_filtering(tmp_path: Path):
    """Verify filtering the canvas by a specific Bounded Context highlights matching nodes."""
    init_project(tmp_path, name="TestBcFilterProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph&bc=core";
    location.href = "http://localhost:8080/#tab=graph&bc=core";
    {project_data_js}
    {app_js}

    assert.strictEqual(window.filterState.bc, 'core');
    const bcSelect = elements['graph-bc-select'];
    assert.strictEqual(bcSelect.value, 'core');

    // Verify nodes in 'core' are visible while other BCs are dimmed
    window.nodes.forEach(n => {{
      const nodeBc = n.resolvedBc || n.bc;
      if (nodeBc === 'core' || n.id === 'core') {{
        assert.strictEqual(window.isNodeVisible(n), true, `Node ${{n.id}} in core should be visible`);
      }}
    }});

    // Reset BC filter
    window.setFilter('bc', 'all');
    assert.strictEqual(window.filterState.bc, 'all');
    assert.strictEqual(bcSelect.value, 'all');
    """
    run_node_test(html, test_js)


def test_graph_task_status_and_hide_done_filter(tmp_path: Path):
    """Verify task status filtering and Hide Done toggle on the Relationship Graph canvas."""
    init_project(tmp_path, name="TestStatusFilterProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph&status=Refined&hideDone=true";
    location.href = "http://localhost:8080/#tab=graph&status=Refined&hideDone=true";
    {project_data_js}
    {app_js}

    assert.strictEqual(window.filterState.status, 'Refined');
    assert.strictEqual(window.filterState.hideDone, true);
    assert(elements['graph-hide-done-btn'].classList.contains('active'));

    const taskNodes = window.nodes.filter(n => n.type === 'task');
    taskNodes.forEach(t => {{
      if (t.status === 'Complete') {{
        assert.strictEqual(window.isNodeVisible(t), false, `Complete task ${{t.id}} should be hidden`);
      }} else if (t.status === 'Refined') {{
        assert.strictEqual(window.isNodeVisible(t), true, `Refined task ${{t.id}} should be visible`);
      }} else {{
        assert.strictEqual(window.isNodeVisible(t), false, `Proposed task ${{t.id}} should be filtered`);
      }}
    }});

    // Toggle Hide Done off
    window.toggleHideDone();
    assert.strictEqual(window.filterState.hideDone, false);
    assert.strictEqual(elements['graph-hide-done-btn'].classList.contains('active'), false);
    """
    run_node_test(html, test_js)


def test_entity_type_pills_toggling(tmp_path: Path):
    """Verify toggling individual entity type pills shows/hides those entity categories."""
    init_project(tmp_path, name="TestTypeToggleProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph";
    location.href = "http://localhost:8080/#tab=graph";
    {project_data_js}
    {app_js}

    const state = window.getGraphFilterState();
    assert.strictEqual(state.types.has('task'), true);
    assert.strictEqual(state.types.has('story'), true);

    // Toggle off tasks
    window.toggleTypeFilter('task');
    assert.strictEqual(state.types.has('task'), false);
    assert.strictEqual(elements['pill-toggle-task'].classList.contains('active'), false);

    window.nodes.filter(n => n.type === 'task').forEach(t => {{
      assert.strictEqual(window.isNodeVisible(t), false, "Tasks should be hidden when toggled off");
    }});
    window.nodes.filter(n => n.type === 'story').forEach(s => {{
      assert.strictEqual(window.isNodeVisible(s), true, "Stories should remain visible");
    }});

    // Toggle tasks back on
    window.toggleTypeFilter('task');
    assert.strictEqual(state.types.has('task'), true);
    assert.strictEqual(elements['pill-toggle-task'].classList.contains('active'), true);
    """
    run_node_test(html, test_js)


def test_perspective_presets_switching(tmp_path: Path):
    """Verify applying perspective presets adjusts layout, clustering, and filters in one click."""
    init_project(tmp_path, name="TestPresetsProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph";
    location.href = "http://localhost:8080/#tab=graph";
    {project_data_js}
    {app_js}

    // 1. Apply Bounded Context Clusters preset
    window.applyPerspectivePreset('bc');
    assert.strictEqual(window.filterState.groupBy, 'bc');
    assert(elements['btn-cluster-bc'].classList.contains('active'));

    // 2. Apply Active Delivery preset
    window.applyPerspectivePreset('delivery');
    assert.strictEqual(window.filterState.hideDone, true);
    const state = window.getGraphFilterState();
    assert.strictEqual(state.types.has('task'), true);
    assert.strictEqual(state.types.has('adr'), false, "ADRs should be excluded from delivery preset");

    // 3. Apply Architecture & ADRs preset
    window.applyPerspectivePreset('architecture');
    assert.strictEqual(state.types.has('adr'), true);
    assert.strictEqual(state.types.has('prd'), true);
    assert.strictEqual(state.types.has('task'), false, "Tasks should be excluded from architecture preset");

    // 4. Reset All Filters
    window.resetAllFilters();
    assert.strictEqual(state.types.size, 6);
    assert.strictEqual(window.filterState.hideDone, false);
    assert.strictEqual(window.filterState.bc, 'all');
    assert.strictEqual(window.filterState.groupBy, 'release');
    """
    run_node_test(html, test_js)


def test_drawer_filter_by_bc_action(tmp_path: Path):
    """Verify window.filterByBc in drawer switches to graph and filters by target BC."""
    init_project(tmp_path, name="TestDrawerBcActionProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=kanban";
    location.href = "http://localhost:8080/#tab=kanban";
    {project_data_js}
    {app_js}

    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'kanban');

    // Trigger filterByBc from drawer
    window.filterByBc('core');
    assert.strictEqual(window.filterState.bc, 'core');
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'graph');
    assert(location.hash.includes('tab=graph'));
    assert(location.hash.includes('bc=core'));
    """
    run_node_test(html, test_js)
