"""Unified multi-perspective project matrix view and relational cross-filtering."""

from __future__ import annotations

MATRIX_CSS = r"""
.matrix-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}
.matrix-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  background: var(--bg-surface, #1e293b);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle, #334155);
}
.matrix-table-wrap {
  overflow-x: auto;
  background: var(--bg-surface, #1e293b);
  border-radius: 8px;
  border: 1px solid var(--border-subtle, #334155);
}
.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
  color: #e2e8f0;
  text-align: left;
}
.matrix-table th {
  background: rgba(15, 23, 42, 0.7);
  padding: 10px 14px;
  font-weight: 700;
  color: #94a3b8;
  border-bottom: 2px solid var(--border-subtle, #334155);
  white-space: nowrap;
}
.matrix-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(51, 65, 85, 0.5);
  vertical-align: middle;
}
.matrix-table tr:hover {
  background: rgba(51, 65, 85, 0.25);
}
.matrix-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  margin: 1px 2px;
}
.matrix-badge-complete { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.4); }
.matrix-badge-refined { background: rgba(245, 158, 11, 0.2); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.4); }
.matrix-badge-proposed { background: rgba(139, 92, 246, 0.2); color: #c4b5fd; border: 1px solid rgba(139, 92, 246, 0.4); }
.matrix-badge-prd { background: rgba(244, 63, 94, 0.2); color: #fda4af; border: 1px solid rgba(244, 63, 94, 0.4); }
.matrix-badge-adr { background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); }
.matrix-badge-story { background: rgba(6, 182, 212, 0.2); color: #67e8f9; border: 1px solid rgba(6, 182, 212, 0.4); }
.matrix-badge-persona { background: rgba(245, 158, 11, 0.2); color: #fde68a; border: 1px solid rgba(245, 158, 11, 0.4); }
.matrix-badge-bc { background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3); }
.matrix-badge-release { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }
"""

