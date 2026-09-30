"""Lead console script and fleet telemetry harvester for SpecOps."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig

LEAD_CONSOLE_CSS = r"""
.lead-console-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}
.rescue-banner {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(185, 28, 28, 0.3));
  border: 1px solid rgba(239, 68, 68, 0.6);
  border-radius: 8px;
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.15);
}
.rescue-banner-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.rescue-banner-title {
  color: #fca5a5;
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
    const cmd = "spec-ops rescue inspect " + taskId;
    const nav = (typeof window !== "undefined" && window.navigator && window.navigator.clipboard) ? window.navigator : (typeof navigator !== "undefined" ? navigator : null);
    if (nav && nav.clipboard && nav.clipboard.writeText) {
      return nav.clipboard.writeText(cmd).then(() => {
        if (btnElem) {
          const orig = btnElem.textContent;
          btnElem.textContent = "✓ Copied Command!";
          btnElem.style.background = "#10b981";
          setTimeout(() => {
            btnElem.textContent = orig;
            btnElem.style.background = "";
          }, 2000);
        }
        return cmd;
      });
    } else if (typeof prompt === "function") {
      prompt("Copy CLI rescue command:", cmd);
      return Promise.resolve(cmd);
    }
    return Promise.resolve(cmd);
  };

  window.inspectWorktree = function(taskId) {
    const fleet = (data && data.telemetry) || [];
    const item = fleet.find(t => t.task_id === taskId || t.id === taskId);
    const box = document.getElementById("worktree-log-display-" + taskId);
    if (box) {
      box.style.display = box.style.display === "none" ? "block" : "none";
      return;
    }
    // If not inline, open entity drawer
    if (typeof openDrawer === "function") {
      openDrawer(taskId);
    }
  };

  window.renderLeadConsoleView = function() {
    const fleet = (data && data.telemetry) || [];
    const stalledItems = fleet.filter(t => t.stalled || t.status === "Stalled" || (t.attempt && t.attempt.startsWith("3/3")));

    return `
      <div class="lead-console-container">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <h2 style="font-size:1.1rem; font-weight:700; color:#fff; margin-bottom:2px;">Lead Operations Console</h2>
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
                <p style="font-size:0.74rem; color:#fca5a5; margin-top:2px;">Autonomous attempts exhausted (${escapeHtml(st.attempt || '3/3')}). Preflight check failing.</p>
              </div>
            </div>
            <div style="display:flex; gap:8px;">
              <button class="ctrl-btn" onclick="window.inspectWorktree('${escapeHtml(st.task_id || st.id)}')">Inspect Worktree</button>
              <button class="ctrl-btn" style="background:#ef4444; color:#fff; border-color:#dc2626;" onclick="window.takeoverTask('${escapeHtml(st.task_id || st.id)}', this)">Takeover Task</button>
            </div>
          </div>
        `).join("")}

        <div class="fleet-grid-wrap">
          <table class="fleet-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Worktree Path</th>
                <th>Branch</th>
                <th>Status</th>
                <th>Attempt</th>
                <th>Active Preflight Check</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${fleet.map(t => {
                const isStalled = t.stalled || t.status === "Stalled" || (t.attempt && t.attempt.startsWith("3/3"));
                const stClass = isStalled ? "status-stalled" : (t.status === "Self-Healing" ? "status-healing" : "status-executing");
                const tid = escapeHtml(t.task_id || t.id);

                return `
                  <tr>
                    <td><strong style="color:#f8fafc; cursor:pointer;" onclick="openDrawer('${tid}')">${tid}</strong></td>
                    <td style="font-family:monospace; font-size:0.75rem; color:#94a3b8;">${escapeHtml(t.worktree_path || '')}</td>
                    <td style="font-family:monospace; font-size:0.75rem; color:#67e8f9;">${escapeHtml(t.branch || '')}</td>
                    <td><span class="status-pill ${stClass}">${escapeHtml(t.status || 'Executing')}</span></td>
                    <td><span style="font-weight:600; color:#e2e8f0;">${escapeHtml(t.attempt || '1/3')}</span></td>
                    <td><span style="color:#cbd5e1;">${escapeHtml(t.active_preflight_check || 'uv run pytest')}</span></td>
                    <td>
                      <div style="display:flex; gap:6px;">
                        <button class="ctrl-btn" onclick="window.inspectWorktree('${tid}')">Inspect Worktree</button>
                        ${isStalled ? `<button class="ctrl-btn" style="background:#ef4444; color:#fff; border-color:#dc2626;" onclick="window.takeoverTask('${tid}', this)">Takeover Task</button>` : ''}
                      </div>
                    </td>
                  </tr>
                  <tr id="worktree-log-display-${tid}" style="display:none; background:#0f172a;">
                    <td colspan="7" style="padding:12px 16px;">
                      <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                        <strong style="color:#fca5a5;">Failure Feedback &amp; .task-prompt.md:</strong>
                        <div style="display:flex; gap:8px;">
                          <a href="#entity=${tid}" onclick="openDrawer('${tid}')" style="color:#38bdf8; font-size:0.75rem;">Deep link to task specification and diff</a>
                          <button class="ctrl-btn" onclick="document.getElementById('worktree-log-display-${tid}').style.display='none'">✕ Close</button>
                        </div>
                      </div>
                      <div class="worktree-inspect-box">${escapeHtml(t.failure_log || t.prompt_feedback || 'No feedback log found in worktree.')}</div>
                    </td>
                  </tr>
                `;
              }).join("")}
              ${fleet.length === 0 ? '<tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b;">No active autonomous worker streams detected in .worktrees/.</td></tr>' : ''}
            </tbody>
          </table>
        </div>

        ${stalledItems.length > 0 ? `
          <div class="rescue-panel">
            <h3 style="font-size:0.95rem; font-weight:700; color:#fca5a5;">Human Rescue Deck</h3>
            <p style="font-size:0.75rem; color:#94a3b8;">Click 'Takeover Task' to copy the CLI rescue command or inspect failure logs and diffs directly.</p>
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${stalledItems.map(st => `
                <div style="display:flex; justify-content:space-between; align-items:center; background:#1e293b; padding:10px 14px; border-radius:6px;">
                  <div>
                    <strong style="color:#fff;">${escapeHtml(st.task_id || st.id)}</strong>
                    <span style="color:#94a3b8; font-size:0.75rem; margin-left:8px;">${escapeHtml(st.branch || '')}</span>
                  </div>
                  <div style="display:flex; align-items:center; gap:8px;">
                    <a href="#entity=${escapeHtml(st.task_id || st.id)}" onclick="openDrawer('${escapeHtml(st.task_id || st.id)}')" style="color:#38bdf8; font-size:0.75rem;">Task Spec &amp; Diff</a>
                    <button class="ctrl-btn" onclick="window.takeoverTask('${escapeHtml(st.task_id || st.id)}', this)">Takeover Task</button>
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


def harvest_fleet_telemetry(config: SpecOpsConfig) -> list[dict[str, Any]]:
    """Harvests active worker telemetry from isolated git worktrees."""
    worktrees_parent = config.root_dir / ".worktrees"
    if not worktrees_parent.exists():
        return []

    telemetry: list[dict[str, Any]] = []

    for p in sorted(worktrees_parent.iterdir()):
        if not p.is_dir():
            continue
        m = re.match(r"^task-(\d+)", p.name)
        if not m:
            continue

        tid_num = m.group(1).zfill(4)
        tid = f"TASK-{tid_num}"

        # Branch detection
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=p,
            capture_output=True,
            text=True,
        )
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else f"feat/task-{tid_num}"

        # Status and metadata files
        worker_json = p / ".specops" / "worker.json"
        telemetry_json = p / ".telemetry.json"

        status = "Executing"
        attempt = "1/3"
        active_check = "uv run pytest"
        failure_log = ""
        prompt_feedback = ""
        stalled = False

        if worker_json.exists():
            try:
                wdata = json.loads(worker_json.read_text(encoding="utf-8"))
                status = wdata.get("status", status)
                attempt = wdata.get("attempt", attempt)
                active_check = wdata.get("active_preflight_check", active_check)
                stalled = bool(wdata.get("stalled", False))
                failure_log = wdata.get("failure_log", "")
            except Exception:
                pass
        elif telemetry_json.exists():
            try:
                tdata = json.loads(telemetry_json.read_text(encoding="utf-8"))
                status = tdata.get("status", status)
                attempt = tdata.get("attempt", attempt)
                active_check = tdata.get("active_preflight_check", active_check)
                stalled = bool(tdata.get("stalled", False))
                failure_log = tdata.get("failure_log", "")
            except Exception:
                pass
        else:
            # Parse .task-prompt.md
            prompt_file = p / ".task-prompt.md"
            if prompt_file.exists():
                text = prompt_file.read_text(encoding="utf-8", errors="ignore")
                prompt_feedback = text

                # Check attempt
                att_match = re.search(r"\(Attempt\s+(\d+)\)", text, re.IGNORECASE)
                if att_match:
                    att_num = int(att_match.group(1))
                    attempt = f"{att_num}/3"
                    if att_num >= 3:
                        stalled = True
                        status = "Stalled"
                    elif att_num > 1:
                        status = "Self-Healing"
                elif "stalled" in text.lower():
                    stalled = True
                    status = "Stalled"
                    attempt = "3/3"

                # Check active check
                if "file limit" in text.lower() or "file length" in text.lower():
                    active_check = "Fixing file limit"
                elif "pytest" in text.lower():
                    active_check = "uv run pytest"
                elif "spec-ops health" in text.lower():
                    active_check = "uv run spec-ops health"

                if "## Preflight Failure Feedback" in text:
                    failure_log = text.split("## Preflight Failure Feedback")[-1].strip()
                elif "## Architectural Review Feedback" in text:
                    failure_log = text.split("## Architectural Review Feedback")[-1].strip()

        rel_path = f".worktrees/{p.name}"

        telemetry.append(
            {
                "task_id": tid,
                "id": tid,
                "worktree_path": rel_path,
                "branch": branch,
                "status": status,
                "attempt": attempt,
                "active_preflight_check": active_check,
                "failure_log": failure_log,
                "prompt_feedback": prompt_feedback,
                "stalled": stalled or status == "Stalled" or attempt.startswith("3/3"),
                "rescue_cmd": f"spec-ops rescue inspect {tid}",
            }
        )

    return telemetry
