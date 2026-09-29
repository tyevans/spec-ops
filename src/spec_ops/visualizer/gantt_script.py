"""Client-side Gantt timeline view script for SpecOps visualizer."""
from __future__ import annotations

GANTT_JS = r"""
  // --- Gantt Timeline View ---
  function renderGanttView() {
    const tasks = getFilteredTasks();
    const groups = {};

    tasks.forEach(t => {
      let g = "Horizon";
      if (filterState.groupBy === "release") {
        g = t.target_release ? `Release ${t.target_release}` : "Unscheduled";
      } else {
        g = t.target_bc ? `BC: ${t.target_bc}` : "General";
      }
      if (!groups[g]) groups[g] = [];
      groups[g].push(t);
    });

    if (Object.keys(groups).length === 0) {
      return `<div class="empty-state">No deliverables match the active filter criteria.</div>`;
    }

    return `
      <div style="display:flex; flex-direction:column; gap:20px;">
        ${Object.entries(groups).map(([grp, items]) => {
          const doneCount = items.filter(x => x.status === "Complete").length;
          const pct = Math.round((doneCount / items.length) * 100);

          return `
            <div class="gantt-group-card">
              <div class="gantt-group-header">
                <div>
                  <h3 style="font-size:0.95rem; font-weight:700; color:#fff;">${grp}</h3>
                  <span style="font-size:0.75rem; color:var(--text-muted);">${items.length} tasks · ${pct}% delivered</span>
                </div>
                <div style="width:140px; height:6px; background:rgba(255,255,255,0.08); border-radius:9999px; overflow:hidden;">
                  <div style="width:${pct}%; height:100%; background:#10b981; border-radius:9999px;"></div>
                </div>
              </div>

              <div class="gantt-items-list">
                ${items.map(t => {
                  const statusCls = t.status === "Complete" ? "status-complete" : (t.status === "Refined" ? "status-refined" : "status-proposed");
                  const progress = t.status === "Complete" ? 100 : (t.status === "Refined" ? 60 : 20);

                  return `
                    <div class="gantt-item-row" onclick="openDrawer('${escapeHtml(t.id)}')">
                      <div style="display:flex; align-items:center; gap:10px; width:220px; flex-shrink:0;">
                        <span class="entity-pill ${statusCls}">${escapeHtml(t.id)}</span>
                        <span style="font-size:0.75rem; color:var(--text-muted); font-mono">${escapeHtml(t.status)}</span>
                      </div>
                      <div style="flex:1; min-width:0; padding-right:15px;">
                        <div style="font-size:0.84rem; font-weight:600; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(t.title)}</div>
                        <div style="font-size:0.74rem; color:var(--text-muted); margin-top:2px;">
                          ${t.target_bc ? `<span style="color:#67e8f9; margin-right:8px;">BC: ${escapeHtml(t.target_bc)}</span>` : ""}
                          ${t.governing_prds && t.governing_prds.length ? `<span>PRD: ${t.governing_prds.map(escapeHtml).join(", ")}</span>` : ""}
                        </div>
                      </div>
                      <div style="width:180px; flex-shrink:0;">
                        <div class="gantt-bar-container">
                          <div class="gantt-bar ${statusCls}" style="width:${progress}%;"></div>
                        </div>
                      </div>
                    </div>`;
                }).join("")}
              </div>
            </div>`;
        }).join("")}
      </div>
    `;
  }
"""
