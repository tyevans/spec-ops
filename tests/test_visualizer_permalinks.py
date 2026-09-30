"""Blackbox frontdoor tests for entity permalinks, focal targeting, and shareable URL actions."""

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


def test_entity_permalink_resolution_auto_opens_drawer(tmp_path: Path):
    """Verify navigating to #entity=<ID> automatically opens drawer and focuses entity."""
    init_project(tmp_path, name="TestPermalinkProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#entity=TASK-0001";
    location.href = "http://localhost:8080/#entity=TASK-0001";
    {project_data_js}
    {app_js}

    // Verify drawer opened automatically on load
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert(elements['drawer-title'].textContent.includes('TASK-0001'));
    assert.strictEqual(elements['drawer-type-badge'].textContent, 'TASK');
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'graph');

    // Verify 2D Canvas camera focal centering
    assert.strictEqual(window.getFocusedNodeId(), 'TASK-0001');
    const camera = window.getCameraState();
    assert.strictEqual(camera.focusedNodeId, 'TASK-0001');
    assert(camera.panX !== 0 || camera.targetPanX !== null);

    // Verify opening ADR entity via permalink
    window.openDrawer('ADR-0001');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert.strictEqual(elements['drawer-type-badge'].textContent, 'ADR');
    assert.strictEqual(window.getFocusedNodeId(), 'ADR-0001');
    """
    run_node_test(html, test_js)


def test_drawer_open_close_synchronizes_url_hash(tmp_path: Path):
    """Verify opening and closing drawers synchronizes the entity parameter in URL hash."""
    init_project(tmp_path, name="TestSyncDrawerProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph";
    location.href = "http://localhost:8080/#tab=graph";
    {project_data_js}
    {app_js}

    assert.strictEqual(location.hash, '#tab=graph');
    assert.strictEqual(elements['drawer'].classList.contains('open'), false);

    // Open drawer -> adds entity to URL hash
    window.openDrawer('TASK-0001');
    assert.strictEqual(location.hash, '#tab=graph&entity=TASK-0001');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert.strictEqual(window.getFocusedNodeId(), 'TASK-0001');

    // Close drawer -> removes entity from URL hash and clears focal node
    window.closeDrawer();
    assert.strictEqual(location.hash, '#tab=graph');
    assert.strictEqual(elements['drawer'].classList.contains('open'), false);
    assert.strictEqual(window.getFocusedNodeId(), null);
    """
    run_node_test(html, test_js)


def test_drawer_copy_deep_link_action_and_feedback(tmp_path: Path):
    """Verify Copy Deep Link button in detail drawer header copies URL and shows visual feedback."""
    init_project(tmp_path, name="TestCopyLinkProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=graph&entity=TASK-0001";
    location.href = "http://localhost:8080/#tab=graph&entity=TASK-0001";
    {project_data_js}
    {app_js}

    const permalinkBtn = elements['drawer-permalink-btn'];
    permalinkBtn.textContent = "🔗 Copy Deep Link";

    // Copy deep link from drawer
    const copiedUrl = window.copyDeepLink();
    assert.strictEqual(copiedUrl, 'http://localhost:8080/#tab=graph&entity=TASK-0001');
    assert.strictEqual(clipboardContent, 'http://localhost:8080/#tab=graph&entity=TASK-0001');
    assert.strictEqual(permalinkBtn.textContent, '✓ Copied URL!');
    """
    run_node_test(html, test_js)


def test_kanban_and_adr_context_actions_copy_link(tmp_path: Path):
    """Verify Copy Link context action buttons on Kanban cards and ADR lists."""
    init_project(tmp_path, name="TestContextActionsProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "";
    location.href = "http://localhost:8080/";
    {project_data_js}
    {app_js}

    // 1. Switch to Kanban view
    window.switchTab('kanban');
    const dashboardHtml = elements['dashboard-content'].innerHTML;
    assert(dashboardHtml.includes('copy-link-btn'));
    assert(dashboardHtml.includes('window.copyDeepLink'));

    const mockKanbanBtn = makeElement('kanban-copy-btn');
    mockKanbanBtn.textContent = '🔗 Copy Link';
    let stopped = false;
    const mockEvent = {{ stopPropagation: () => {{ stopped = true; }} }};

    window.copyDeepLink('TASK-0001', mockKanbanBtn, mockEvent);
    assert.strictEqual(stopped, true);
    assert.strictEqual(clipboardContent, 'http://localhost:8080/#tab=kanban&entity=TASK-0001');
    assert.strictEqual(mockKanbanBtn.textContent, '✓ Copied URL!');

    // 2. Switch to ADRs view
    window.switchTab('adrs');
    const adrDashboardHtml = elements['dashboard-content'].innerHTML;
    assert(adrDashboardHtml.includes('copy-link-btn'));
    assert(adrDashboardHtml.includes('window.copyDeepLink'));

    const mockAdrBtn = makeElement('adr-copy-btn');
    mockAdrBtn.textContent = '🔗 Copy Link';
    stopped = false;

    window.copyDeepLink('ADR-0001', mockAdrBtn, mockEvent);
    assert.strictEqual(stopped, true);
    assert.strictEqual(clipboardContent, 'http://localhost:8080/#tab=adrs&entity=ADR-0001');
    assert.strictEqual(mockAdrBtn.textContent, '✓ Copied URL!');
    """
    run_node_test(html, test_js)


def test_matrix_deep_link_activates_tab_and_highlights_stories(tmp_path: Path):
    """Verify #tab=matrix&entity=<ID> activates Matrix tab, opens drawer, and highlights linked stories (DoD 1)."""
    init_project(tmp_path, name="TestMatrixDeepLink")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=matrix&entity=TASK-0001";
    location.href = "http://localhost:8080/#tab=matrix&entity=TASK-0001";
    {project_data_js}
    {app_js}

    // Verify matrix tab is active
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'matrix');

    // Verify drawer opened automatically
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert(elements['drawer-title'].textContent.includes('TASK-0001'));

    // Verify matrix view rendered with row and linked story highlighting
    const matrixContent = elements['dashboard-content'].innerHTML;
    assert(matrixContent.includes('Project Traceability Matrix'));
    assert(matrixContent.includes('TASK-0001'));
    assert(matrixContent.includes('highlighted-story') || matrixContent.includes('border-left:3px solid #38bdf8'));
    """
    run_node_test(html, test_js)


def test_canvas_focus_deep_link_smooth_pan_and_zoom(tmp_path: Path):
    """Verify #tab=canvas&focus=<ID> smoothly animates camera to center at 1.5x zoom (DoD 4)."""
    init_project(tmp_path, name="TestCanvasFocus")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)
    project_data_js, app_js = _extract_scripts(html)

    test_js = f"""
    location.hash = "#tab=canvas&focus=TASK-0001";
    location.href = "http://localhost:8080/#tab=canvas&focus=TASK-0001";
    {project_data_js}
    {app_js}

    // Verify tab mapped to graph
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'graph');

    // Verify camera focal node and 1.5x zoom
    assert.strictEqual(window.getFocusedNodeId(), 'TASK-0001');
    const camera = window.getCameraState();
    assert.strictEqual(camera.focusedNodeId, 'TASK-0001');
    assert.strictEqual(camera.zoom, 1.5);
    assert(camera.targetPanX !== null || camera.panX !== 0);

    // Verify detail drawer opened for target entity
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert(elements['drawer-title'].textContent.includes('TASK-0001'));
    """
    run_node_test(html, test_js)

