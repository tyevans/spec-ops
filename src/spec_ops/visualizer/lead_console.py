"""Lead console script and fleet telemetry harvester for SpecOps."""

from __future__ import annotations

from typing import Any

from ..config.models import SpecOpsConfig
from .telemetry_script import aggregate_fleet_telemetry, harvest_fleet_telemetry

LEAD_CONSOLE_CSS = r"""
.lead-console-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}
.rescue-banner {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(185, 28, 28, 0.3));
  border: 2px solid #f59e0b;
  border-radius: 8px;
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.15);
}
.rescue-banner-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.rescue-banner-title {
  color: #fde68a;
  font-weight: 700;
  font-size: 0.95rem;
}
.fleet-grid-wrap {
  background: var(--bg-surface, #1e293b);
  border-radius: 8px;
  border: 1px solid var(--border-subtle, #334155);
  overflow-x: auto;
}
.fleet-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
  color: #e2e8f0;
  text-align: left;
}
.fleet-table th {
  background: rgba(15, 23, 42, 0.7);
  padding: 10px 14px;
  font-weight: 700;
  color: #94a3b8;
  border-bottom: 2px solid var(--border-subtle, #334155);
  white-space: nowrap;
}
.fleet-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(51, 65, 85, 0.5);
  vertical-align: middle;
}
.row-stalled {
  border: 2px solid #f59e0b !important;
  background: rgba(245, 158, 11, 0.08) !important;
}
.status-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
}
.status-executing { background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.4); }
.status-healing { background: rgba(245, 158, 11, 0.2); color: #fde68a; border: 1px solid rgba(245, 158, 11, 0.4); }
.status-stalled { background: rgba(239, 68, 68, 0.25); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.5); }
.rescue-panel {
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.worktree-inspect-box {
  background: #090d16;
  border-radius: 6px;
  padding: 12px;
  font-family: monospace;
  font-size: 0.75rem;
  color: #cbd5e1;
  max-height: 250px;
  overflow-y: auto;
  white-space: pre-wrap;
  border: 1px solid #1e293b;
}
"""

