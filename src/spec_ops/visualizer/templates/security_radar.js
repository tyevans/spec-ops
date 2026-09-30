(function() {
  window.securityRadarFilterState = window.securityRadarFilterState || {
    showOnlyUnsigned: false,
    searchQuery: "",
  };

  window.toggleUnsignedFilter = function(checked) {
    window.securityRadarFilterState.showOnlyUnsigned = Boolean(checked);
    if (typeof renderActiveView === "function") {
      renderActiveView();
    }
  };

  window.setSecuritySearch = function(query) {
    window.securityRadarFilterState.searchQuery = query || "";
    if (typeof renderActiveView === "function") {
      renderActiveView();
    }
  };

  function getSecurityData() {
    if (window.PROJECT_DATA && window.PROJECT_DATA.security) {
      return window.PROJECT_DATA.security;
    }
    const sec = (typeof data !== "undefined" && data && data.security) ? data.security : {};
    return sec;
  }

  function getTriageTasks() {
    const sec = getSecurityData();
    if (sec.triage_tasks && sec.triage_tasks.length > 0) {
      return sec.triage_tasks;
    }
    const rawTasks = (typeof data !== "undefined" && data && data.tasks) ? data.tasks : [];
    return rawTasks.map(t => {
      const hasSignoff = Boolean(t.signed_off_by || t.has_human_signoff);
      const hasSignedCommits = Boolean(t.has_signed_commits || (t.commit_signature_status && ["SIGNED", "G", "U", "VALID"].includes(t.commit_signature_status.toUpperCase())));
      const cveCount = Number(t.cve_count || 0);
      const missing = [];
      if (!hasSignoff) missing.append ? missing.append("Human Review Sign-off") : missing.push("Human Review Sign-off");
      if (!hasSignedCommits) missing.push("Cryptographic Commit Signature");
      if (cveCount > 0) missing.push(cveCount + " Open CVE(s)");
      const isCompliant = missing.length === 0;
      return {
        id: t.id,
        title: t.title || "",
        status: t.status || "Proposed",
        target_bc: t.target_bc || "",
        signed_off_by: t.signed_off_by || "",
        signed_off_at: t.signed_off_at || "",
        has_human_signoff: hasSignoff,
        has_signed_commits: hasSignedCommits,
        cve_count: cveCount,
        missing_artifacts: missing,
        is_compliant: isCompliant,
        status_label: isCompliant ? "Compliant" : "Non-Compliant (Blocking)",
        permalink: "#tab=security&entity=" + t.id,
      };
    });
  }

  window.renderSecurityRadarView = function() {
    const sec = getSecurityData();
    const tasks = getTriageTasks();
    const state = window.securityRadarFilterState;

    const filtered = tasks.filter(t => {
      if (state.showOnlyUnsigned && t.is_compliant) {
        return false;
      }
      if (state.searchQuery) {
        const q = state.searchQuery.toLowerCase().trim();
        const match = (t.id && t.id.toLowerCase().includes(q)) ||
                      (t.title && t.title.toLowerCase().includes(q)) ||
                      (t.target_bc && t.target_bc.toLowerCase().includes(q));
        if (!match) return false;
      }
      return true;
    });

    const secretStatus = sec.secret_scan_status || "Pass";
    const lockfileStatus = sec.lockfile_integrity || "Synchronized";
    const signedCommits = sec.signed_commit_coverage_display || (sec.signed_commit_coverage !== undefined ? sec.signed_commit_coverage + "%" : "100%");
    const humanSignoff = sec.human_signoff_rate_display || (sec.human_signoff_rate !== undefined ? sec.human_signoff_rate + "%" : "100%");
    const vulnIndicator = sec.vulnerability_indicator || "0 Low / 0 Med / 0 High";

    return `
      <div class="sec-radar-container">
        <div class="sec-metric-cards-grid">
          <div class="sec-metric-card" id="card-secret-scan">
            <div class="sec-card-title">Secret Scan Status</div>
            <div class="sec-card-value ${secretStatus === 'Pass' ? 'status-pass' : 'status-fail'}">${escapeHtml(secretStatus)}</div>
          </div>
          <div class="sec-metric-card" id="card-lockfile-integrity">
            <div class="sec-card-title">Lockfile Integrity</div>
            <div class="sec-card-value ${lockfileStatus === 'Synchronized' ? 'status-pass' : 'status-warn'}">${escapeHtml(lockfileStatus)}</div>
          </div>
          <div class="sec-metric-card" id="card-signed-commit-coverage">
            <div class="sec-card-title">Signed Commit Coverage</div>
            <div class="sec-card-value status-pct">${escapeHtml(signedCommits)}</div>
          </div>
          <div class="sec-metric-card" id="card-human-signoff-rate">
            <div class="sec-card-title">Human Sign-off Rate</div>
            <div class="sec-card-value status-pct">${escapeHtml(humanSignoff)}</div>
          </div>
          <div class="sec-metric-card" id="card-known-vulnerability-count">
            <div class="sec-card-title">Known Vulnerability Count</div>
            <div class="sec-card-value status-cve">${escapeHtml(vulnIndicator)}</div>
          </div>
        </div>

        <div class="sec-triage-toolbar">
          <div style="display:flex; align-items:center; gap:12px; flex:1;">
            <input type="text" class="filter-input" placeholder="Filter triage tasks by ID, title, BC..." value="${escapeHtml(state.searchQuery)}" oninput="window.setSecuritySearch(this.value)" style="max-width:280px;">
            <label class="sec-filter-toggle">
              <input type="checkbox" id="filter-unsigned-unreviewed" ${state.showOnlyUnsigned ? 'checked' : ''} onchange="window.toggleUnsignedFilter(this.checked)">
              <span>Show Only Unsigned / Unreviewed</span>
            </label>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="count-badge" style="background:rgba(56,189,248,0.15); color:#38bdf8; font-size:0.75rem; padding:4px 10px; border-radius:9999px;">
              ${filtered.length} of ${tasks.length} tasks
            </span>
          </div>
        </div>

        <div class="sec-triage-table-wrap">
          <table class="sec-triage-table" id="compliance-triage-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Title</th>
                <th>Bounded Context</th>
                <th>Human Sign-Off</th>
                <th>Commit Signature</th>
                <th>CVEs</th>
                <th>Compliance Status</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.map(t => `
                <tr class="triage-row ${t.is_compliant ? 'row-compliant' : 'row-non-compliant'}" onclick="openDrawer('${escapeHtml(t.id)}')">
                  <td><span class="entity-pill pill-task">${escapeHtml(t.id)}</span></td>
                  <td><strong style="color:#fff;">${escapeHtml(t.title)}</strong></td>
                  <td><span class="entity-pill pill-bc">${escapeHtml(t.target_bc || 'core')}</span></td>
                  <td>${t.has_human_signoff ? '<span class="status-badge badge-pass">✓ Signed</span>' : '<span class="status-badge badge-fail">Pending</span>'}</td>
                  <td>${t.has_signed_commits ? '<span class="status-badge badge-pass">✓ Signed</span>' : '<span class="status-badge badge-fail">Unsigned</span>'}</td>
                  <td>${t.cve_count > 0 ? `<span class="status-badge badge-fail">${t.cve_count} CVE</span>` : '<span class="status-badge badge-pass">0</span>'}</td>
                  <td><span class="compliance-pill ${t.is_compliant ? 'pill-ok' : 'pill-block'}">${escapeHtml(t.status_label)}</span></td>
                </tr>
              `).join("")}
              ${filtered.length === 0 ? '<tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b;">No matching tasks found in compliance triage.</td></tr>' : ''}
            </tbody>
          </table>
        </div>
      </div>
    `;
  };

  window.renderTaskComplianceCard = function(t) {
    if (!t) return "";
    const tasks = getTriageTasks();
    const cleanId = String(t.id || t.canonical_id || "").toUpperCase();
    let comp = tasks.find(item => item.id && item.id.toUpperCase() === cleanId);
    if (!comp) {
      const hasSignoff = Boolean(t.signed_off_by || t.has_human_signoff);
      const hasSignedCommits = Boolean(t.has_signed_commits || (t.commit_signature_status && ["SIGNED", "G", "U", "VALID"].includes(t.commit_signature_status.toUpperCase())));
      const cveCount = Number(t.cve_count || 0);
      const missing = [];
      if (!hasSignoff) missing.push("Human Review Sign-off");
      if (!hasSignedCommits) missing.push("Cryptographic Commit Signature");
      if (cveCount > 0) missing.push(cveCount + " Open CVE(s)");
      comp = {
        has_human_signoff: hasSignoff,
        has_signed_commits: hasSignedCommits,
        cve_count: cveCount,
        missing_artifacts: missing,
        is_compliant: missing.length === 0,
      };
    }

    const missing = comp.missing_artifacts || [];
    const permalinkUrl = "#tab=security&entity=" + encodeURIComponent(cleanId);

    return `
      <div class="card-box sec-drawer-compliance-box">
        <div class="card-box-title">Compliance &amp; Security Posture</div>
        <div class="compliance-drawer-grid">
          <div><span style="color:var(--text-muted);">Human Review Sign-off:</span> <b class="${comp.has_human_signoff ? 'pass' : 'fail'}">${comp.has_human_signoff ? escapeHtml(t.signed_off_by || 'Signed') : 'Pending / Missing'}</b></div>
          <div><span style="color:var(--text-muted);">Cryptographic Commits:</span> <b class="${comp.has_signed_commits ? 'pass' : 'fail'}">${comp.has_signed_commits ? 'Signed (GPG/SSH)' : 'Unsigned Commits'}</b></div>
          <div><span style="color:var(--text-muted);">Known Vulnerabilities:</span> <b class="${comp.cve_count > 0 ? 'fail' : 'pass'}">${comp.cve_count || 0} Open CVEs</b></div>
          <div><span style="color:var(--text-muted);">Compliance Status:</span> <span class="compliance-pill ${comp.is_compliant ? 'pill-ok' : 'pill-block'}">${comp.is_compliant ? 'Compliant' : 'Non-Compliant (Blocking)'}</span></div>
        </div>
        <div style="margin-top:10px;">
          <div style="font-size:0.75rem; color:var(--text-muted); font-weight:600; margin-bottom:4px;">Missing Compliance Artifacts:</div>
          ${missing.length > 0 ? `
            <ul class="missing-artifacts-list" style="margin:4px 0 0 18px; color:#fca5a5; font-size:0.78rem;">
              ${missing.map(m => `<li>${escapeHtml(m)}</li>`).join("")}
            </ul>
          ` : `
            <div style="color:#6ee7b7; font-size:0.78rem;">✓ None (All required compliance artifacts present)</div>
          `}
        </div>
        <div style="margin-top:12px; display:flex; align-items:center; gap:8px; font-size:0.75rem;">
          <span style="color:var(--text-muted);">Permalink URL:</span>
          <a href="${permalinkUrl}" class="sec-drawer-permalink" style="color:#38bdf8; font-family:monospace; text-decoration:none;">${permalinkUrl}</a>
          <button class="copy-btn" onclick="copyDeepLink('${escapeHtml(cleanId)}', this, event)" style="font-size:0.7rem; padding:2px 8px;">Copy Link</button>
        </div>
      </div>
    `;
  };
})();
