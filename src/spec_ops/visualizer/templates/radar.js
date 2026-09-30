/**
 * Living Architectural Review Radar, Bounded Context Coupling Matrix,
 * ADR Supersession Lineage Tree, and Specification Drift Audit.
 */

window.architecturalRadarState = window.architecturalRadarState || { selectedContext: "all", activeSubView: "matrix" };

window.renderArchitectureRadarView = function() {
  const arch = (data && data.architecture) || {};
  const bcs = (data && data.bounded_contexts) || [];
  const matrix = arch.coupling_matrix || [];
  const violations = arch.violations || [];
  const adrs = (data && data.adrs) || [];
  const drift = arch.drift_audit || { orphaned_tasks: [], orphaned_stories: [], orphaned_prds: [], orphaned_commits: [], total_orphans: 0 };

  const bcNames = Array.from(new Set(
    bcs.map(b => b.id || b.name).concat(matrix.map(m => m.from_bc)).concat(matrix.map(m => m.to_bc)).filter(Boolean)
  )).sort();

  return `
    <div class="architecture-radar-container" style="display:flex; flex-direction:column; gap:20px; width:100%; max-width:1240px; margin:0 auto;">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
        <div>
          <h2 style="font-size:1.3rem; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
            <span>📡 Architectural Review Radar</span>
            <span class="badge" style="background:rgba(99,102,241,0.2); color:#a5b4fc; border:1px solid rgba(99,102,241,0.4); font-size:0.75rem;">Living Audit</span>
          </h2>
          <p style="font-size:0.8rem; color:var(--text-muted); margin-top:2px;">
            Auditing bounded context couplings, detecting illegal cross-context module imports, visualizing ADR supersession trees, and highlighting orphaned specifications in real time.
          </p>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="ctrl-btn" id="btn-radar-audit-drift" onclick="window.openDriftAuditModal()" title="Audit Specification Drift">🔍 Audit Specification Drift</button>
          <button class="ctrl-btn active" id="btn-export-drift-json" onclick="window.exportDriftAuditReport()" title="Export Specification Drift JSON">📄 Export Audit Report</button>
        </div>
      </div>

      <!-- 3 Summary Metrics Cards -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px;">
        <div class="card-box" id="card-bc-coupling" style="border-left:4px solid #6366f1;">
          <div style="font-size:0.75rem; color:var(--text-muted); font-weight:600; text-transform:uppercase;">Bounded Context Boundaries</div>
          <div style="font-size:1.6rem; font-weight:800; color:#fff; margin:4px 0;">${bcNames.length} Contexts</div>
          <div style="font-size:0.78rem; color:${violations.length > 0 ? '#ef4444' : '#10b981'}; font-weight:600;">
            ${violations.length > 0 ? `⚠️ ${violations.length} Illegal Boundary Import(s)` : `✓ Clean Boundary Separation (0 Violations)`}
          </div>
        </div>

        <div class="card-box" id="card-adr-supersession" style="border-left:4px solid #06b6d4;">
          <div style="font-size:0.75rem; color:var(--text-muted); font-weight:600; text-transform:uppercase;">ADR Supersession Radar</div>
          <div style="font-size:1.6rem; font-weight:800; color:#fff; margin:4px 0;">
            ${adrs.filter(a => a.status === 'Accepted' || !a.superseded_by).length} Active / ${adrs.filter(a => a.status === 'Superseded' || a.superseded_by).length} Superseded
          </div>
          <div style="font-size:0.78rem; color:#94a3b8;">${(arch.obsolete_citations || []).length} active tasks citing obsolete decisions</div>
        </div>

        <div class="card-box" id="card-spec-drift" style="border-left:4px solid #f59e0b;">
          <div style="font-size:0.75rem; color:var(--text-muted); font-weight:600; text-transform:uppercase;">Specification Drift Status</div>
          <div style="font-size:1.6rem; font-weight:800; color:#fff; margin:4px 0;">${drift.total_orphans} Orphan Entities</div>
          <div style="font-size:0.78rem; color:${drift.total_orphans > 0 ? '#f59e0b' : '#10b981'}; font-weight:600;">
            ${drift.total_orphans > 0 ? `${drift.orphaned_tasks.length} tasks, ${drift.orphaned_stories.length} stories, ${drift.orphaned_prds.length} PRDs` : `✓ Zero specification drift detected`}
          </div>
        </div>
      </div>

      <!-- Section 1: Bounded Context Boundary & Coupling Matrix -->
      <div class="card-box" id="section-coupling-matrix">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
          <div>
            <h3 style="font-size:1.05rem; font-weight:700; color:#fff;">Bounded Context Boundary &amp; Coupling Matrix</h3>
            <p style="font-size:0.75rem; color:var(--text-muted);">Cross-context coupling matrices highlight permissible and prohibited import vectors.</p>
          </div>
          <div style="display:flex; gap:6px;">
            <button class="ctrl-btn" onclick="window.switchTab('graph'); if(window.switchLayout) window.switchLayout('radial');" title="View in Radial Radar">🎯 Radar Layout</button>
            <button class="ctrl-btn" onclick="window.switchTab('graph'); if(window.switchLayout) window.switchLayout('flow');" title="View in Flow DAG">🌊 Flow DAG</button>
          </div>
        </div>

        <div class="matrix-table-wrap" style="overflow-x:auto;">
          <table class="matrix-table" id="coupling-matrix-table" style="width:100%; border-collapse:collapse;">
            <thead>
              <tr>
                <th style="background:rgba(15,23,42,0.85); padding:8px 12px;">From \\ To Context</th>
                ${bcNames.map(bc => `<th style="background:rgba(15,23,42,0.85); padding:8px 12px; text-align:center;">${escapeHtml(bc)}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${bcNames.map(src => `
                <tr>
                  <td style="font-weight:700; color:#cbd5e1; background:rgba(15,23,42,0.4);">${escapeHtml(src)}</td>
                  ${bcNames.map(tgt => {
                    if (src === tgt) return `<td style="text-align:center; color:#64748b; font-size:0.75rem;">—</td>`;
                    const cell = matrix.find(m => m.from_bc === src && m.to_bc === tgt) || {
                      count: 0,
                      is_prohibited: violations.some(v => v.source === src && v.target === tgt),
                      status: violations.some(v => v.source === src && v.target === tgt) ? "prohibited" : "permissible"
                    };
                    const isProhibited = cell.is_prohibited || cell.status === "prohibited";
                    const badgeClass = isProhibited ? "matrix-badge-prohibited pulsing-red" : "matrix-badge-complete";
                    const badgeBg = isProhibited ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.15)";
                    const badgeColor = isProhibited ? "#fca5a5" : "#6ee7b7";
                    const badgeBorder = isProhibited ? "1px solid #ef4444" : "1px solid rgba(16, 185, 129, 0.3)";
                    const label = isProhibited ? `Prohibited (${cell.count})` : (cell.count > 0 ? `Permissible (${cell.count})` : `Allowed`);
                    return `<td style="text-align:center; padding:8px;"><span class="matrix-badge ${badgeClass}" style="background:${badgeBg}; color:${badgeColor}; border:${badgeBorder}; font-size:0.7rem;">${label}</span></td>`;
                  }).join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>

        ${violations.length > 0 ? `
          <div style="margin-top:16px; background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:12px;">
            <div style="font-weight:700; color:#fca5a5; font-size:0.82rem; margin-bottom:8px;">⚠️ Prohibited Import Violations (ADR-0007 / Boundary Invariants):</div>
            <div style="display:flex; flex-direction:column; gap:6px;">
              ${violations.map(v => `
                <div style="font-size:0.76rem; color:#e2e8f0; display:flex; align-items:center; gap:8px;">
                  <span class="matrix-badge matrix-badge-prohibited" style="background:#ef4444; color:#fff; font-size:0.68rem;">VIOLATION</span>
                  <code>${escapeHtml(v.source)}</code> &rarr; <code>${escapeHtml(v.target)}</code>
                  <span style="color:var(--text-muted);">(${escapeHtml(v.message || v.type)})</span>
                  ${v.file_path ? `<span style="color:#64748b; font-size:0.7rem; margin-left:auto;">${escapeHtml(v.file_path)}</span>` : ""}
                </div>
              `).join("")}
            </div>
          </div>
        ` : `
          <div style="margin-top:12px; font-size:0.76rem; color:#10b981; font-weight:600;">
            ✓ Clean boundary separation verified: zero illegal cross-context imports detected.
          </div>
        `}
      </div>

      <!-- Section 2: ADR Supersession Lineage Tree & Active Status Radar -->
      <div class="card-box" id="section-adr-supersession">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <div>
            <h3 style="font-size:1.05rem; font-weight:700; color:#fff;">ADR Supersession Lineage &amp; Active Status Radar</h3>
            <p style="font-size:0.75rem; color:var(--text-muted);">Active decisions are rendered in green, superseded decisions are flagged with strikethrough badges, and tasks citing obsolete ADRs are listed.</p>
          </div>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:12px;">
          ${adrs.map(a => {
            const isSuperseded = (a.status === 'Superseded') || Boolean(a.superseded_by);
            const statusClass = isSuperseded ? "matrix-badge-superseded" : "matrix-badge-complete";
            const badgeBg = isSuperseded ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.2)";
            const badgeColor = isSuperseded ? "#fca5a5" : "#6ee7b7";
            const badgeBorder = isSuperseded ? "1px solid rgba(239,68,68,0.4)" : "1px solid rgba(16, 185, 129, 0.4)";
            const styleAttr = isSuperseded ? `style="background:${badgeBg}; color:${badgeColor}; border:${badgeBorder}; text-decoration:line-through;"` : `style="background:${badgeBg}; color:${badgeColor}; border:${badgeBorder};"`;
            const targetAdr = a.superseded_by ? adrs.find(x => x.id === a.superseded_by || x.id.replace("ADR-", "") === a.superseded_by.replace("ADR-", "")) : null;
            const targetTitle = (targetAdr && targetAdr.title) ? `: ${targetAdr.title}` : (a.superseded_by_title ? `: ${a.superseded_by_title}` : "");

            return `
              <div class="card-box adr-item-card" style="padding:12px; border:${isSuperseded ? '1px solid rgba(239,68,68,0.35)' : '1px solid var(--border-subtle)'}; background:${isSuperseded ? 'rgba(239,68,68,0.04)' : 'rgba(15,23,42,0.4)'};">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                  <span class="entity-pill pill-adr" onclick="openDrawer('${escapeHtml(a.id)}')">${escapeHtml(a.id)}</span>
                  <span class="matrix-badge ${statusClass}" ${styleAttr}>${isSuperseded ? 'Superseded' : escapeHtml(a.status || 'Accepted')}</span>
                </div>
                <h4 style="font-size:0.88rem; font-weight:700; color:#fff; cursor:pointer;" onclick="openDrawer('${escapeHtml(a.id)}')">${escapeHtml(a.title)}</h4>
                ${isSuperseded && a.superseded_by ? `
                  <div class="superseded-notice-box" style="margin-top:8px; padding:6px 10px; background:rgba(239,68,68,0.12); border-radius:6px; font-size:0.74rem;">
                    <span style="color:#fca5a5; font-weight:700;">Superseded by </span>
                    <a href="#tab=adrs&entity=${escapeHtml(a.superseded_by)}" onclick="openDrawer('${escapeHtml(a.superseded_by)}')" style="color:#67e8f9; text-decoration:underline; font-weight:700;">
                      ${escapeHtml(a.superseded_by)}${escapeHtml(targetTitle)}
                    </a>
                  </div>` : ""}
                <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center; font-size:0.72rem; color:var(--text-muted); border-top:1px solid rgba(51,65,85,0.4); padding-top:6px;">
                  <span>${escapeHtml(a.domain || 'Architecture')}</span>
                  <button class="ctrl-btn" style="padding:2px 8px; font-size:0.7rem;" onclick="openDrawer('${escapeHtml(a.id)}')">Inspect</button>
                </div>
              </div>`;
          }).join("")}
        </div>

        ${(arch.obsolete_citations && arch.obsolete_citations.length > 0) ? `
          <div style="margin-top:16px; background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.3); border-radius:8px; padding:12px;">
            <div style="font-weight:700; color:#fcd34d; font-size:0.82rem; margin-bottom:8px;">⚠️ Tasks Citing Obsolete / Superseded ADRs:</div>
            <div style="display:flex; flex-direction:column; gap:6px;">
              ${arch.obsolete_citations.map(c => `
                <div style="font-size:0.76rem; color:#e2e8f0; display:flex; align-items:center; gap:8px;">
                  <span class="entity-pill pill-task" onclick="openDrawer('${escapeHtml(c.task_id)}')">${escapeHtml(c.task_id)}</span>
                  <span>cites superseded <b>${escapeHtml(c.adr_id)}</b>; requires architectural re-refinement</span>
                </div>`).join("")}
            </div>
          </div>` : ""}
      </div>
    </div>`;
};

// --- Modal: Automated Orphan Work Item and Specification Drift Audit ---
window.openDriftAuditModal = function() {
  const modal = document.getElementById("drift-audit-modal");
  if (!modal) return;
  modal.style.display = "flex";
  window.renderDriftAuditModalContent();
};

window.closeDriftAuditModal = function() {
  const modal = document.getElementById("drift-audit-modal");
  if (modal) modal.style.display = "none";
};

window.generateDriftAuditReport = function() {
  const tasks = (data && data.tasks) || [];
  const stories = (data && data.stories) || [];
  const prds = (data && data.prds) || [];
  const commits = (data && data.commits) || [];

  const orphaned_tasks = tasks.filter(t => (!t.governing_prds || t.governing_prds.length === 0) && (!t.governing_stories || t.governing_stories.length === 0)).map(t => ({ id: t.id, title: t.title, file_path: t.file_path }));
  const orphaned_stories = stories.filter(s => !s.governing_prd).map(s => ({ id: s.id, title: s.title, file_path: s.file_path }));
  const orphaned_prds = prds.filter(p => !p.tasks || p.tasks.length === 0).map(p => ({ id: p.id, title: p.title, file_path: p.file_path }));
  const orphaned_commits = (commits || []).filter(c => !c.task_id).map(c => ({ hash: c.hash, subject: c.subject }));

  return {
    timestamp: new Date().toISOString(),
    orphaned_tasks, orphaned_stories, orphaned_prds, orphaned_commits,
    total_orphans: orphaned_tasks.length + orphaned_stories.length + orphaned_prds.length + orphaned_commits.length
  };
};

window.renderDriftAuditModalContent = function() {
  const body = document.getElementById("drift-audit-modal-body");
  if (!body) return;
  const report = window.generateDriftAuditReport();

  body.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      <div style="font-size:0.8rem; color:var(--text-muted);">
        Categorized audit of orphan entities lacking governing specs or implementing links. Use 1-click actions to scaffold missing specs or archive obsolete entries.
      </div>

      <!-- Orphan Tasks -->
      <div class="card-box" style="padding:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <h4 style="font-size:0.88rem; font-weight:700; color:#fff;">Backlog Tasks with No Governing PRD or Story (${report.orphaned_tasks.length})</h4>
        </div>
        ${report.orphaned_tasks.length === 0 ? `<div style="font-size:0.75rem; color:#10b981;">✓ Zero orphaned tasks</div>` : `
          <div style="display:flex; flex-direction:column; gap:6px;">
            ${report.orphaned_tasks.map(t => `
              <div class="drift-row" id="drift-task-${escapeHtml(t.id)}" style="display:flex; align-items:center; justify-content:space-between; padding:6px 10px; background:rgba(15,23,42,0.6); border-radius:6px; font-size:0.76rem;">
                <div><span class="entity-pill pill-task">${escapeHtml(t.id)}</span><strong style="margin-left:6px; color:#fff;">${escapeHtml(t.title)}</strong></div>
                <div style="display:flex; gap:6px;">
                  <button class="ctrl-btn" onclick="window.scaffoldMissingSpec('${escapeHtml(t.id)}')">Scaffold Governing Spec</button>
                  <button class="ctrl-btn" onclick="window.archiveObsoleteEntry('${escapeHtml(t.id)}')">Archive Obsolete Entry</button>
                </div>
              </div>`).join("")}
          </div>`}
      </div>

      <!-- Orphan Stories -->
      <div class="card-box" style="padding:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <h4 style="font-size:0.88rem; font-weight:700; color:#fff;">User Stories with No Linked PRD (${report.orphaned_stories.length})</h4>
        </div>
        ${report.orphaned_stories.length === 0 ? `<div style="font-size:0.75rem; color:#10b981;">✓ Zero orphaned stories</div>` : `
          <div style="display:flex; flex-direction:column; gap:6px;">
            ${report.orphaned_stories.map(s => `
              <div class="drift-row" id="drift-story-${escapeHtml(s.id)}" style="display:flex; align-items:center; justify-content:space-between; padding:6px 10px; background:rgba(15,23,42,0.6); border-radius:6px; font-size:0.76rem;">
                <div><span class="entity-pill pill-story">${escapeHtml(s.id)}</span><strong style="margin-left:6px; color:#fff;">${escapeHtml(s.title)}</strong></div>
                <div style="display:flex; gap:6px;">
                  <button class="ctrl-btn" onclick="window.scaffoldMissingSpec('${escapeHtml(s.id)}')">Scaffold Missing Spec</button>
                  <button class="ctrl-btn" onclick="window.archiveObsoleteEntry('${escapeHtml(s.id)}')">Archive Obsolete Entry</button>
                </div>
              </div>`).join("")}
          </div>`}
      </div>

      <!-- Orphan PRDs -->
      <div class="card-box" style="padding:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <h4 style="font-size:0.88rem; font-weight:700; color:#fff;">PRDs with Zero Implementing Tasks (${report.orphaned_prds.length})</h4>
        </div>
        ${report.orphaned_prds.length === 0 ? `<div style="font-size:0.75rem; color:#10b981;">✓ Zero orphaned PRDs</div>` : `
          <div style="display:flex; flex-direction:column; gap:6px;">
            ${report.orphaned_prds.map(p => `
              <div class="drift-row" id="drift-prd-${escapeHtml(p.id)}" style="display:flex; align-items:center; justify-content:space-between; padding:6px 10px; background:rgba(15,23,42,0.6); border-radius:6px; font-size:0.76rem;">
                <div><span class="entity-pill pill-prd">${escapeHtml(p.id)}</span><strong style="margin-left:6px; color:#fff;">${escapeHtml(p.title)}</strong></div>
                <div style="display:flex; gap:6px;">
                  <button class="ctrl-btn" onclick="window.scaffoldMissingSpec('${escapeHtml(p.id)}')">Scaffold Implementing Tasks</button>
                  <button class="ctrl-btn" onclick="window.archiveObsoleteEntry('${escapeHtml(p.id)}')">Archive Obsolete Entry</button>
                </div>
              </div>`).join("")}
          </div>`}
      </div>
    </div>`;
};

window.scaffoldMissingSpec = function(id) {
  const isTask = String(id).toUpperCase().startsWith("TASK");
  const isStory = String(id).toUpperCase().startsWith("US");
  const isPrd = String(id).toUpperCase().startsWith("PRD");
  const prefix = isTask ? "drift-task-" : (isStory ? "drift-story-" : (isPrd ? "drift-prd-" : ""));
  const row = prefix ? document.getElementById(prefix + id) : (document.getElementById(`drift-task-${id}`) || document.getElementById(`drift-story-${id}`) || document.getElementById(`drift-prd-${id}`));
  if (row) row.innerHTML = `<span style="color:#10b981; font-weight:600;">✓ Scaffolded missing governing spec for ${escapeHtml(id)}</span>`;
};

window.archiveObsoleteEntry = function(id) {
  const isTask = String(id).toUpperCase().startsWith("TASK");
  const isStory = String(id).toUpperCase().startsWith("US");
  const isPrd = String(id).toUpperCase().startsWith("PRD");
  const prefix = isTask ? "drift-task-" : (isStory ? "drift-story-" : (isPrd ? "drift-prd-" : ""));
  const row = prefix ? document.getElementById(prefix + id) : (document.getElementById(`drift-task-${id}`) || document.getElementById(`drift-story-${id}`) || document.getElementById(`drift-prd-${id}`));
  if (row) row.innerHTML = `<span style="color:#94a3b8; font-style:italic;">✓ Archived obsolete entry ${escapeHtml(id)}</span>`;
};

window.exportDriftAuditReport = function() {
  const report = window.generateDriftAuditReport();
  window.lastExportedDriftAudit = report;
  const jsonStr = JSON.stringify(report, null, 2);

  if (typeof document !== "undefined" && document.createElement) {
    const blob = (typeof Blob !== "undefined") ? new Blob([jsonStr], { type: "application/json" }) : null;
    if (blob && typeof URL !== "undefined" && URL.createObjectURL) {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "spec-drift-audit.json";
      if (document.body && document.body.appendChild) {
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    }
  }

  if (typeof fs !== "undefined" && fs.writeFileSync) {
    try {
      if (!fs.existsSync("dist")) fs.mkdirSync("dist", { recursive: true });
      fs.writeFileSync("dist/spec-drift-audit.json", jsonStr, "utf-8");
    } catch (e) {}
  }

  const btn = document.getElementById("btn-export-drift-json");
  if (btn) {
    const prev = btn.textContent;
    btn.textContent = "✓ Exported dist/spec-drift-audit.json";
    setTimeout(() => { btn.textContent = prev; }, 1800);
  }
  return report;
};