LEAD_CONSOLE_JS = r"""
  window.takeoverTask = function(taskId, btnElem) {
    const cmd = "spec-ops rescue " + taskId;
    const nav = (typeof window !== "undefined" && window.navigator && window.navigator.clipboard) ? window.navigator : (typeof navigator !== "undefined" ? navigator : null);
    
    function onCopied() {
      if (btnElem) {
        const orig = btnElem.textContent;
        btnElem.textContent = "✓ Copied Command!";
        btnElem.style.background = "#10b981";
        setTimeout(() => {
          btnElem.textContent = orig;
          btnElem.style.background = "";
        }, 2000);
      }
      if (typeof openDrawer === "function") {
        openDrawer(taskId);
      }
      return cmd;
    }

    if (nav && nav.clipboard && nav.clipboard.writeText) {
      return nav.clipboard.writeText(cmd).then(onCopied);
    } else if (typeof prompt === "function") {
      prompt("Copy CLI rescue command:", cmd);
      return Promise.resolve(onCopied());
    }
    return Promise.resolve(onCopied());
  };

  window.inspectWorktree = function(taskId) {
    const box = document.getElementById("worktree-log-display-" + taskId);
    if (box) {
      box.style.display = box.style.display === "none" ? "table-row" : "none";
    }
    if (typeof openDrawer === "function") {
      openDrawer(taskId);
    }
  };

  window.renderWorktreeTelemetryCard = function(t) {
    const fleet = (typeof data !== "undefined" && data && data.telemetry) ? data.telemetry : [];
    const telem = fleet.find(item => (item.task_id === t.id || item.id === t.id));
    if (!telem) return "";

    return `
      <div class="card-box" style="border: 1px solid rgba(245, 158, 11, 0.5); background: rgba(245, 158, 11, 0.05); margin-bottom: 12px;">
        <div class="card-box-title" style="color:#fde68a;">🛠️ Worktree Fleet Diagnostics &amp; Developer Handover</div>
        <div style="font-size:0.8rem; display:flex; flex-direction:column; gap:8px;">
          <div><strong style="color:#cbd5e1;">Worktree Directory:</strong> <code style="color:#67e8f9;">${escapeHtml(telem.worktree_path || telem.worktree_dir || '')}</code></div>
          <div><strong style="color:#cbd5e1;">Branch:</strong> <code style="color:#67e8f9;">${escapeHtml(telem.branch || '')}</code></div>
          <div><strong style="color:#cbd5e1;">Status:</strong> <span class="status-pill ${telem.stalled ? 'status-stalled' : 'status-executing'}">${escapeHtml(telem.status || '')}</span></div>
          <div><strong style="color:#cbd5e1;">Last Preflight Hook:</strong> <code style="color:#fca5a5;">${escapeHtml(telem.current_preflight_hook || telem.active_preflight_check || '')}</code></div>
          <div>
            <strong style="color:#cbd5e1;">Instructions for Developer Handover:</strong>
            <pre style="background:#090d16; padding:8px; border-radius:4px; font-size:0.75rem; color:#a7f3d0; margin-top:4px; white-space:pre-wrap;">${escapeHtml(telem.handover_instructions || '1. spec-ops rescue ' + escapeHtml(t.id) + '\n2. Fix preflight failures\n3. spec-ops rescue ' + escapeHtml(t.id) + ' --complete')}</pre>
          </div>
          <div>
            <strong style="color:#cbd5e1;">File Diff:</strong>
            <pre style="background:#090d16; padding:8px; border-radius:4px; font-size:0.72rem; color:#cbd5e1; max-height:160px; overflow-y:auto; margin-top:4px; white-space:pre-wrap;">${escapeHtml(telem.diff || 'No uncommitted changes in worktree.')}</pre>
          </div>
          <div>
            <strong style="color:#cbd5e1;">Last Preflight Terminal Output / Failure Feedback:</strong>
            <pre style="background:#090d16; padding:8px; border-radius:4px; font-size:0.72rem; color:#fca5a5; max-height:160px; overflow-y:auto; margin-top:4px; white-space:pre-wrap;">${escapeHtml(telem.failure_log || 'All preflight checks passing cleanly.')}</pre>
          </div>
          ${telem.prompt_feedback ? `
          <div>
            <strong style="color:#cbd5e1;">Last Generated Agent Prompt (.task-prompt.md):</strong>
            <pre style="background:#090d16; padding:8px; border-radius:4px; font-size:0.72rem; color:#94a3b8; max-height:160px; overflow-y:auto; margin-top:4px; white-space:pre-wrap;">${escapeHtml(telem.prompt_feedback)}</pre>
          </div>` : ''}
          <div style="display:flex; gap:8px; margin-top:6px;">
            <button class="ctrl-btn" style="background:#ef4444; color:#fff; border-color:#dc2626;" onclick="window.takeoverTask('${escapeHtml(t.id)}', this)">🚀 Launch Rescue Takeover</button>
          </div>
        </div>
      </div>
    `;
  };

  if (typeof window !== "undefined" && !window._fleetTelemetryInterval) {
    const timer = setInterval(function() {
      if (typeof activeTab !== "undefined" && (activeTab === "lead" || activeTab === "fleet") && typeof fetch === "function") {
        fetch("/api/telemetry")
          .then(r => r.json())
          .then(fleet => {
            if (typeof data !== "undefined" && data) {
              data.telemetry = fleet;
              if (typeof renderActiveView === "function") {
                renderActiveView();
              }
            }
          })
          .catch(() => {});
      }
    }, 3000);
    if (timer && typeof timer.unref === "function") {
      timer.unref();
    }
    window._fleetTelemetryInterval = timer;
  }

  window.renderLeadConsoleView = function() {
    const fleet = (data && data.telemetry) || [];
    const stalledItems = fleet.filter(t => t.stalled || (t.status && t.status.includes("Stalled")) || (t.attempt && t.attempt.startsWith("3/3")) || (t.retries && t.retries.startsWith("3/3")));

    return `
      <div class="lead-console-container">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <h2 style="font-size:1.1rem; font-weight:700; color:#fff; margin-bottom:2px;">Lead Operations Console / Fleet Telemetry</h2>
            <p style="font-size:0.75rem; color:var(--text-muted, #94a3b8);">Live agent fleet telemetry, active worktrees, preflight checks, and human rescue takeover.</p>
          </div>
          <span style="font-size:0.8rem; font-weight:600; color:#10b981;">● Fleet Active (${fleet.length} worker${fleet.length === 1 ? '' : 's'})</span>
        </div>

        ${stalledItems.map(st => `
          <div class="rescue-banner">
            <div class="rescue-banner-left">
              <span style="font-size:1.3rem;">⚠️</span>
              <div>
                <span class="rescue-banner-title">${escapeHtml(st.task_id || st.id)} Stalled: Awaiting Human Takeover</span>
                <p style="font-size:0.74rem; color:#fde68a; margin-top:2px;">Autonomous attempts exhausted (${escapeHtml(st.retries || st.attempt || '3/3')}). Preflight check failing.</p>
                ${st.failure_log ? `<div style="font-size:0.72rem; color:#fca5a5; margin-top:4px; font-family:monospace;">${escapeHtml(st.failure_log.substring(0, 160))}</div>` : ''}
              </div>
            </div>
            <div style="display:flex; gap:8px;">
              <button class="ctrl-btn" onclick="window.inspectWorktree('${escapeHtml(st.task_id || st.id)}')">Inspect Worktree</button>
              <button class="ctrl-btn" style="background:#ef4444; color:#fff; border-color:#dc2626;" onclick="window.takeoverTask('${escapeHtml(st.task_id || st.id)}', this)">🚀 Launch Rescue Takeover</button>
            </div>
          </div>
        `).join("")}

        <div class="fleet-grid-wrap">
          <table class="fleet-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Worktree Directory</th>
                <th>Task Title</th>
                <th>Branch</th>
                <th>Status</th>
                <th>Retries</th>
                <th>Current Preflight Hook</th>
                <th>Elapsed Runtime</th>
                <th>Memory</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${fleet.map(t => {
                const isStalled = t.stalled || (t.status && t.status.includes("Stalled")) || (t.attempt && t.attempt.startsWith("3/3")) || (t.retries && t.retries.startsWith("3/3"));
                const stClass = isStalled ? "status-stalled" : (t.status === "Self-Healing" ? "status-healing" : "status-executing");
                const rowClass = isStalled ? "row-stalled" : "";
                const tid = escapeHtml(t.task_id || t.id);
                const displayStatus = isStalled ? "Stalled: Human Takeover Required" : (t.status || 'Running');
                const retryDisplay = (t.status === "Self-Healing" || (t.retries && t.retries.includes("Self-Healing")))
                  ? `${escapeHtml(t.retries || t.attempt || '2/3')} Self-Healing`
                  : escapeHtml(t.retries || t.attempt || '0/3');

                return `
                  <tr class="${rowClass}" style="${isStalled ? 'border: 2px solid #f59e0b; background: rgba(245, 158, 11, 0.08);' : ''}">
                    <td><strong style="color:#f8fafc; cursor:pointer;" onclick="openDrawer('${tid}')">${tid}</strong></td>
                    <td style="font-family:monospace; font-size:0.75rem; color:#94a3b8;">${escapeHtml(t.worktree_path || t.worktree_dir || '')}</td>
                    <td style="color:#e2e8f0; font-size:0.78rem;">${escapeHtml(t.title || t.task_title || '')}</td>
                    <td style="font-family:monospace; font-size:0.75rem; color:#67e8f9;">${escapeHtml(t.branch || '')}</td>
                    <td><span class="status-pill ${stClass}">${escapeHtml(displayStatus)}</span></td>
                    <td><span style="font-weight:600; color:#e2e8f0;">${retryDisplay}</span></td>
                    <td><span style="color:#cbd5e1;">${escapeHtml(t.current_preflight_hook || t.active_preflight_check || 'uv run pytest')}</span></td>
                    <td style="font-family:monospace; font-size:0.75rem; color:#94a3b8;">${escapeHtml(t.elapsed_runtime || '0s')}</td>
                    <td style="font-family:monospace; font-size:0.75rem; color:#94a3b8;">${escapeHtml(t.memory_usage || (t.memory_mb ? t.memory_mb + ' MB' : '128 MB'))}</td>
                    <td>
                      <div style="display:flex; gap:6px;">
                        <button class="ctrl-btn" onclick="window.inspectWorktree('${tid}')">Inspect Worktree</button>
                        ${isStalled ? `<button class="ctrl-btn rescue-btn" style="background:#ef4444; color:#fff; border-color:#dc2626;" onclick="window.takeoverTask('${tid}', this)">🚀 Launch Rescue Takeover</button>` : `<button class="ctrl-btn rescue-btn" onclick="window.takeoverTask('${tid}', this)">Rescue Task</button>`}
                      </div>
                    </td>
                  </tr>
                  <tr id="worktree-log-display-${tid}" style="display:none; background:#0f172a;">
                    <td colspan="10" style="padding:12px 16px;">
                      <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                        <strong style="color:#fde68a;">Diagnostic Failure Excerpt &amp; Agent Prompt:</strong>
                        <div style="display:flex; gap:8px;">
                          <a href="#entity=${tid}" onclick="openDrawer('${tid}')" style="color:#38bdf8; font-size:0.75rem;">Deep link to task specification and diff</a>
                          <button class="ctrl-btn" onclick="document.getElementById('worktree-log-display-${tid}').style.display='none'">✕ Close</button>
                        </div>
                      </div>
                      ${t.failure_log ? `<div class="worktree-inspect-box" style="margin-bottom:8px; border-color:rgba(239,68,68,0.4);"><strong style="color:#fca5a5;">Failure Excerpt:</strong>\n${escapeHtml(t.failure_log)}</div>` : ''}
                      ${t.prompt_feedback ? `<div class="worktree-inspect-box"><strong style="color:#94a3b8;">Prompt Feedback:</strong>\n${escapeHtml(t.prompt_feedback)}</div>` : (!t.failure_log ? '<div class="worktree-inspect-box">No feedback log found in worktree.</div>' : '')}
                    </td>
                  </tr>
                `;
              }).join("")}
              ${fleet.length === 0 ? '<tr><td colspan="10" style="text-align:center; padding:30px; color:#64748b;">No active autonomous worker streams detected in .worktrees/.</td></tr>' : ''}
            </tbody>
          </table>
        </div>

        ${stalledItems.length > 0 ? `
          <div class="rescue-panel">
            <h3 style="font-size:0.95rem; font-weight:700; color:#fca5a5;">Human Rescue Deck</h3>
            <p style="font-size:0.75rem; color:#94a3b8;">Click '🚀 Launch Rescue Takeover' to copy the CLI rescue command or inspect failure logs and diffs directly.</p>
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${stalledItems.map(st => `
                <div style="display:flex; justify-content:space-between; align-items:center; background:#1e293b; padding:10px 14px; border-radius:6px; border:1px solid #f59e0b;">
                  <div>
                    <strong style="color:#fff;">${escapeHtml(st.task_id || st.id)}</strong>
                    <span style="color:#94a3b8; font-size:0.75rem; margin-left:8px;">${escapeHtml(st.branch || '')}</span>
                    <span class="status-pill status-stalled" style="margin-left:8px;">Stalled: Human Takeover Required</span>
                  </div>
                  <div style="display:flex; align-items:center; gap:8px;">
                    <a href="#entity=${escapeHtml(st.task_id || st.id)}" onclick="openDrawer('${escapeHtml(st.task_id || st.id)}')" style="color:#38bdf8; font-size:0.75rem;">Task Spec &amp; Diff</a>
                    <button class="ctrl-btn" style="background:#ef4444; color:#fff; border-color:#dc2626;" onclick="window.takeoverTask('${escapeHtml(st.task_id || st.id)}', this)">🚀 Launch Rescue Takeover</button>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        ` : ''}
      </div>
    `;
  };
"""
