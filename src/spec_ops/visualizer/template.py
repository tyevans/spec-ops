"""HTML template assembling CSS styles and JS scripts for the SpecOps Visualizer."""

from typing import Any

from .scripts import VISUALIZER_JS
from .styles import VISUALIZER_CSS
from .tour_script import TOUR_CSS


class SafeTemplate(str):
    """String template that safely substitutes explicitly supplied keyword arguments."""

    def format(self, *args: Any, **kwargs: Any) -> str:
        res = str(self)
        if "back_link" not in kwargs:
            kwargs["back_link"] = "../index.html"
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
""" + TOUR_CSS + """
  </style>
</head>
<body>
  <header>
    <div class="header-left">
      <a href="{back_link}" class="nav-back-btn">← Back to Docs</a>
      <h1>⚡ {title} <span class="badge">Visualizer</span></h1>
      <button class="tour-btn" id="btn-guided-tour" onclick="startGuidedTour()" title="Interactive walkthrough of SpecOps visualizer">🧭 Take Guided Tour</button>
      <button class="ctrl-btn" id="btn-audit-drift" onclick="window.openDriftAuditModal()" title="Audit Specification Drift">🔍 Audit Specification Drift</button>
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
    <button class="tab-btn active" id="tab-graph" data-tab="graph" onclick="switchTab('graph')">🌐 Relationship Graph</button>
    <button class="tab-btn" id="tab-matrix" data-tab="matrix" onclick="switchTab('matrix')">🗂️ Project Matrix</button>
    <button class="tab-btn" id="tab-gantt" data-tab="gantt" onclick="switchTab('gantt')">📊 Gantt & Timeline</button>
    <button class="tab-btn" id="tab-kanban" data-tab="kanban" onclick="switchTab('kanban')">📋 Kanban Board</button>
    <button class="tab-btn" id="tab-prds" data-tab="prds" onclick="switchTab('prds')">🎯 PRDs & Features</button>
    <button class="tab-btn" id="tab-adrs" data-tab="adrs" onclick="switchTab('adrs')">🏛️ ADR Architecture</button>
    <button class="tab-btn" id="tab-radar" data-tab="radar" onclick="switchTab('radar')" title="Living Architectural Review Radar">📡 Architectural Review Radar</button>
    <button class="tab-btn" id="tab-personas" data-tab="personas" onclick="switchTab('personas')">👥 Personas & Stories</button>
    <button class="tab-btn" id="tab-lead" data-tab="lead" onclick="switchTab('lead')" title="Live Autonomous Worker Fleet Telemetry and Lead Operations Console">⚡ Lead Console / Fleet Telemetry</button>
    <button class="tab-btn" id="tab-security" data-tab="security" onclick="switchTab('security')">🛡️ Security &amp; Compliance</button>
    <button class="tab-btn" id="tab-uat" data-tab="uat" onclick="switchTab('uat')">📋 UAT Readiness</button>
    <button class="tab-btn" id="tab-sandbox" data-tab="sandbox" onclick="switchTab('sandbox')">🧪 PRD Sandbox</button>
  </nav>

  <main>
    <div id="canvas-view">
      <div class="graph-filter-toolbar" id="graph-filter-toolbar">
        <div class="toolbar-left">
          <select class="filter-select preset-select" id="graph-preset-select" onchange="applyPerspectivePreset(this.value)" title="Choose a perspective preset">
            <option value="default">🌐 Perspective: Default</option>
            <option value="bc">🪐 Bounded Context Clusters</option>
            <option value="delivery">⚡ Active Delivery</option>
            <option value="architecture">🏛️ Architecture &amp; ADRs</option>
            <option value="flow">🌊 Traceability Flow</option>
            <option value="custom" disabled hidden>⚙️ Custom Perspective</option>
          </select>

          <button class="ctrl-btn cluster-toggle-btn" id="btn-cluster-bc" onclick="toggleBcClustering()" title="Group and cluster nodes by Bounded Context">
            📦 Cluster: BC
          </button>

          <select class="filter-select" id="graph-bc-select" onchange="window.setFilter('bc', this.value)" title="Filter by Bounded Context">
            <option value="all">All Bounded Contexts</option>
          </select>

          <select class="filter-select" id="graph-status-select" onchange="window.setFilter('status', this.value)" title="Filter by status">
            <option value="all">All Statuses</option>
            <option value="Complete">Complete</option>
            <option value="Refined">Refined</option>
            <option value="Proposed">Proposed</option>
          </select>

          <button class="ctrl-btn" id="graph-hide-done-btn" onclick="toggleHideDone()" title="Hide complete tasks">
            👁️ Hide Done
          </button>
        </div>

        <div class="toolbar-right">
          <div class="type-pills-group" id="graph-type-pills">
            <button class="type-pill-btn active" id="pill-toggle-task" onclick="toggleTypeFilter('task')" title="Toggle Tasks"><span class="dot" style="background:#10B981"></span>Tasks</button>
            <button class="type-pill-btn active" id="pill-toggle-story" onclick="toggleTypeFilter('story')" title="Toggle Stories"><span class="dot" style="background:#06B6D4"></span>Stories</button>
            <button class="type-pill-btn active" id="pill-toggle-prd" onclick="toggleTypeFilter('prd')" title="Toggle PRDs"><span class="dot" style="background:#F43F5E"></span>PRDs</button>
            <button class="type-pill-btn active" id="pill-toggle-adr" onclick="toggleTypeFilter('adr')" title="Toggle ADRs"><span class="dot" style="background:#6366F1"></span>ADRs</button>
            <button class="type-pill-btn active" id="pill-toggle-persona" onclick="toggleTypeFilter('persona')" title="Toggle Personas"><span class="dot" style="background:#F59E0B"></span>Personas</button>
            <button class="type-pill-btn active" id="pill-toggle-bc" onclick="toggleTypeFilter('bc')" title="Toggle BC Nodes"><span class="dot" style="background:#EC4899"></span>BCs</button>
          </div>

          <select class="filter-select" id="graph-hop-select" onchange="setHopFilter(this.value)" title="Blast Radius / Neighborhood Hops">
            <option value="all">Hops: All</option>
            <option value="1">1-Hop</option>
            <option value="2">2-Hops</option>
          </select>

          <span class="filter-count-badge" id="graph-filter-count">0 nodes</span>
          <button class="ctrl-btn" id="btn-reset-filters" onclick="resetAllFilters()" title="Reset all filters">↺ Reset</button>
        </div>
      </div>

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
            <button class="copy-btn" id="drawer-permalink-btn" onclick="copyDeepLink()">🔗 Copy Deep Link</button>
          </div>
        </div>
        <button class="close-btn" onclick="closeDrawer()">&times;</button>
      </div>
      <div class="drawer-body" id="drawer-body"></div>
    </div>

    <div id="welcome-overlay" class="tour-overlay" style="display:none;">
      <div id="welcome-modal" class="tour-modal">
        <div class="tour-header">
          <span class="tour-step-badge">Product Manager Onboarding</span>
          <button class="tour-close-btn" onclick="dismissWelcomeModal()">&times;</button>
        </div>
        <h3 id="welcome-title">Welcome to SpecOps</h3>
        <p id="welcome-desc">Take a 2-minute tour of SpecOps for Product Managers</p>
        <p style="font-size:0.8rem; color:#94a3b8; margin-bottom:16px;">
          Learn how to explore PRDs &amp; Features, Gantt timelines, UAT matrix, and deep-link permalinks with zero terminal jargon.
        </p>
        <div class="tour-footer">
          <button class="ctrl-btn" id="welcome-skip-btn" onclick="dismissWelcomeModal()">Skip</button>
          <button class="ctrl-btn active" id="welcome-start-btn" onclick="startGuidedTourFromWelcome()">Take a 2-minute tour of SpecOps for Product Managers</button>
        </div>
      </div>
    </div>

    <div id="tour-overlay" class="tour-overlay" style="display:none;">
      <div id="tour-modal" class="tour-modal">
        <div class="tour-header">
          <span id="tour-step-badge" class="tour-step-badge">Step 1 of 4</span>
          <button class="tour-close-btn" onclick="closeTour()">&times;</button>
        </div>
        <h3 id="tour-title">1. Philosophy of PMaC (Project Management as Code)</h3>
        <p id="tour-desc">All specifications, user stories, tasks, and architectural decisions are version-locked in git directly alongside implementation code.</p>
        <div class="tour-footer">
          <button class="ctrl-btn" id="tour-prev-btn" onclick="prevTourStep()" style="visibility:hidden;">← Back</button>
          <button class="ctrl-btn" id="tour-skip-btn" onclick="closeTour()">Skip Tour</button>
          <button class="ctrl-btn active" id="tour-next-btn" onclick="nextTourStep()">Next →</button>
        </div>
    <div id="drift-audit-modal" class="tour-overlay" style="display:none;">
      <div id="drift-audit-modal-content" class="tour-modal" style="max-width:760px; width:92%; max-height:86vh; overflow-y:auto;">
        <div class="tour-header">
          <span class="tour-step-badge" style="background:#6366f1;">Architectural Review</span>
          <button class="tour-close-btn" onclick="window.closeDriftAuditModal()">&times;</button>
        </div>
        <h3 style="color:#fff; margin-bottom:4px;">Specification Drift &amp; Orphan Entities Audit</h3>
        <div id="drift-audit-modal-body"></div>
        <div class="tour-footer" style="margin-top:16px;">
          <button class="ctrl-btn" onclick="window.closeDriftAuditModal()">Close</button>
          <button class="ctrl-btn active" id="btn-modal-export-drift" onclick="window.exportDriftAuditReport()">📄 Export Audit Report (dist/spec-drift-audit.json)</button>
        </div>
      </div>
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
