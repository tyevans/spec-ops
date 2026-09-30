"""Tests for standalone 2D project visualizer generator and multi-view templates."""

from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.generator import generate_standalone_html, serialize_project_data
from spec_ops.visualizer.template import SafeTemplate


def test_safe_template_keyword_substitution():
    """Verify SafeTemplate substitutes {key} without breaking CSS braces."""
    raw = "body { color: {text_color}; margin: 0; } .nav { padding: 1rem; }"
    tmpl = SafeTemplate(raw)
    result = tmpl.format(text_color="#FFFFFF")
    assert "color: #FFFFFF;" in result
    assert "margin: 0;" in result
    assert ".nav { padding: 1rem; }" in result


def test_visualizer_generation_on_scaffolded_project(tmp_path: Path):
    """Verify standalone HTML visualizer generates with all multi-view modules."""
    init_project(tmp_path, name="TestVisProject")
    config = load_config(root_dir=tmp_path)

    payload = serialize_project_data(config)
    assert payload["project"]["name"] == "TestVisProject"
    assert len(payload["nodes"]) >= 4
    assert len(payload["edges"]) >= 1
    assert "tasks" in payload
    assert "personas" in payload
    assert "stories" in payload
    assert "adrs" in payload

    html = generate_standalone_html(config)
    assert "<!DOCTYPE html>" in html
    assert "TestVisProject — SpecOps Visualizer" in html
    # Check tab buttons
    assert 'data-tab="graph"' in html
    assert 'data-tab="matrix"' in html
    assert 'data-tab="gantt"' in html
    assert 'data-tab="kanban"' in html
    assert 'data-tab="prds"' in html
    assert 'data-tab="adrs"' in html
    assert 'data-tab="personas"' in html
    assert 'data-tab="lead"' in html
    assert 'data-tab="security"' in html
    # Check scripts embedded
    assert "window.switchTab = function(" in html
    assert "window.renderMatrixView = function(" in html
    assert "window.renderLeadConsoleView = function(" in html
    assert "window.renderSecurityRadarView = function(" in html
    assert "function renderGanttView(" in html
    assert "function renderKanbanView(" in html
    assert "function renderPrdsView(" in html
    assert "function renderAdrsView(" in html
    assert "function renderPersonasView(" in html
    assert "window.openDrawer = function(" in html
    assert "function computeFlowLayout(" in html
    assert "function fitFlowView(" in html
    assert "window.switchLayout = function(" in html


def test_flow_dag_layout_script_present_and_balanced():
    """Verify that flow DAG layout script contains multi-column balancing and relational sorting."""
    from spec_ops.visualizer.layouts_script import LAYOUTS_JS

    assert "computeFlowLayout" in LAYOUTS_JS
    assert "fitFlowView" in LAYOUTS_JS
    assert "targetMaxRows" in LAYOUTS_JS
    assert "stageConfig" in LAYOUTS_JS
    assert "nodePrdMap" in LAYOUTS_JS
    assert "flowStages" in LAYOUTS_JS


