"""HTML template assembling CSS styles and JS scripts for the SpecOps Visualizer."""

from typing import Any

from .scripts import VISUALIZER_JS
from .styles import VISUALIZER_CSS


class SafeTemplate(str):
    """String template that safely substitutes explicitly supplied keyword arguments."""

    def format(self, *args: Any, **kwargs: Any) -> str:
        res = str(self)
        for k, v in kwargs.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res


_BASE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SpecOps Visualizer</title>
  <style>
""" + VISUALIZER_CSS + """
  </style>
</head>
<body>
  <header>
    <div class="header-left">
      <a href="../index.html" class="nav-back-btn">← Back to Docs</a>
      <h1>⚡ {title} <span class="badge">Visualizer</span></h1>
    </div>
    <div class="header-center" id="graph-controls">
      <div class="layout-group">
        <button class="layout-btn active" id="btn-layout-network" onclick="switchLayout('network')">🪐 Force</button>
        <button class="layout-btn" id="btn-layout-flow" onclick="switchLayout('flow')">🌊 Flow DAG</button>
        <button class="layout-btn" id="btn-layout-radial" onclick="switchLayout('radial')">🎯 Radar</button>
      </div>
      <button class="ctrl-btn" id="btn-physics-toggle" onclick="togglePhysics()" title="Pause/Resume Force Simulation">⏸️ Freeze</button>
      <button class="ctrl-btn" id="btn-physics-shuffle" onclick="shufflePhysics()" title="Inject kinetic energy to shuffle nodes">⚡ Shuffle</button>
      <div class="search-box">
        <input type="text" id="search-input" placeholder="Search entities (e.g. TASK, Alex, PRD)...">
      </div>
    </div>
    <div class="stats-bar" id="stats">
      <span>Tasks: <b id="stat-tasks">0</b></span>
      <span>Stories: <b id="stat-stories">0</b></span>
      <span>PRDs: <b id="stat-prds">0</b></span>
      <span>ADRs: <b id="stat-adrs">0</b></span>
      <span>Edges: <b id="stat-edges">0</b></span>
    </div>
  </header>

  <nav class="nav-tabs-bar" id="tab-nav">
    <button class="tab-btn active" data-tab="graph" onclick="switchTab('graph')">🌐 Relationship Graph</button>
    <button class="tab-btn" data-tab="gantt" onclick="switchTab('gantt')">📊 Gantt & Timeline</button>
    <button class="tab-btn" data-tab="kanban" onclick="switchTab('kanban')">📋 Kanban Board</button>
    <button class="tab-btn" data-tab="prds" onclick="switchTab('prds')">🎯 PRDs & Features</button>
    <button class="tab-btn" data-tab="adrs" onclick="switchTab('adrs')">🏛️ ADR Architecture</button>
    <button class="tab-btn" data-tab="personas" onclick="switchTab('personas')">👥 Personas & Stories</button>
  </nav>

  <main>
    <div id="canvas-view">
      <div class="legend">
        <div class="legend-item"><span class="legend-dot" style="background:#F59E0B"></span> Persona</div>
        <div class="legend-item"><span class="legend-dot" style="background:#06B6D4"></span> Story</div>
        <div class="legend-item"><span class="legend-dot" style="background:#F43F5E"></span> PRD</div>
        <div class="legend-item"><span class="legend-dot" style="background:#10B981"></span> Complete Task</div>
        <div class="legend-item"><span class="legend-dot" style="background:#F59E0B"></span> Refined Task</div>
        <div class="legend-item"><span class="legend-dot" style="background:#8B5CF6"></span> Proposed Task</div>
        <div class="legend-item"><span class="legend-dot" style="background:#6366F1"></span> ADR</div>
        <div class="legend-item"><span class="legend-dot" style="background:#EC4899"></span> Bounded Context</div>
      </div>
      <div class="hint-bar">
        Scroll to Zoom · Drag canvas to Pan · Drag nodes to move · Click to inspect
      </div>
      <div class="zoom-controls">
        <button class="zoom-btn" onclick="zoomIn()" title="Zoom In">+</button>
        <button class="zoom-btn" onclick="zoomOut()" title="Zoom Out">−</button>
        <button class="zoom-btn" onclick="resetZoom()" title="Reset Camera">⟲</button>
      </div>
      <canvas id="network-canvas"></canvas>
    </div>

    <div id="dashboard-view">
      <div id="dashboard-content"></div>
    </div>

    <div id="drawer-backdrop" onclick="closeDrawer()"></div>
    <div id="drawer">
      <div class="drawer-header">
        <div class="drawer-title-area">
          <span class="drawer-type-badge" id="drawer-type-badge">TASK</span>
          <h2 id="drawer-title">Entity Title</h2>
          <div class="drawer-filepath-bar">
            <span>File:</span>
            <span class="filepath-text" id="drawer-filepath-text">docs/project/...</span>
            <button class="copy-btn" id="drawer-copy-btn" onclick="copyFilePath()">📋 Copy Path</button>
          </div>
        </div>
        <button class="close-btn" onclick="closeDrawer()">&times;</button>
      </div>
      <div class="drawer-body" id="drawer-body"></div>
    </div>
  </main>
  <script>
    window.PROJECT_DATA = {data_json};
  </script>
  <script>
""" + VISUALIZER_JS + """
  </script>
</body>
</html>
"""

VISUALIZER_HTML_TEMPLATE = SafeTemplate(_BASE_SHELL)
