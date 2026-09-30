"""Client-side detail drawer rendering script for SpecOps visualizer."""

DRAWER_JS = r"""
  let currentEntity = null;

  function renderMarkdown(md) {
    if (!md) return "";
    return md
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/```([a-z]*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/^### (.*$)/gim, "<h3>$1</h3>")
      .replace(/^## (.*$)/gim, "<h2>$1</h2>")
      .replace(/^# (.*$)/gim, "<h1>$1</h1>")
      .replace(/^\> (.*$)/gim, "<blockquote>$1</blockquote>")
      .replace(/^\s*-\s+(.*$)/gim, "<li>$1</li>")
      .replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>")
      .replace(/\n\n+/g, "<p></p>");
  }

  function findEntity(id) {
    if (!id) return null;
    const rawId = String(id).toUpperCase();
    let entity = (data.tasks || []).find(t => t.id && (t.id.toUpperCase() === rawId || t.id.toUpperCase().replace("TASK-", "") === rawId.replace("TASK-", "")));
    if (entity) return { entity, type: "TASK" };

    entity = (data.stories || []).find(s => s.id && (s.id.toUpperCase() === rawId || s.id.toUpperCase().replace("US-", "") === rawId.replace("US-", "")));
    if (entity) return { entity, type: "STORY" };

    entity = (data.prds || []).find(p => p.id && (p.id.toUpperCase() === rawId || p.id.toUpperCase().replace("PRD-", "") === rawId.replace("PRD-", "")));
    if (entity) return { entity, type: "PRD" };

    entity = (data.adrs || []).find(a => a.id && (a.id.toUpperCase() === rawId || a.id.toUpperCase().replace("ADR-", "") === rawId.replace("ADR-", "")));
    if (entity) return { entity, type: "ADR" };

    const lowerId = String(id).toLowerCase();
    entity = (data.personas || []).find(p => (p.id && p.id.toLowerCase() === lowerId) || (p.name && p.name.toLowerCase() === lowerId));
    if (entity) return { entity, type: "PERSONA" };

    entity = (data.bounded_contexts || []).find(b => (b.id && b.id.toLowerCase() === lowerId) || (b.name && b.name.toLowerCase() === lowerId));
    if (entity) return { entity, type: "BOUNDED CONTEXT" };

    const node = (data.nodes || []).find(n => n.id && n.id.toUpperCase() === rawId);
    if (node) return { entity: node, type: (node.type || "ENTITY").toUpperCase() };

    return null;
  }

  function pill(id, type) {
    const cls = { task: "pill-task", adr: "pill-adr", story: "pill-story", prd: "pill-prd", persona: "pill-persona", bc: "pill-bc" }[type] || "pill-task";
    return `<button class="entity-pill ${cls}" onclick="openDrawer('${id}')">${id}</button>`;
  }

  function renderTaskCard(t) {
    const statusBg = t.status === "Complete" ? "rgba(16,185,129,0.2); color:#6ee7b7; border-color:rgba(16,185,129,0.4)"
      : (t.status === "Refined" ? "rgba(245,158,11,0.2); color:#fcd34d; border-color:rgba(245,158,11,0.4)"
      : "rgba(139,92,246,0.2); color:#c4b5fd; border-color:rgba(139,92,246,0.4)");
    const commits = t.commits || [];
    const prs = t.prs || [];

    return `
      <div class="card-box">
        <div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
          <span style="padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700; border:1px solid; background:${statusBg}">${t.status}</span>
          ${t.target_bc ? `<button class="entity-pill pill-bc" onclick="window.filterByBc('${t.target_bc}')">BC: ${t.target_bc}</button>` : ""}
          ${t.target_release ? `<span class="entity-pill pill-prd">Release ${t.target_release}</span>` : ""}
          ${t.priority_rank < 900000 ? `<span class="entity-pill" style="color:#94a3b8">Rank #${t.priority_rank}</span>` : ""}
        </div>
      </div>
      ${t.target_bc ? `
      <div class="card-box" id="task-bc-field">
        <div class="card-box-title" style="display:flex; justify-content:space-between; align-items:center;">
          <span>Target Bounded Context</span>
          <button class="entity-pill pill-bc" onclick="window.filterByBc('${t.target_bc}')" title="Filter graph by ${t.target_bc}">BC: ${t.target_bc}</button>
        </div>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:6px;">Related tasks in ${t.target_bc}:</div>
        <div class="pills-container" id="related-bc-tasks">
          ${(function() {
            const rel = (data.tasks || []).filter(o => (o.target_bc === t.target_bc || o.bc === t.target_bc) && o.id !== t.id);
            if (!rel.length) return '<span style="color:var(--text-muted); font-size:0.75rem;">None</span>';
            return rel.map(r => `<button class="entity-pill pill-task" onclick="openDrawer('${r.id}')">${r.id}</button>`).join("");
          })()}
        </div>
      </div>` : ""}
      <div class="card-box">
        <div class="card-box-title"><span>Git Commits & Pull Requests</span><span>${commits.length} commits / ${prs.length} PRs</span></div>
        ${prs.length > 0 ? `<div class="pills-container"><span style="font-size:0.75rem; color:var(--text-muted); align-self:center;">Pull Requests:</span>${prs.map(p => `<span class="entity-pill pill-story">🔀 ${p}</span>`).join("")}</div>` : ""}
        ${commits.length > 0 ? `<div style="display:flex; flex-direction:column; gap:6px; max-height:180px; overflow-y:auto;">${commits.map(c => `
          <div class="commit-row"><div class="commit-meta"><span class="commit-hash">${c.hash}</span><span class="commit-date">${c.date} by ${c.author}</span></div><div class="commit-subject">${c.subject}</div></div>`).join("")}</div>` : `<p style="font-size:0.76rem; color:var(--text-muted); font-style:italic;">No linked git commits detected. Commits referencing <code>task-XXXX</code> or frontmatter <code>prs:</code> link automatically.</p>`}
      </div>
      <div class="card-box">
        <div class="card-box-title">Traceability & Governance</div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.78rem;">
          <div><div style="color:var(--text-muted); font-weight:600; margin-bottom:4px;">Governing ADRs:</div><div class="pills-container">${t.governing_adrs && t.governing_adrs.length ? t.governing_adrs.map(a => pill(a, "adr")).join("") : '<span style="color:var(--text-muted)">None</span>'}</div></div>
          <div><div style="color:var(--text-muted); font-weight:600; margin-bottom:4px;">Dependencies:</div><div class="pills-container">${t.dependencies && t.dependencies.length ? t.dependencies.map(d => pill(d, "task")).join("") : '<span style="color:var(--text-muted)">None</span>'}</div></div>
          <div><div style="color:var(--text-muted); font-weight:600; margin-bottom:4px;">Governing Stories:</div><div class="pills-container">${t.governing_stories && t.governing_stories.length ? t.governing_stories.map(s => `<button class="entity-pill pill-story highlighted-story" onclick="openDrawer('${s}')">${s}</button>`).join("") : '<span style="color:var(--text-muted)">None</span>'}</div></div>
          <div><div style="color:var(--text-muted); font-weight:600; margin-bottom:4px;">Governing PRDs:</div><div class="pills-container">${t.governing_prds && t.governing_prds.length ? t.governing_prds.map(p => pill(p, "prd")).join("") : '<span style="color:var(--text-muted)">None</span>'}</div></div>
        </div>
      </div>
      <div class="card-box"><div class="card-box-title">Specification Content</div><div class="markdown-box">${renderMarkdown(t.body || t.raw_markdown)}</div></div>
      ${typeof window.renderTaskComplianceCard === "function" ? window.renderTaskComplianceCard(t) : ""}
    `;
  }

  function renderStoryCard(s) {
    return `
      <div class="card-box">
        <div style="display:flex; gap:8px; align-items:center;">
          <span class="entity-pill pill-story">Persona: ${s.persona || 'Alex'}</span>
          ${s.governing_prd ? `<span class="entity-pill pill-prd" onclick="openDrawer('${s.governing_prd}')">PRD: ${s.governing_prd}</span>` : ""}
          <button class="uat-receipt-btn" onclick="window.exportUatReceipt('${s.feature || s.id}', '${s.governing_prd || 'PRD-0005'}', ${JSON.stringify(s.scenarios || [])}, event)" style="margin-left:auto;">📄 Export UAT Verification Receipt</button>
        </div>
      </div>
      ${(s.as_a || s.i_want || s.so_that) ? `
        <div class="card-box">
          <div class="card-box-title">User Value Proposition</div>
          <div style="display:flex; flex-direction:column; gap:6px; font-size:0.84rem;">
            ${s.as_a ? `<div><strong style="color:#67e8f9">As an:</strong> ${s.as_a}</div>` : ""}
            ${s.i_want ? `<div><strong style="color:#67e8f9">I want:</strong> ${s.i_want}</div>` : ""}
            ${s.so_that ? `<div><strong style="color:#67e8f9">So that:</strong> ${s.so_that}</div>` : ""}
          </div>
        </div>` : ""}
      ${(s.scenarios && s.scenarios.length > 0) ? `
        <div class="card-box">
          <div class="card-box-title">Acceptance Criteria (BDD Scenarios)</div>
          <div style="display:flex; flex-direction:column; gap:6px;">
            ${s.scenarios.map(sc => `
              <div style="background:rgba(15,23,42,0.6); border:1px solid var(--border-subtle); border-radius:6px; padding:8px 10px; font-size:0.8rem; display:flex; gap:8px; align-items:flex-start;">
                <span style="color:#10b981; font-weight:bold;">✓</span><span style="color:#e2e8f0;">${sc}</span>
              </div>`).join("")}
          </div>
        </div>` : ""}
      ${(s.implementing_tasks && s.implementing_tasks.length > 0) ? `
        <div class="card-box"><div class="card-box-title">Implementing Backlog Tasks</div><div class="pills-container">${s.implementing_tasks.map(t => pill(t, "task")).join("")}</div></div>` : ""}
      <div class="card-box"><div class="card-box-title">Full Specification Markdown</div><div class="markdown-box">${renderMarkdown(s.raw_markdown)}</div></div>
    `;
  }

  function renderPrdCard(p) {
    return `
      <div class="card-box">
        <div style="display:flex; gap:8px; align-items:center;">
          <span style="padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700; background:rgba(244,63,94,0.2); color:#fda4af; border:1px solid rgba(244,63,94,0.4)">${p.status}</span>
          ${p.target_persona ? `<span class="entity-pill pill-persona" onclick="openDrawer('${p.target_persona}')">Target: ${p.target_persona}</span>` : ""}
        </div>
      </div>
      ${p.problem_statement ? `<div class="card-box"><div class="card-box-title" style="color:#fda4af">Problem Statement</div><div class="markdown-box">${renderMarkdown(p.problem_statement)}</div></div>` : ""}
      ${(p.outcomes && p.outcomes.length > 0) ? `
        <div class="card-box">
          <div class="card-box-title">Checkable Outcomes</div>
          <div style="display:flex; flex-direction:column; gap:6px;">
            ${p.outcomes.map(o => `
              <div style="background:rgba(15,23,42,0.6); border:1px solid var(--border-subtle); border-radius:6px; padding:8px 10px; font-size:0.8rem; display:flex; gap:8px;">
                <span style="color:#f43f5e; font-weight:bold;">•</span><span style="color:#e2e8f0;">${o}</span>
              </div>`).join("")}
          </div>
        </div>` : ""}
      <div class="card-box">
        <div class="card-box-title">Traceability Links</div>
        <div style="display:flex; flex-direction:column; gap:8px;">
          <div><div style="color:var(--text-muted); font-size:0.76rem; font-weight:600; margin-bottom:4px;">Linked User Stories:</div><div class="pills-container">${p.linked_stories && p.linked_stories.length ? p.linked_stories.map(s => pill(s, "story")).join("") : '<span style="color:var(--text-muted)">None</span>'}</div></div>
          <div><div style="color:var(--text-muted); font-size:0.76rem; font-weight:600; margin-bottom:4px;">Implementing Tasks:</div><div class="pills-container">${p.tasks && p.tasks.length ? p.tasks.map(t => pill(t, "task")).join("") : '<span style="color:var(--text-muted)">None</span>'}</div></div>
        </div>
      </div>
      <div class="card-box"><div class="card-box-title">Full PRD Markdown</div><div class="markdown-box">${renderMarkdown(p.raw_markdown)}</div></div>
    `;
  }

  function renderAdrCard(a) {
    return `
      <div class="card-box">
        <div style="display:flex; gap:8px; align-items:center;">
          <span style="padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700; background:rgba(99,102,241,0.2); color:#a5b4fc; border:1px solid rgba(99,102,241,0.4)">${a.status}</span>
          <span class="entity-pill pill-adr">${a.domain || 'Architecture'}</span>
        </div>
      </div>
      ${a.context ? `<div class="card-box"><div class="card-box-title" style="color:#a5b4fc">Context</div><div class="markdown-box">${renderMarkdown(a.context)}</div></div>` : ""}
      ${a.decision ? `<div class="card-box"><div class="card-box-title" style="color:#c4b5fd">Decision</div><div class="markdown-box">${renderMarkdown(a.decision)}</div></div>` : ""}
      ${a.consequences ? `<div class="card-box"><div class="card-box-title" style="color:#94a3b8">Consequences</div><div class="markdown-box">${renderMarkdown(a.consequences)}</div></div>` : ""}
      ${(a.implementing_tasks && a.implementing_tasks.length > 0) ? `
        <div class="card-box"><div class="card-box-title">Implementing Tasks (${a.implementing_tasks.length})</div><div class="pills-container">${a.implementing_tasks.map(t => pill(t, "task")).join("")}</div></div>` : ""}
      <div class="card-box"><div class="card-box-title">Full ADR Markdown</div><div class="markdown-box">${renderMarkdown(a.raw_markdown)}</div></div>
    `;
  }

  function renderPersonaCard(p) {
    return `
      <div class="card-box">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:42px; height:42px; border-radius:10px; background:#f59e0b; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:1.2rem; color:#fff;">${(p.name || 'P')[0]}</div>
          <div><div style="font-weight:700; font-size:1.05rem; color:#fff;">${p.name}</div><div style="font-size:0.78rem; color:var(--text-muted);">${p.role || ''}</div></div>
        </div>
      </div>
      ${(p.pain_points && p.pain_points.length > 0) ? `
        <div class="card-box">
          <div class="card-box-title" style="color:#f59e0b">Pain Points</div>
          <div style="display:flex; flex-direction:column; gap:6px;">${p.pain_points.map(pt => `<div style="font-size:0.8rem; display:flex; gap:8px; color:#e2e8f0;"><span>⚠️</span><span>${pt}</span></div>`).join("")}</div>
        </div>` : ""}
      ${(p.goals && p.goals.length > 0) ? `
        <div class="card-box">
          <div class="card-box-title" style="color:#10b981">Goals with SpecOps</div>
          <div style="display:flex; flex-direction:column; gap:6px;">${p.goals.map(g => `<div style="font-size:0.8rem; display:flex; gap:8px; color:#e2e8f0;"><span>🎯</span><span>${g}</span></div>`).join("")}</div>
        </div>` : ""}
      ${(p.story_ids && p.story_ids.length > 0) ? `
        <div class="card-box">
          <div class="card-box-title">Desired User Stories</div>
          <div class="pills-container">${p.story_ids.map(s => pill(s, "story")).join("")}</div>
        </div>` : ""}
      <div class="card-box"><div class="card-box-title">Full Persona Profile</div><div class="markdown-box">${renderMarkdown(p.raw_markdown)}</div></div>
    `;
  }

  function renderBcCard(b) {
    const bcName = b.id || b.name || b.bc || "";
    return `
      <div class="card-box">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="entity-pill pill-bc">Architectural Boundary</span>
          <button class="ctrl-btn" onclick="window.filterByBc('${bcName}')" title="Isolate this Bounded Context on Graph">🔍 Isolate on Graph</button>
        </div>
      </div>
      <div class="card-box">
        <div class="card-box-title">Deployed Tasks (${(b.tasks || []).length})</div>
        <div class="pills-container">${b.tasks && b.tasks.length ? b.tasks.map(t => pill(t, "task")).join("") : '<span style="color:var(--text-muted)">None</span>'}</div>
      </div>
    `;
  }

  window.filterByBc = function(bcName, targetTab) {
    if (!bcName) return;
    window.setFilter('bc', bcName);
    if (targetTab) {
      window.switchTab(targetTab);
    } else if (activeTab !== 'graph') {
      window.switchTab('graph');
    }
    if (typeof updateGraphToolbarUI === "function") updateGraphToolbarUI();
    if (typeof wakePhysics === "function") wakePhysics();
  };

  window.openDrawer = function(id) {
    const match = findEntity(id);
    if (!match) return;

    const { entity, type } = match;
    currentEntity = entity;

    const badge = document.getElementById("drawer-type-badge");
    const titleEl = document.getElementById("drawer-title");
    const filepathEl = document.getElementById("drawer-filepath-text");
    const bodyEl = document.getElementById("drawer-body");
    const copyBtn = document.getElementById("drawer-copy-btn");
    const permalinkBtn = document.getElementById("drawer-permalink-btn");

    if (badge) {
      badge.textContent = type;
      const typeColors = {
        TASK: "background:rgba(139,92,246,0.25); color:#c4b5fd; border:1px solid rgba(139,92,246,0.5)",
        STORY: "background:rgba(6,182,212,0.25); color:#67e8f9; border:1px solid rgba(6,182,212,0.5)",
        PRD: "background:rgba(244,63,94,0.25); color:#fda4af; border:1px solid rgba(244,63,94,0.5)",
        ADR: "background:rgba(99,102,241,0.25); color:#a5b4fc; border:1px solid rgba(99,102,241,0.5)",
        PERSONA: "background:rgba(245,158,11,0.25); color:#fde68a; border:1px solid rgba(245,158,11,0.5)",
        "BOUNDED CONTEXT": "background:rgba(236,72,153,0.25); color:#f472b6; border:1px solid rgba(236,72,153,0.5)",
      };
      badge.style = typeColors[type] || typeColors.TASK;
    }

    if (titleEl) titleEl.textContent = (entity.name || entity.id) + (entity.title ? ": " + entity.title : "");
    if (filepathEl) filepathEl.textContent = entity.file_path || "docs/project/";
    if (copyBtn) copyBtn.style.display = entity.file_path ? "inline-block" : "none";
    if (permalinkBtn) permalinkBtn.style.display = "inline-block";

    if (bodyEl) {
      if (type === "TASK") bodyEl.innerHTML = renderTaskCard(entity);
      else if (type === "STORY") bodyEl.innerHTML = renderStoryCard(entity);
      else if (type === "PRD") bodyEl.innerHTML = renderPrdCard(entity);
      else if (type === "ADR") bodyEl.innerHTML = renderAdrCard(entity);
      else if (type === "PERSONA") bodyEl.innerHTML = renderPersonaCard(entity);
      else if (type === "BOUNDED CONTEXT") bodyEl.innerHTML = renderBcCard(entity);
      else bodyEl.innerHTML = "<p>No detailed view available.</p>";
    }

    document.getElementById("drawer").classList.add("open");
    const backdrop = document.getElementById("drawer-backdrop");
    if (backdrop) backdrop.classList.add("open");

    if (typeof activeTab !== "undefined" && activeTab === "graph" && window.focusNode) {
      window.focusNode(entity.id || id);
    }
    if (typeof updateUrl === "function" && !isSyncingFromUrl) {
      updateUrl(true);
    }
  };

  window.closeDrawer = function() {
    document.getElementById("drawer").classList.remove("open");
    const backdrop = document.getElementById("drawer-backdrop");
    if (backdrop) backdrop.classList.remove("open");
    currentEntity = null;
    if (typeof activeTab !== "undefined" && activeTab === "graph" && window.focusNode) {
      window.focusNode(null);
    }
    if (typeof updateUrl === "function" && !isSyncingFromUrl) {
      updateUrl(false);
    }
  };

  window.copyDeepLink = function(entityId, btnEl, event) {
    if (event && event.stopPropagation) {
      event.stopPropagation();
    }
    const targetId = entityId || (currentEntity ? (currentEntity.id || currentEntity.name) : null);
    const base = (typeof window !== "undefined" && window.location && window.location.href)
      ? window.location.href.split("#")[0]
      : (typeof location !== "undefined" && location.href ? location.href.split("#")[0] : "");

    let url = "";
    if (!entityId && currentEntity && typeof serializeHash === "function") {
      url = base + serializeHash();
    } else if (targetId) {
      const targetTab = (typeof activeTab !== "undefined" && activeTab) ? activeTab : "graph";
      url = `${base}#tab=${encodeURIComponent(targetTab)}&entity=${encodeURIComponent(targetId)}`;
    } else {
      url = (typeof window !== "undefined" && window.location) ? window.location.href : (typeof location !== "undefined" ? location.href : "");
    }

    let btn = btnEl;
    if (!btn && typeof document !== "undefined") {
      btn = document.getElementById("drawer-permalink-btn");
    }

    const showSuccess = () => {
      if (btn) {
        const prev = btn.textContent;
        btn.textContent = "✓ Copied URL!";
        setTimeout(() => { btn.textContent = prev; }, 1500);
      }
    };

    showSuccess();
    const nav = (typeof window !== "undefined" && window.navigator) || (typeof navigator !== "undefined" ? navigator : null);
    if (nav && nav.clipboard && nav.clipboard.writeText) {
      nav.clipboard.writeText(url).catch(() => {});
    }
    return url;
  };

  window.copyFilePath = function() {
    if (!currentEntity || !currentEntity.file_path) return;
    const nav = (typeof window !== "undefined" && window.navigator) || (typeof navigator !== "undefined" ? navigator : null);
    const showSuccess = () => {
      const btn = document.getElementById("drawer-copy-btn");
      if (btn) {
        const prev = btn.textContent;
        btn.textContent = "✓ Copied!";
        setTimeout(() => { btn.textContent = prev; }, 1500);
      }
    };
    if (nav && nav.clipboard && nav.clipboard.writeText) {
      nav.clipboard.writeText(currentEntity.file_path).then(showSuccess).catch(showSuccess);
    } else {
      showSuccess();
    }
  };

  canvas.addEventListener("click", e => {
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const { x, y } = screenToWorld(sx, sy);
    const clicked = nodes.find(n => Math.hypot(n.x - x, n.y - y) <= n.radius + 6);
    if (clicked) {
      window.openDrawer(clicked.id);
    }
  });

  window.addEventListener("keydown", e => {
    if (e.key === "Escape") window.closeDrawer();
  });
"""
