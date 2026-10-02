"""PRD Studio user interface renderer, component stories, and client assets."""

from __future__ import annotations

import json
from typing import Any

from .studio import KNOWN_PERSONAS

STUDIO_COMPONENT_STORIES: dict[str, dict[str, Any]] = {
    "PRDFormEditor": {
        "title": "PRD Form Editor Component",
        "description": "Interactive form fields for title, persona, component, problem statement, and outcomes.",
        "props": ["state", "validation_errors", "is_dirty"],
        "default_state": {
            "title": "Self-Service Notification Center",
            "persona": "Taylor",
            "component": "prd",
            "problem_statement": "Users cannot configure digest preferences.",
            "outcomes": ["User configures digest frequency via UI"],
            "is_dirty": False,
            "is_valid": True,
        },
    },
    "CheckableOutcomesBuilder": {
        "title": "Checkable Outcomes List Builder",
        "description": "Dynamic outcome list with addition, deletion, and index reordering.",
        "props": ["outcomes", "on_add", "on_remove", "on_reorder"],
        "default_state": {
            "outcomes": [
                "Running spec-ops prd studio launches the UI",
                "Flags zero violations with line-level diagnostics",
            ]
        },
    },
    "DiataxisLivePreview": {
        "title": "Diataxis Live Preview Pane",
        "description": "Real-time split-pane Markdown rendering with syntax highlighting and validation badges.",
        "props": ["markdown_content", "is_valid", "stage"],
        "default_state": {
            "markdown_content": "# PRD-0003: Product Discovery\n## Problem Statement\n...",
            "is_valid": True,
            "stage": "idea",
        },
    },
    "PRDRegistryDrawer": {
        "title": "PRD Registry Browser Drawer",
        "description": "Sidebar for browsing, filtering, and loading PRD specifications across stages.",
        "props": ["prds", "active_prd_id", "on_select"],
        "default_state": {
            "active_prd_id": "PRD-0003",
            "prds": [
                {"prd_id": "PRD-0001", "title": "Core Architecture", "stage": "accepted"},
                {"prd_id": "PRD-0003", "title": "Product Discovery", "stage": "idea"},
            ],
        },
    },
    "ActionToolbar": {
        "title": "PRD Studio Action Toolbar",
        "description": "Global action bar with save, commit writeback, stage promotion, and sync status.",
        "props": ["is_dirty", "last_saved_at", "last_commit_hash", "stage"],
        "default_state": {"is_dirty": False, "last_saved_at": 1727800000.0, "stage": "idea"},
    },
}


