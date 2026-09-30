"""Client-side JavaScript rendering the living Customer UAT Verification Matrix and sign-off UI."""

UAT_JS = r"""
  // --- UAT Readiness Matrix View ---
  window.renderUatView = function() {
    const uat = data.uat || { matrix: [], readiness_percentage: 0.0 };
    const matrix = uat.matrix || [];
    const readiness = uat.readiness_percentage !== undefined ? uat.readiness_percentage : 0.0;

    let rowsHtml = "";
    if (matrix.length === 0) {
      rowsHtml = `<tr><td colspan="5" style="text-align:center; padding:30px; color:var(--text-muted);">No accepted PRD checkable outcomes found.</td></tr>`;
    } else {
      rowsHtml = matrix.map(item => {
        const isApproved = item.uat_status === "Approved" || item.uat_status === "Approved (PM UAT)";
        const badgeBg = isApproved ? "#10b981" : "rgba(245, 158, 11, 0.15)";
        const badgeColor = isApproved ? "#ffffff" : "#f59e0b";
        const badgeBorder = isApproved ? "1px solid #059669" : "1px solid rgba(245, 158, 11, 0.4)";
        const testClass = item.test_status && item.test_status.includes("Passed") ? "badge-passed" : "badge-pending";

        const storiesHtml = (item.linked_stories || []).length > 0
          ? item.linked_stories.map(s => `<span class="entity-pill pill-story" style="font-size:0.75rem; margin-right:4px;">${escapeHtml(s)}</span>`).join("")
          : `<span style="color:var(--text-muted); font-size:0.8rem;">—</span>`;

        return `
          <tr id="uat-row-${escapeHtml(item.prd_id)}-${escapeHtml(item.outcome_id)}">
            <td style="font-weight:500;">
              <div>${escapeHtml(item.outcome_text)}</div>
              <small style="color:var(--text-muted); font-size:0.72rem;">${escapeHtml(item.prd_id)} Outcome ${escapeHtml(item.outcome_id)}</small>
            </td>
            <td>${storiesHtml}</td>
            <td>
              <span class="badge ${testClass}" style="font-size:0.78rem; font-weight:600; padding:3px 8px; border-radius:4px; background:rgba(16, 185, 129, 0.15); color:#10b981; border:1px solid rgba(16, 185, 129, 0.3);">
                ${escapeHtml(item.test_status || 'Pending')}
              </span>
            </td>
            <td>
              <span class="badge uat-status-badge ${isApproved ? 'badge-green' : ''}" 
                    id="uat-badge-${escapeHtml(item.prd_id)}-${escapeHtml(item.outcome_id)}" 
                    style="font-size:0.78rem; font-weight:600; padding:3px 8px; border-radius:4px; background:${badgeBg}; color:${badgeColor}; border:${badgeBorder}; display:inline-block;">
                ${escapeHtml(item.uat_status || 'Pending PM')}
              </span>
            </td>
            <td>
              <button class="ctrl-btn btn-toggle-uat" 
                      style="font-size:0.75rem; padding:4px 10px; cursor:pointer;"
                      onclick="window.toggleUatSignoff('${escapeHtml(item.prd_id)}', '${escapeHtml(item.outcome_id)}')">
                ${isApproved ? 'Revoke Sign-Off' : 'Approve (PM UAT)'}
              </button>
            </td>
          </tr>
        `;
      }).join("");
    }

    return `
      <div class="uat-dashboard-container" style="padding:20px; max-width:1200px; margin:0 auto; width:100%;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:16px;">
          <div>
            <h2 style="font-size:1.4rem; font-weight:700; color:#fff; margin-bottom:4px;">📋 Customer UAT Verification Matrix</h2>
            <p style="color:var(--text-muted); font-size:0.85rem;">Living correlation of PRD checkable outcomes, BDD test verification, and formal PM sign-offs.</p>
          </div>
          <div style="background:var(--bg-card); border:1px solid var(--border-subtle); padding:10px 18px; border-radius:8px; display:flex; align-items:center; gap:12px;">
            <span style="font-size:0.85rem; color:var(--text-muted);">Overall Customer Delivery Readiness:</span>
            <span id="uat-readiness-pct" style="font-size:1.3rem; font-weight:800; color:#10b981;">${readiness.toFixed(1)}%</span>
          </div>
        </div>

        <div style="background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:8px; overflow:hidden;">
          <table class="matrix-table" style="width:100%; border-collapse:collapse; font-size:0.85rem;">
            <thead>
              <tr style="background:rgba(255,255,255,0.03); border-bottom:1px solid var(--border-subtle); text-align:left;">
                <th style="padding:12px 16px; color:var(--text-muted); font-weight:600;">PRD Outcome</th>
                <th style="padding:12px 16px; color:var(--text-muted); font-weight:600;">Linked Story</th>
                <th style="padding:12px 16px; color:var(--text-muted); font-weight:600;">Test Status</th>
                <th style="padding:12px 16px; color:var(--text-muted); font-weight:600;">UAT Status</th>
                <th style="padding:12px 16px; color:var(--text-muted); font-weight:600;">Action</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      </div>
    `;
  };

  window.toggleUatSignoff = function(prdId, outcomeId, optionalStatus, optionalNotes, optionalReviewer) {
    const uat = data.uat || { matrix: [], readiness_percentage: 0.0 };
    const matrix = uat.matrix || [];
    const item = matrix.find(m => m.prd_id === prdId && String(m.outcome_id) === String(outcomeId));
    
    const currentApproved = item && (item.uat_status === "Approved" || item.uat_status === "Approved (PM UAT)");
    const targetStatus = optionalStatus || (currentApproved ? "Pending PM" : "Approved");
    const notes = optionalNotes || (currentApproved ? "Revoked by PM" : "Verified multi-tab switching and drawer responsiveness on Chromium");
    const reviewer = optionalReviewer || "Taylor <taylor@specops.local>";

    if (item) {
      item.uat_status = targetStatus;
      item.notes = notes;
      item.reviewer = reviewer;
      item.timestamp = new Date().toISOString();
    }

    // Immediate DOM update for green badge
    const badge = document.getElementById(`uat-badge-${prdId}-${outcomeId}`);
    if (badge) {
      if (targetStatus === "Approved") {
        badge.textContent = "Approved";
        badge.className = "badge uat-status-badge badge-green";
        badge.style.background = "#10b981";
        badge.style.color = "#ffffff";
        badge.style.border = "1px solid #059669";
      } else {
        badge.textContent = targetStatus;
        badge.className = "badge uat-status-badge";
        badge.style.background = "rgba(245, 158, 11, 0.15)";
        badge.style.color = "#f59e0b";
        badge.style.border = "1px solid rgba(245, 158, 11, 0.4)";
      }
    }

    // Recompute readiness
    const approvedCount = matrix.filter(m => m.uat_status === "Approved" || m.uat_status === "Approved (PM UAT)").length;
    const totalCount = matrix.length;
    const newPct = totalCount > 0 ? (approvedCount / totalCount) * 100.0 : 0.0;
    uat.readiness_percentage = newPct;
    const pctElem = document.getElementById("uat-readiness-pct");
    if (pctElem) {
      pctElem.textContent = `${newPct.toFixed(1)}%`;
    }

    // Send async POST to server
    fetch("/api/uat/signoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prd_id: prdId,
        outcome_id: outcomeId,
        status: targetStatus,
        notes: notes,
        reviewer: reviewer,
      })
    }).catch(err => {
      console.warn("UAT sign-off local sync (offline mode):", err);
    });
  };
"""