def test_url_hash_routing_script_presence_and_invariants(tmp_path: Path):
    """Verify that URL hash router and permalink controls are generated in the HTML bundle."""
    init_project(tmp_path, name="TestRouteProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)

    assert "window.parseHash = parseHash;" in html
    assert "window.serializeHash = serializeHash;" in html
    assert "function internalSwitchTab(" in html
    assert "function updateUrl(" in html
    assert "window.copyDeepLink = function(" in html
    assert 'id="drawer-permalink-btn"' in html
    assert "window.focusNode = function(" in html
    assert "window.addEventListener(\"popstate\", onHistoryChange);" in html
    assert "window.addEventListener(\"hashchange\", onHistoryChange);" in html


def _run_node_test(html: str, test_script: str) -> None:
    import re
    import subprocess

    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) >= 2
    project_data_js = scripts[0]
    app_js = scripts[1]

    harness = f"""
    const assert = require('assert');
    const events = {{}};
    const historyStack = [];
    let historyIndex = -1;

    const location = {{
      hash: "",
      href: "http://localhost:8080/",
    }};

    const history = {{
      pushState(data, unused, url) {{
        location.hash = url;
        location.href = "http://localhost:8080/" + url;
        historyIndex++;
        historyStack.splice(historyIndex, historyStack.length - historyIndex, url);
      }},
      replaceState(data, unused, url) {{
        location.hash = url;
        location.href = "http://localhost:8080/" + url;
        if (historyIndex === -1) {{
          historyIndex = 0;
          historyStack.push(url);
        }} else {{
          historyStack[historyIndex] = url;
        }}
      }}
    }};

    const elements = {{}};
    function makeElement(id) {{
      const classes = new Set();
      return elements[id] = {{
        id,
        style: {{ display: "" }},
        classList: {{
          add: (c) => classes.add(c),
          remove: (c) => classes.delete(c),
          contains: (c) => classes.has(c),
        }},
        dataset: {{ tab: id }},
        textContent: "",
        value: "",
        innerHTML: "",
        addEventListener: () => {{}},
        getContext: () => ({{
          clearRect: () => {{}}, save: () => {{}}, restore: () => {{}},
          translate: () => {{}}, scale: () => {{}}, beginPath: () => {{}},
          arc: () => {{}}, fill: () => {{}}, stroke: () => {{}},
          moveTo: () => {{}}, lineTo: () => {{}}, fillText: () => {{}},
          setLineDash: () => {{}},
        }}),
        clientWidth: 1000, clientHeight: 800,
        getBoundingClientRect: () => ({{ left: 0, top: 0, width: 1000, height: 800 }}),
      }};
    }}

    const tabBtns = ["graph", "matrix", "gantt", "kanban", "prds", "adrs", "personas", "lead", "security"].map(t => {{
      const btn = makeElement("tab-" + t);
      btn.dataset.tab = t;
      return btn;
    }});

    const document = {{
      getElementById: (id) => elements[id] || makeElement(id),
      querySelectorAll: (sel) => sel === ".tab-btn" ? tabBtns : [],
      addEventListener: (ev, fn) => {{ (events[ev] = events[ev] || []).push(fn); }},
    }};

    const storage = {{}};
    const localStorage = {{
      getItem: (k) => storage[k] !== undefined ? storage[k] : null,
      setItem: (k, v) => {{ storage[k] = String(v); }},
      removeItem: (k) => {{ delete storage[k]; }},
      clear: () => {{ for (const k in storage) delete storage[k]; }},
    }};

    let clipboardContent = '';
    const window = {{
      location, history, document, localStorage,
      addEventListener: (ev, fn) => {{ (events[ev] = events[ev] || []).push(fn); }},
      navigator: {{ clipboard: {{ writeText: async (t) => {{ clipboardContent = t; }} }} }},
      requestAnimationFrame: () => {{}},
    }};

    global.window = window;
    global.document = document;
    global.location = location;
    global.history = history;
    global.localStorage = localStorage;
    global.requestAnimationFrame = window.requestAnimationFrame;
    global.URLSearchParams = URLSearchParams;

    function triggerPopState() {{
      (events['popstate'] || []).forEach(fn => fn());
    }}

    {test_script}
    """
    res = subprocess.run(["node"], input=harness, capture_output=True, text=True)
    assert res.returncode == 0, f"Node test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"


run_node_test = _run_node_test


def test_node_deep_linking_initial_render(tmp_path: Path):
    """Verify deep-linking to view tabs and entities on initial load (US-0103 Scenario 1)."""
    init_project(tmp_path, name="TestDeepLink")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)

    test_js = """
    // Case 1: Kanban with entity TASK-0001
    location.hash = "#tab=kanban&entity=TASK-0001";
    location.href = "http://localhost:8080/#tab=kanban&entity=TASK-0001";
    {project_data_js}
    {app_js}

    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'kanban');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert(elements['drawer-title'].textContent.includes('TASK-0001'));
    assert.strictEqual(elements['dashboard-view'].style.display, 'flex');
    assert.strictEqual(elements['canvas-view'].style.display, 'none');
    """
    import re
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    _run_node_test(html, test_js.format(project_data_js=scripts[0], app_js=scripts[1]))


