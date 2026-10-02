"""CSS styles for the SpecOps Visualizer."""

from .lead_console import LEAD_CONSOLE_CSS
from .security_metrics import SECURITY_RADAR_CSS
from .matrix import MATRIX_CSS

_BASE_CSS = """
:root {
  --bg: #0b0f19;
  --card-bg: rgba(19, 26, 42, 0.95);
  --elevated: #151d30;
  --border: rgba(255, 255, 255, 0.12);
  --border-subtle: rgba(255, 255, 255, 0.08);
  --text: #f3f4f6;
  --text-muted: #94a3b8;
  --primary: #3b82f6;
  --primary-hover: #60a5fa;
  --accent-purple: #8b5cf6;
  --accent-emerald: #10b981;
  --accent-amber: #f59e0b;
  --accent-cyan: #06b6d4;
  --accent-rose: #f43f5e;
  --accent-indigo: #6366f1;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 100vw;
  overflow-x: hidden;
  overflow-y: hidden;
}

header {
  background: var(--card-bg);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border);
  padding: 10px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 20;
  gap: 14px;
}
.header-left { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.nav-back-btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px;
  background: rgba(255, 255, 255, 0.07); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); text-decoration: none;
  font-size: 0.82rem; font-weight: 600; transition: all 0.15s ease;
}
.nav-back-btn:hover { background: rgba(59, 130, 246, 0.2); border-color: var(--primary); color: #fff; }
header h1 { font-size: 1.05rem; display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.badge { font-size: 0.72rem; padding: 2px 8px; border-radius: 9999px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-weight: 600; }

.header-center { display: flex; align-items: center; gap: 10px; flex: 1; justify-content: center; }
.layout-group { display: flex; background: var(--elevated); border: 1px solid var(--border); border-radius: 8px; padding: 3px; gap: 2px; }
.layout-btn {
  background: transparent; border: none; color: var(--text-muted); padding: 5px 11px;
  border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer;
  transition: all 0.15s ease; display: flex; align-items: center; gap: 5px;
}
.layout-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.06); }
.layout-btn.active { background: #4f46e5; color: #fff; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4); }

.ctrl-btn {
  background: var(--elevated); border: 1px solid var(--border); color: var(--text-muted);
  padding: 5px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;
  cursor: pointer; transition: all 0.15s ease; display: flex; align-items: center; gap: 5px;
}
.ctrl-btn:hover, .ctrl-btn.active { color: #fff; border-color: var(--primary); background: rgba(59, 130, 246, 0.15); }

.search-box { position: relative; width: 220px; }
.search-box input {
  width: 100%; background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border);
  border-radius: 6px; padding: 6px 12px; color: #fff; font-size: 0.82rem; outline: none; transition: border-color 0.15s;
}
.search-box input:focus { border-color: var(--primary); }

.stats-bar { display: flex; gap: 12px; font-size: 0.8rem; color: var(--text-muted); align-items: center; white-space: nowrap; flex-shrink: 0; }
.stats-bar span b { color: var(--text); }

/* Navigation Tabs Bar */
.nav-tabs-bar {
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  padding: 6px 18px;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 15;
  overflow-x: auto;
}
.tab-btn {
  background: transparent; border: 1px solid transparent; color: var(--text-muted);
  padding: 5px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;
  cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.15s ease;
  white-space: nowrap;
}
.tab-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.05); }
.tab-btn.active {
  background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border-color: rgba(99, 102, 241, 0.4);
}

main { flex: 1; display: flex; position: relative; overflow: hidden; }

/* 2D Canvas View */
#canvas-view { flex: 1; width: 100%; height: 100%; position: relative; display: flex; }
#network-canvas { flex: 1; width: 100%; height: 100%; background: radial-gradient(circle at center, #111827 0%, #030712 100%); cursor: grab; }
#network-canvas:active { cursor: grabbing; }

/* Graph Canvas Filter Toolbar */
.graph-filter-toolbar {
  position: absolute; top: 10px; left: 14px; right: 14px;
  background: rgba(15, 23, 42, 0.94); backdrop-filter: blur(14px);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 6px 12px; display: flex; justify-content: space-between;
  align-items: center; gap: 8px; z-index: 10; flex-wrap: wrap;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45);
}
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.type-pills-group {
  display: flex; align-items: center; gap: 3px;
  background: rgba(11, 15, 25, 0.6); border: 1px solid var(--border-subtle);
  border-radius: 6px; padding: 2px 4px;
}
.type-pill-btn {
  background: transparent; border: 1px solid transparent; border-radius: 4px;
  padding: 3px 6px; font-size: 0.72rem; font-weight: 600; color: var(--text-muted);
  cursor: pointer; display: flex; align-items: center; gap: 5px; transition: all 0.15s ease;
}
.type-pill-btn .dot { width: 7px; height: 7px; border-radius: 50%; opacity: 0.5; }
.type-pill-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.05); }
.type-pill-btn.active {
  background: rgba(255, 255, 255, 0.1); color: #fff; border-color: rgba(255, 255, 255, 0.2);
}
.type-pill-btn.active .dot { opacity: 1; box-shadow: 0 0 6px currentColor; }
.filter-count-badge {
  font-size: 0.72rem; color: var(--text-muted); padding: 3px 8px;
  background: rgba(255, 255, 255, 0.05); border-radius: 4px; white-space: nowrap; font-family: monospace;
}
.cluster-toggle-btn.active {
  background: rgba(236, 72, 153, 0.2); border-color: #ec4899; color: #f472b6;
  box-shadow: 0 0 10px rgba(236, 72, 153, 0.25);
}

.legend {
  position: absolute; top: 56px; left: 14px; background: var(--card-bg);
  backdrop-filter: blur(8px); border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 12px; font-size: 0.72rem; z-index: 5; display: flex; flex-direction: column; gap: 4px; pointer-events: none;
}
.legend-item { display: flex; align-items: center; gap: 8px; color: var(--text-muted); }
.legend-dot { width: 9px; height: 9px; border-radius: 50%; }

.hint-bar {
  position: absolute; bottom: 14px; left: 14px; background: rgba(15, 23, 42, 0.85);
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; font-size: 0.74rem; color: var(--text-muted); pointer-events: none;
}

.zoom-controls { position: absolute; bottom: 14px; right: 14px; display: flex; gap: 6px; z-index: 5; }
.zoom-btn {
  background: var(--card-bg); border: 1px solid var(--border); color: var(--text);
  width: 32px; height: 32px; border-radius: 6px; font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.zoom-btn:hover { background: rgba(255, 255, 255, 0.15); }

/* Dashboard Multi-Tab View */
#dashboard-view {
  flex: 1; width: 100%; height: 100%; overflow-y: auto; padding: 20px 24px;
  display: none; flex-direction: column; gap: 16px;
}
#dashboard-content { display: flex; flex-direction: column; gap: 16px; width: 100%; }

/* Faceted Filter Bar */
.view-filter-bar {
  background: var(--elevated); border: 1px solid var(--border-subtle); border-radius: 8px;
  padding: 10px 16px; display: flex; justify-content: space-between; align-items: center;
  gap: 12px; flex-wrap: wrap;
}
.filter-input {
  background: rgba(11, 15, 25, 0.8); border: 1px solid var(--border); border-radius: 6px;
  padding: 5px 10px; color: #fff; font-size: 0.78rem; outline: none; width: 220px;
}
.filter-input:focus { border-color: var(--primary); }
.filter-select {
  background: rgba(11, 15, 25, 0.8); border: 1px solid var(--border); border-radius: 6px;
  padding: 5px 8px; color: var(--text); font-size: 0.78rem; outline: none; cursor: pointer;
}
.filter-checkbox-label {
  display: flex; align-items: center; gap: 6px; font-size: 0.76rem; color: var(--text-muted); cursor: pointer;
}
.active-filter-chip {
  display: inline-flex; align-items: center; gap: 8px; background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 9999px; padding: 3px 10px;
  font-size: 0.74rem; color: #93c5fd;
}
.active-filter-chip button {
  background: transparent; border: none; color: #93c5fd; cursor: pointer; font-size: 1rem; line-height: 1;
}

/* Gantt Styles */
.gantt-group-card {
  background: var(--elevated); border: 1px solid var(--border-subtle); border-radius: 10px;
  padding: 16px; display: flex; flex-direction: column; gap: 12px;
}
.gantt-group-header {
  display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;
}
.gantt-items-list { display: flex; flex-direction: column; gap: 8px; }
.gantt-item-row {
  display: flex; align-items: center; padding: 8px 12px; background: rgba(11, 15, 25, 0.5);
  border: 1px solid var(--border-subtle); border-radius: 6px; cursor: pointer; transition: background 0.15s;
}
.gantt-item-row:hover { background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.15); }
.gantt-bar-container {
  width: 100%; height: 8px; background: rgba(255, 255, 255, 0.08); border-radius: 9999px; overflow: hidden;
}
.gantt-bar { height: 100%; border-radius: 9999px; }
.status-complete { background: #10b981; }
.status-refined { background: #f59e0b; }
.status-proposed { background: #8b5cf6; }

/* Kanban Styles */
.kanban-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; width: 100%;
}
.kanban-col {
  background: var(--elevated); border: 1px solid var(--border-subtle); border-radius: 10px;
  display: flex; flex-direction: column; max-height: calc(100vh - 180px);
}
.kanban-col-header {
  padding: 12px 16px; border-bottom: 1px solid var(--border-subtle); display: flex;
  justify-content: space-between; align-items: center; font-size: 0.85rem;
}
.count-badge { padding: 2px 7px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; }
.kanban-cards-area {
  padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; flex: 1;
}
.kanban-card {
  background: rgba(11, 15, 25, 0.75); border: 1px solid var(--border-subtle); border-radius: 8px;
  padding: 12px; cursor: pointer; transition: all 0.15s ease;
}
.kanban-card:hover {
  border-color: rgba(255, 255, 255, 0.2); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.empty-state {
  padding: 30px; text-align: center; color: var(--text-muted); font-size: 0.85rem;
  background: var(--elevated); border: 1px dashed var(--border); border-radius: 10px;
}

/* Backdrop & Drawer */
#drawer-backdrop {
  position: absolute; inset: 0; background: rgba(0, 0, 0, 0.45); backdrop-filter: blur(2px);
  z-index: 25; opacity: 0; pointer-events: none; transition: opacity 0.25s ease;
}
#drawer-backdrop.open { opacity: 1; pointer-events: auto; }

#drawer {
  position: absolute; right: 0; top: 0; bottom: 0; width: 520px; max-width: 92vw;
  background: var(--card-bg); backdrop-filter: blur(20px); border-left: 1px solid var(--border);
  transform: translateX(100%); transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex; flex-direction: column; z-index: 30; box-shadow: -10px 0 35px rgba(0, 0, 0, 0.6);
}
#drawer.open { transform: translateX(0); }

.drawer-header {
  padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex;
  justify-content: space-between; align-items: flex-start; gap: 12px; background: rgba(15, 23, 42, 0.5);
}
.drawer-title-area { display: flex; flex-direction: column; gap: 6px; flex: 1; min-width: 0; }
.drawer-type-badge {
  display: inline-flex; align-items: center; align-self: flex-start; padding: 3px 9px;
  border-radius: 9999px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
}
.drawer-title-area h2 { font-size: 1.15rem; font-weight: 700; color: #fff; line-height: 1.3; word-break: break-word; }
.drawer-filepath-bar { display: flex; align-items: center; gap: 8px; font-size: 0.76rem; color: var(--text-muted); margin-top: 4px; }
.filepath-text { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; color: #93c5fd; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }
.copy-btn {
  background: rgba(255, 255, 255, 0.08); border: 1px solid var(--border); border-radius: 4px;
  padding: 2px 7px; color: var(--text); font-size: 0.72rem; cursor: pointer; white-space: nowrap; transition: all 0.15s;
}
.copy-btn:hover { background: rgba(59, 130, 246, 0.25); border-color: var(--primary); }
.close-btn { cursor: pointer; background: transparent; border: none; color: var(--text-muted); font-size: 1.4rem; padding: 0 4px; line-height: 1; }
.close-btn:hover { color: #fff; }

.drawer-body { padding: 20px; overflow-y: auto; flex: 1; font-size: 0.88rem; line-height: 1.6; display: flex; flex-direction: column; gap: 18px; }

.card-box {
  background: var(--elevated); border: 1px solid var(--border-subtle); border-radius: 10px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 10px;
}
.card-box-title {
  font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--text-muted); display: flex; align-items: center; justify-content: space-between;
}
.card-box code {
  background: rgba(255, 255, 255, 0.1); padding: 1px 5px; border-radius: 4px;
  font-family: ui-monospace, monospace; font-size: 0.8em; color: #93c5fd;
}
.pills-container { display: flex; flex-wrap: wrap; gap: 6px; }
.entity-pill {
  display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 0.76rem; font-weight: 600;
  cursor: pointer; border: 1px solid transparent; transition: all 0.15s ease; background: rgba(255, 255, 255, 0.06); color: var(--text);
}
.entity-pill:hover { filter: brightness(1.2); transform: translateY(-1px); }
.pill-task { background: rgba(139, 92, 246, 0.15); color: #c4b5fd; border-color: rgba(139, 92, 246, 0.3); }
.pill-adr { background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border-color: rgba(99, 102, 241, 0.3); }
.pill-story { background: rgba(6, 182, 212, 0.15); color: #67e8f9; border-color: rgba(6, 182, 212, 0.3); }
.pill-prd { background: rgba(244, 63, 94, 0.15); color: #fda4af; border-color: rgba(244, 63, 94, 0.3); }
.pill-persona { background: rgba(245, 158, 11, 0.15); color: #fde68a; border-color: rgba(245, 158, 11, 0.3); }
.pill-bc { background: rgba(236, 72, 153, 0.15); color: #f472b6; border-color: rgba(236, 72, 153, 0.3); }

.commit-row {
  background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-subtle); border-radius: 6px;
  padding: 8px 10px; display: flex; flex-direction: column; gap: 3px; font-size: 0.76rem;
}
.commit-meta { display: flex; justify-content: space-between; font-family: ui-monospace, monospace; }
.commit-hash { color: #818cf8; font-weight: 700; }
.commit-date { color: var(--text-muted); font-size: 0.72rem; }
.commit-subject { color: #e2e8f0; font-family: ui-monospace, monospace; line-height: 1.3; }

.markdown-box {
  background: rgba(11, 15, 25, 0.6); border: 1px solid var(--border-subtle); border-radius: 8px;
  padding: 14px; font-size: 0.82rem; line-height: 1.6; color: #cbd5e1;
}
.markdown-box h1, .markdown-box h2, .markdown-box h3 { color: #fff; margin-top: 12px; margin-bottom: 6px; font-size: 0.94rem; }
.markdown-box h1:first-child, .markdown-box h2:first-child { margin-top: 0; }
.markdown-box p { margin-bottom: 8px; }
.markdown-box ul, .markdown-box ol { margin-left: 20px; margin-bottom: 8px; }
.markdown-box li { margin-bottom: 3px; }
.markdown-box code {
  background: rgba(255, 255, 255, 0.1); padding: 1px 5px; border-radius: 4px;
  font-family: ui-monospace, monospace; font-size: 0.8em; color: #93c5fd;
}
.markdown-box pre { background: #030712; border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px; overflow-x: auto; margin-bottom: 10px; }
.markdown-box pre code { background: transparent; padding: 0; color: #a5b4fc; }
.markdown-box blockquote { border-left: 3px solid #6366f1; padding-left: 12px; color: #94a3b8; font-style: italic; margin-bottom: 8px; }
@media (max-width: 768px) {
  header { flex-wrap: wrap; padding: 8px 12px; gap: 8px; height: auto; max-width: 100vw; }
  .header-left { flex-wrap: wrap; gap: 8px; width: 100%; justify-content: space-between; }
  .header-center { flex-wrap: wrap; width: 100%; justify-content: flex-start; gap: 6px; }
  .search-box { width: 100%; }
  .stats-bar { width: 100%; overflow-x: auto; padding-bottom: 2px; }
  .nav-tabs-bar { max-width: 100vw; overflow-x: auto; -webkit-overflow-scrolling: touch; padding: 6px 10px; }
  .graph-filter-toolbar { flex-wrap: wrap; max-width: 100vw; padding: 6px 10px; height: auto; }
  #canvas-view, #dashboard-view, main { max-width: 100vw; overflow-x: hidden; }
}
"""

VISUALIZER_CSS = _BASE_CSS + "\n" + MATRIX_CSS + "\n" + LEAD_CONSOLE_CSS + "\n" + SECURITY_RADAR_CSS