def render_studio_html(initial_state: dict[str, Any] | None = None) -> str:
    """Renders browser-native vanilla HTML/CSS/JS interface for SpecOps PRD Studio."""
    init_json = json.dumps(initial_state or {}, ensure_ascii=False)
    personas_options = "".join(f'<option value="{p}">{p}</option>' for p in sorted(KNOWN_PERSONAS))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SpecOps PRD Studio</title>
  <style>
    :root {{ --bg: #0f172a; --surface: #1e293b; --border: #334155; --text: #f8fafc; --muted: #94a3b8; --accent: #38bdf8; --accent-hover: #0ea5e9; --danger: #ef4444; --danger-bg: #450a0a; --success: #22c55e; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
    header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }}
    .brand {{ font-size: 1.1rem; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 8px; }}
    .status-badge {{ font-size: 0.75rem; padding: 3px 8px; border-radius: 9999px; background: #047857; color: #a7f3d0; font-weight: 600; text-transform: uppercase; }}
    .status-badge.dirty {{ background: #b45309; color: #fde68a; }}
    .container {{ flex: 1; display: flex; overflow: hidden; }}
    .sidebar {{ width: 280px; background: #0b1120; border-right: 1px solid var(--border); display: flex; flex-direction: column; }}
    .sidebar-header {{ padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 0.85rem; font-weight: 600; color: var(--muted); display: flex; justify-content: space-between; align-items: center; }}
    .prd-list {{ flex: 1; overflow-y: auto; list-style: none; }}
    .prd-item {{ padding: 10px 16px; border-bottom: 1px solid rgba(51, 65, 85, 0.4); cursor: pointer; display: flex; flex-direction: column; gap: 4px; }}
    .prd-item:hover, .prd-item.active {{ background: rgba(56, 189, 248, 0.1); }}
    .prd-item-id {{ font-size: 0.75rem; font-weight: 700; color: var(--accent); }}
    .prd-item-title {{ font-size: 0.85rem; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .editor-pane {{ flex: 1; display: flex; overflow: hidden; }}
    .form-pane {{ flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; border-right: 1px solid var(--border); }}
    .preview-pane {{ flex: 1; overflow-y: auto; padding: 24px; background: #020617; }}
    .form-group {{ display: flex; flex-direction: column; gap: 6px; }}
    label {{ font-size: 0.85rem; font-weight: 600; color: var(--muted); }}
    input, select, textarea {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 10px 12px; border-radius: 6px; font-size: 0.9rem; outline: none; }}
    input:focus, select:focus, textarea:focus {{ border-color: var(--accent); }}
    textarea {{ resize: vertical; min-height: 80px; font-family: inherit; }}
    .outcomes-list {{ display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }}
    .outcome-row {{ display: flex; gap: 8px; align-items: center; background: rgba(30, 41, 59, 0.6); padding: 8px; border-radius: 6px; border: 1px solid var(--border); }}
    .btn-icon {{ background: transparent; border: 1px solid var(--border); color: var(--muted); padding: 4px 8px; border-radius: 4px; cursor: pointer; }}
    .btn-row {{ display: flex; gap: 10px; margin-top: 8px; }}
    button.btn-primary {{ background: var(--accent); color: #000; border: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; cursor: pointer; }}
    button.btn-secondary {{ background: var(--surface); color: var(--text); border: 1px solid var(--border); padding: 10px 18px; border-radius: 6px; font-weight: 600; cursor: pointer; }}
    .alert {{ padding: 10px 14px; border-radius: 6px; font-size: 0.85rem; display: none; }}
    .alert-danger {{ background: var(--danger-bg); border: 1px solid var(--danger); color: #fca5a5; }}
    .alert-success {{ background: #064e3b; border: 1px solid var(--success); color: #86efac; }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>⚡ SpecOps PRD Studio</span>
      <span id="stageBadge" class="status-badge">IDEA</span>
      <span id="dirtyBadge" class="status-badge dirty" style="display:none;">DIRTY</span>
    </div>
    <div class="btn-row" style="margin-top:0;">
      <button class="btn-secondary" onclick="newDraft()">New PRD</button>
      <button class="btn-primary" onclick="saveDraft()">Save Draft</button>
      <button class="btn-secondary" onclick="commitPrd()">Commit to Git</button>
      <button class="btn-secondary" onclick="promoteStage('shaped')">Promote to Shaped</button>
    </div>
  </header>

  <div class="container">
    <div class="sidebar">
      <div class="sidebar-header"><span>PRD REGISTRY</span><button class="btn-icon" onclick="refreshPrdList()">↻</button></div>
      <ul class="prd-list" id="prdList"></ul>
    </div>
    <div class="editor-pane">
      <div class="form-pane">
        <div id="validationAlert" class="alert alert-danger"></div>
        <div id="successAlert" class="alert alert-success"></div>
        <div class="form-group"><label for="prdTitle">PRD Title *</label><input type="text" id="prdTitle" oninput="onFieldChange('title', this.value)"></div>
        <div class="form-group"><label for="prdPersona">Target Persona *</label><select id="prdPersona" onchange="onFieldChange('persona', this.value)"><option value="">-- Select Persona --</option>{personas_options}</select></div>
        <div class="form-group"><label for="prdComponent">Component</label><input type="text" id="prdComponent" value="core" oninput="onFieldChange('component', this.value)"></div>
        <div class="form-group"><label for="prdProblem">Problem Statement *</label><textarea id="prdProblem" oninput="onFieldChange('problem_statement', this.value)"></textarea></div>
        <div class="form-group"><label>Checkable Outcomes *</label><div class="outcomes-list" id="outcomesContainer"></div><div style="display:flex; gap:8px; margin-top:8px;"><input type="text" id="newOutcomeInput" style="flex:1;"><button class="btn-secondary" onclick="addOutcome()">+ Add</button></div></div>
      </div>
      <div class="preview-pane">
        <h2 style="font-size: 1rem; color: var(--muted); margin-bottom:12px; text-transform:uppercase;">Diataxis Live Preview</h2>
        <div id="previewContent"></div>
      </div>
    </div>
  </div>

  <script>
    let studioState = {init_json};
    async function initStudio() {{
      if (!studioState || !studioState.session_id) {{
        try {{
          const res = await fetch("/api/studio/state");
          const data = await res.json();
          if (data.success) studioState = data.state;
        }} catch (e) {{ console.error(e); }}
      }}
      renderForm();
      refreshPrdList();
    }}
    function renderForm() {{
      if (!studioState) return;
      document.getElementById("prdTitle").value = studioState.title || "";
      document.getElementById("prdPersona").value = studioState.persona || "";
      document.getElementById("prdComponent").value = studioState.component || "core";
      document.getElementById("prdProblem").value = studioState.problem_statement || "";
      document.getElementById("stageBadge").innerText = (studioState.stage || "IDEA").toUpperCase();
      document.getElementById("dirtyBadge").style.display = studioState.is_dirty ? "inline-block" : "none";
      renderOutcomes();
      renderPreview();
    }}
    function renderOutcomes() {{
      const container = document.getElementById("outcomesContainer");
      container.innerHTML = "";
      (studioState.outcomes || []).forEach((out, idx) => {{
        const row = document.createElement("div");
        row.className = "outcome-row";
        row.innerHTML = `<span style="color:var(--muted); font-size:0.8rem; font-weight:700;">${{idx + 1}}.</span><span style="flex:1; font-size:0.9rem;">${{out}}</span><button class="btn-icon" onclick="removeOutcome(${{idx}})">✕</button>`;
        container.appendChild(row);
      }});
    }}
    function renderPreview() {{
      const title = studioState.title || "Untitled PRD";
      const persona = studioState.persona || "[Persona]";
      const outcomes = (studioState.outcomes || []).map(o => `<li>${{o}}</li>`).join("");
      document.getElementById("previewContent").innerHTML = `
        <h1 style="color:var(--accent); font-size:1.4rem; margin-bottom:10px;">${{title}}</h1>
        <p style="color:var(--muted); font-size:0.85rem; margin-bottom:14px;"><strong>Target Persona:</strong> ${{persona}}</p>
        <h2 style="font-size:1.1rem; margin-bottom:6px;">Problem Statement</h2>
        <p style="font-size:0.9rem; line-height:1.5; color:#cbd5e1; margin-bottom:16px;">${{studioState.problem_statement || "No statement specified."}}</p>
        <h2 style="font-size:1.1rem; margin-bottom:6px;">Checkable Outcomes</h2>
        <ul style="margin-left:20px; font-size:0.9rem; color:#cbd5e1;">${{outcomes || "<li>No outcomes defined.</li>"}}</ul>
      `;
    }}
    async function onFieldChange(field, val) {{
      try {{
        const res = await fetch("/api/studio/draft/update", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ field, value: val }}) }});
        const data = await res.json();
        if (data.success) {{
          studioState = data.state;
          document.getElementById("dirtyBadge").style.display = studioState.is_dirty ? "inline-block" : "none";
          renderPreview();
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function addOutcome() {{
      const input = document.getElementById("newOutcomeInput");
      const val = input.value.trim();
      if (!val) return;
      try {{
        const res = await fetch("/api/studio/draft/outcome/add", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ outcome: val }}) }});
        const data = await res.json();
        if (data.success) {{
          studioState = data.state;
          input.value = "";
          renderOutcomes();
          renderPreview();
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function removeOutcome(idx) {{
      try {{
        const res = await fetch("/api/studio/draft/outcome/remove", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ index: idx }}) }});
        const data = await res.json();
        if (data.success) {{
          studioState = data.state;
          renderOutcomes();
          renderPreview();
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function refreshPrdList() {{
      try {{
        const res = await fetch("/api/studio/prds");
        const data = await res.json();
        if (data.success) {{
          const list = document.getElementById("prdList");
          list.innerHTML = "";
          data.prds.forEach(p => {{
            const li = document.createElement("li");
            li.className = "prd-item" + (studioState && studioState.active_prd_id === p.prd_id ? " active" : "");
            li.innerHTML = `<div class="prd-item-id">${{p.prd_id}} <span style="color:var(--muted); font-weight:normal;">[${{p.stage}}]</span></div><div class="prd-item-title">${{p.title}}</div>`;
            li.onclick = () => loadPrd(p.prd_id);
            list.appendChild(li);
          }});
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function loadPrd(prdId) {{
      try {{
        const res = await fetch("/api/studio/draft/load", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ prd_id: prdId }}) }});
        const data = await res.json();
        if (data.success) {{
          studioState = data.state;
          renderForm();
          refreshPrdList();
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function newDraft() {{
      try {{
        const res = await fetch("/api/studio/draft/new", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{}}) }});
        const data = await res.json();
        if (data.success) {{
          studioState = data.state;
          renderForm();
          refreshPrdList();
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function saveDraft() {{
      const alert = document.getElementById("validationAlert");
      const success = document.getElementById("successAlert");
      alert.style.display = "none"; success.style.display = "none";
      try {{
        const res = await fetch("/api/studio/draft/save", {{ method: "POST" }});
        const data = await res.json();
        if (data.success) {{
          studioState = data.state;
          success.innerText = "Draft saved successfully!";
          success.style.display = "block";
          renderForm();
          refreshPrdList();
        }} else {{
          alert.innerText = data.error || (data.violations || []).join("; ");
          alert.style.display = "block";
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function commitPrd() {{
      try {{
        const res = await fetch("/api/studio/draft/commit", {{ method: "POST" }});
        const data = await res.json();
        const success = document.getElementById("successAlert");
        if (data.success) {{
          success.innerText = "Committed specification: " + (data.commit_hash || "").slice(0, 7);
          success.style.display = "block";
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    async function promoteStage(stage) {{
      try {{
        const res = await fetch("/api/studio/draft/promote", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ stage }}) }});
        const data = await res.json();
        if (data.success) {{
          studioState = data.state;
          renderForm();
          refreshPrdList();
        }}
      }} catch (e) {{ console.error(e); }}
    }}
    window.onload = initStudio;
  </script>
</body>
</html>
"""