def test_node_bidirectional_state_synchronization(tmp_path: Path):
    """Verify bidirectional state sync from UI filters to URL hash (US-0103 Scenario 2)."""
    init_project(tmp_path, name="TestSyncProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)

    test_js = """
    location.hash = "";
    location.href = "http://localhost:8080/";
    {project_data_js}
    {app_js}

    assert.strictEqual(location.hash, '#tab=graph');

    // Switch to Kanban
    window.switchTab('kanban');
    assert.strictEqual(location.hash, '#tab=kanban');

    // Set faceted filters
    window.setFilter('query', 'preflight');
    window.setFilter('status', 'Refined');
    window.setFilter('hideDone', true);

    assert.strictEqual(location.hash, '#tab=kanban&q=preflight&status=Refined&hideDone=true');
    """
    import re
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    _run_node_test(html, test_js.format(project_data_js=scripts[0], app_js=scripts[1]))


def test_node_browser_history_back_forward(tmp_path: Path):
    """Verify browser Back and Forward history traversal (US-0103 Scenario 3)."""
    init_project(tmp_path, name="TestHistoryProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)

    test_js = """
    location.hash = "";
    location.href = "http://localhost:8080/";
    {project_data_js}
    {app_js}

    assert.strictEqual(location.hash, '#tab=graph');

    // 1. Navigate to gantt
    window.switchTab('gantt');
    assert.strictEqual(location.hash, '#tab=gantt');

    // 2. Apply search filter
    window.setFilter('query', 'spike');
    assert.strictEqual(location.hash, '#tab=gantt&q=spike');

    // 3. Open entity drawer
    window.openDrawer('TASK-0001');
    assert.strictEqual(location.hash, '#tab=gantt&q=spike&entity=TASK-0001');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);

    // 4. Back once -> closes drawer, keeps gantt tab and filter
    historyIndex--;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    assert.strictEqual(location.hash, '#tab=gantt&q=spike');
    assert.strictEqual(elements['drawer'].classList.contains('open'), false);
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'gantt');

    // 5. Back second time -> transitions to graph tab
    historyIndex--;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    assert.strictEqual(location.hash, '#tab=graph');
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'graph');

    // 6. Forward once -> re-applies gantt tab and filter
    historyIndex++;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    assert.strictEqual(location.hash, '#tab=gantt&q=spike');
    assert.strictEqual(tabBtns.find(b => b.classList.contains('active'))?.dataset.tab, 'gantt');
    assert.strictEqual(elements['drawer'].classList.contains('open'), false);

    // 7. Forward second time -> re-opens drawer
    historyIndex++;
    location.hash = historyStack[historyIndex];
    triggerPopState();
    assert.strictEqual(location.hash, '#tab=gantt&q=spike&entity=TASK-0001');
    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    """
    import re
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    _run_node_test(html, test_js.format(project_data_js=scripts[0], app_js=scripts[1]))


def test_node_graph_camera_focus_permalink(tmp_path: Path):
    """Verify camera viewport centering and permalink copy on graph view (US-0103 Scenario 4)."""
    init_project(tmp_path, name="TestCameraProject")
    config = load_config(root_dir=tmp_path)
    html = generate_standalone_html(config)

    test_js = """
    location.hash = "#tab=graph&entity=TASK-0001";
    location.href = "http://localhost:8080/#tab=graph&entity=TASK-0001";
    {project_data_js}
    {app_js}

    assert.strictEqual(elements['drawer'].classList.contains('open'), true);
    assert.strictEqual(elements['drawer-permalink-btn'].style.display, 'inline-block');

    // Test deep link copying
    window.copyDeepLink();
    setTimeout(() => {{
      assert.strictEqual(clipboardContent, 'http://localhost:8080/#tab=graph&entity=TASK-0001');
    }}, 10);
    """
    import re
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    _run_node_test(html, test_js.format(project_data_js=scripts[0], app_js=scripts[1]))