MATRIX_JS = r"""
  var matrixFilterState = window.matrixFilterState = window.matrixFilterState || {
    query: "",
    status: "all",
    persona: "all",
    milestone: "all",
    bc: "all"
  };

  window.setMatrixFilter = function(key, val) {
    matrixFilterState[key] = val;
    renderActiveView();
  };

  window.renderMatrixView = function() {
    const tasks = data.tasks || [];
    const stories = data.stories || [];
    const prds = data.prds || [];
    const adrs = data.adrs || [];
    const personas = data.personas || [];

    // Build lookup maps
    const storyMap = new Map(stories.map(s => [s.id, s]));
    const prdMap = new Map(prds.map(p => [p.id, p]));
    const personaMap = new Map(personas.map(p => [p.name, p]));

    const q = (matrixFilterState.query || "").toLowerCase().trim();
    const stFilter = matrixFilterState.status;
    const personaFilter = matrixFilterState.persona;
    const milestoneFilter = matrixFilterState.milestone;
    const bcFilter = matrixFilterState.bc;

    // Filter items
    const rows = tasks.filter(t => {
      if (stFilter !== "all" && t.status !== stFilter) return false;
      if (bcFilter !== "all" && t.target_bc !== bcFilter) return false;
      if (milestoneFilter !== "all" && (t.target_release || "Unscheduled") !== milestoneFilter) return false;

      // Find story & persona
      let linkedPersona = "";
      if (t.governing_stories && t.governing_stories.length > 0) {
        const s = storyMap.get(t.governing_stories[0]);
        if (s && s.persona) linkedPersona = s.persona;
      }
      if (!linkedPersona && t.governing_prds && t.governing_prds.length > 0) {
        const p = prdMap.get(t.governing_prds[0]);
        if (p && p.target_persona) linkedPersona = p.target_persona;
      }
      if (personaFilter !== "all" && linkedPersona !== personaFilter) return false;

      if (q) {
        const searchCorpus = [
          t.id,
          t.title,
          t.status,
          t.target_bc || "",
          t.target_release || "",
          linkedPersona,
          (t.governing_prds || []).join(" "),
          (t.governing_stories || []).join(" "),
          (t.governing_adrs || []).join(" "),
          t.body || ""
        ].join(" ").toLowerCase();
        if (!searchCorpus.includes(q)) return false;
      }
      return true;
    });

    // Collect filter option values
    const allStatuses = ["Complete", "Refined", "Proposed"];
    const allPersonas = Array.from(new Set(personas.map(p => p.name).filter(Boolean))).sort();
    const allMilestones = Array.from(new Set(tasks.map(t => t.target_release || "Unscheduled"))).sort();
    const allBcs = Array.from(new Set(tasks.map(t => t.target_bc).filter(Boolean))).sort();

    return `
      <div class="matrix-container">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <h2 style="font-size:1.1rem; font-weight:700; color:#fff; margin-bottom:2px;">Project Traceability Matrix</h2>
            <p style="font-size:0.75rem; color:var(--text-muted, #94a3b8);">Unified multi-dimensional mapping of Personas, PRDs, Stories, Tasks, ADRs, and Releases.</p>
          </div>
          <span style="font-size:0.8rem; font-weight:600; color:#38bdf8;">${rows.length} of ${tasks.length} deliverables visible</span>
        </div>

        <div class="matrix-filter-bar">
          <input type="text" class="filter-input" placeholder="Search matrix (task, story, ADR, persona)..."
            value="${escapeHtml(matrixFilterState.query)}"
            oninput="window.setMatrixFilter('query', this.value)" style="min-width:220px;">

          <select class="filter-select" onchange="window.setMatrixFilter('status', this.value)">
            <option value="all" ${stFilter === 'all' ? 'selected' : ''}>All Statuses</option>
            ${allStatuses.map(s => `<option value="${escapeHtml(s)}" ${stFilter === s ? 'selected' : ''}>${escapeHtml(s)}</option>`).join("")}
          </select>

          <select class="filter-select" onchange="window.setMatrixFilter('persona', this.value)">
            <option value="all" ${personaFilter === 'all' ? 'selected' : ''}>All Personas</option>
            ${allPersonas.map(p => `<option value="${escapeHtml(p)}" ${personaFilter === p ? 'selected' : ''}>${escapeHtml(p)}</option>`).join("")}
          </select>

          <select class="filter-select" onchange="window.setMatrixFilter('milestone', this.value)">
            <option value="all" ${milestoneFilter === 'all' ? 'selected' : ''}>All Milestones</option>
            ${allMilestones.map(m => `<option value="${escapeHtml(m)}" ${milestoneFilter === m ? 'selected' : ''}>${escapeHtml(m)}</option>`).join("")}
          </select>

          <select class="filter-select" onchange="window.setMatrixFilter('bc', this.value)">
            <option value="all" ${bcFilter === 'all' ? 'selected' : ''}>All Bounded Contexts</option>
            ${allBcs.map(bc => `<option value="${escapeHtml(bc)}" ${bcFilter === bc ? 'selected' : ''}>${escapeHtml(bc)}</option>`).join("")}
          </select>
        </div>

        <div class="matrix-table-wrap">
          <table class="matrix-table">
            <thead>
              <tr>
                <th>Deliverable Task</th>
                <th>Status</th>
                <th>Bounded Context</th>
                <th>Milestone</th>
                <th>Persona</th>
                <th>Governing PRD</th>
                <th>Governing Story</th>
                <th>Governing ADRs</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(t => {
                const stClass = t.status === "Complete" ? "matrix-badge-complete" : (t.status === "Refined" ? "matrix-badge-refined" : "matrix-badge-proposed");

                let personaName = "";
                let personaId = "";
                if (t.governing_stories && t.governing_stories.length > 0) {
                  const s = storyMap.get(t.governing_stories[0]);
                  if (s && s.persona) {
                    personaName = s.persona;
                    const p = personaMap.get(s.persona);
                    if (p) personaId = p.id;
                  }
                }
                if (!personaName && t.governing_prds && t.governing_prds.length > 0) {
                  const p = prdMap.get(t.governing_prds[0]);
                  if (p && p.target_persona) {
                    personaName = p.target_persona;
                    const per = personaMap.get(p.target_persona);
                    if (per) personaId = per.id;
                  }
                }

                return `
                  <tr>
                    <td>
                      <span class="matrix-badge ${stClass}" onclick="openDrawer('${escapeHtml(t.id)}')">${escapeHtml(t.id)}</span>
                      <strong style="cursor:pointer; color:#f8fafc;" onclick="openDrawer('${escapeHtml(t.id)}')">${escapeHtml(t.title)}</strong>
                    </td>
                    <td><span class="matrix-badge ${stClass}">${escapeHtml(t.status)}</span></td>
                    <td>${t.target_bc ? `<span class="matrix-badge matrix-badge-bc">${escapeHtml(t.target_bc)}</span>` : '<span style="color:#64748b">—</span>'}</td>
                    <td><span class="matrix-badge matrix-badge-release">${escapeHtml(t.target_release || 'Unscheduled')}</span></td>
                    <td>${personaName ? `<span class="matrix-badge matrix-badge-persona" onclick="openDrawer('${escapeHtml(personaId || personaName)}')">${escapeHtml(personaName)}</span>` : '<span style="color:#64748b">—</span>'}</td>
                    <td>${(t.governing_prds || []).map(pid => `<span class="matrix-badge matrix-badge-prd" onclick="openDrawer('${escapeHtml(pid)}')">${escapeHtml(pid)}</span>`).join(" ") || '<span style="color:#64748b">—</span>'}</td>
                    <td>${(t.governing_stories || []).map(sid => `<span class="matrix-badge matrix-badge-story" onclick="openDrawer('${escapeHtml(sid)}')">${escapeHtml(sid)}</span>`).join(" ") || '<span style="color:#64748b">—</span>'}</td>
                    <td>${(t.governing_adrs || []).map(aid => `<span class="matrix-badge matrix-badge-adr" onclick="openDrawer('${escapeHtml(aid)}')">${escapeHtml(aid)}</span>`).join(" ") || '<span style="color:#64748b">—</span>'}</td>
                  </tr>
                `;
              }).join("")}
              ${rows.length === 0 ? '<tr><td colspan="8" style="text-align:center; padding:30px; color:#64748b;">No matching items found for active matrix filter.</td></tr>' : ''}
            </tbody>
          </table>
        </div>
      </div>
    `;
  };
"""
