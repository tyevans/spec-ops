"""Client-side multi-view dashboard: Gantt, Kanban, PRDs, ADRs, Personas, and Faceted Filtering."""

VIEWS_JS = r"""
  let activeTab = "graph";
  const filterState = {
    query: "",
    status: "all",
    bc: "all",
    linked: null,
    hideDone: false,
    groupBy: "release",
  };

  window.switchTab = function(tabName) {
    activeTab = tabName;
    document.querySelectorAll(".tab-btn").forEach(btn => {
      if (btn.dataset.tab === tabName) btn.classList.add("active");
      else btn.classList.remove("active");
    });

    const canvasMain = document.getElementById("canvas-view");
    const dashboardMain = document.getElementById("dashboard-view");
    const graphControls = document.getElementById("graph-controls");

    if (tabName === "graph") {
      if (canvasMain) canvasMain.style.display = "flex";
      if (dashboardMain) dashboardMain.style.display = "none";
      if (graphControls) graphControls.style.display = "flex";
    } else {
      if (canvasMain) canvasMain.style.display = "none";
      if (dashboardMain) dashboardMain.style.display = "flex";
      if (graphControls) graphControls.style.display = "none";
      renderActiveView();
    }
  };

  window.setFilter = function(key, val) {
    filterState[key] = val;
    renderActiveView();
  };

  window.filterByLinked = function(id, targetTab) {
    filterState.linked = id;
    if (targetTab) {
      window.switchTab(targetTab);
    } else {
      renderActiveView();
    }
  };

  window.clearLinkedFilter = function() {
    filterState.linked = null;
    renderActiveView();
  };

  function getFilteredTasks() {
    const tasks = data.tasks || [];
    const q = filterState.query.toLowerCase().trim();

    return tasks.filter(t => {
      if (filterState.hideDone && t.status === "Complete") return false;
      if (filterState.status !== "all" && t.status !== filterState.status) return false;
      if (filterState.bc !== "all" && t.target_bc !== filterState.bc) return false;

      if (filterState.linked) {
        const lid = filterState.linked.toUpperCase();
        const matchesPrd = (t.governing_prds || []).some(p => p.toUpperCase().includes(lid));
        const matchesAdr = (t.governing_adrs || []).some(a => a.toUpperCase().includes(lid));
        const matchesStory = (t.governing_stories || []).some(s => s.toUpperCase().includes(lid));
        const matchesDep = (t.dependencies || []).some(d => d.toUpperCase().includes(lid));
        const matchesSelf = t.id.toUpperCase().includes(lid);
        if (!matchesPrd && !matchesAdr && !matchesStory && !matchesDep && !matchesSelf) return false;
      }

      if (q) {
        const match = t.id.toLowerCase().includes(q) ||
                      t.title.toLowerCase().includes(q) ||
                      (t.target_bc && t.target_bc.toLowerCase().includes(q)) ||
                      (t.body && t.body.toLowerCase().includes(q));
        if (!match) return false;
      }
      return true;
    });
  }

  function renderFilterBar() {
    const bcs = Array.from(new Set((data.tasks || []).map(t => t.target_bc).filter(Boolean))).sort();

    return `
      <div class="view-filter-bar">
        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; flex:1;">
          <input type="text" class="filter-input" placeholder="Filter by name, ID, or text..." value="${filterState.query}" oninput="window.setFilter('query', this.value)">
          
          <select class="filter-select" onchange="window.setFilter('status', this.value)">
            <option value="all" ${filterState.status === 'all' ? 'selected' : ''}>All Statuses</option>
            <option value="Complete" ${filterState.status === 'Complete' ? 'selected' : ''}>Complete</option>
            <option value="Refined" ${filterState.status === 'Refined' ? 'selected' : ''}>Refined</option>
            <option value="Proposed" ${filterState.status === 'Proposed' ? 'selected' : ''}>Proposed</option>
          </select>

          <select class="filter-select" onchange="window.setFilter('bc', this.value)">
            <option value="all" ${filterState.bc === 'all' ? 'selected' : ''}>All Bounded Contexts</option>
            ${bcs.map(bc => `<option value="${bc}" ${filterState.bc === bc ? 'selected' : ''}>${bc}</option>`).join("")}
          </select>

          <label class="filter-checkbox-label">
            <input type="checkbox" ${filterState.hideDone ? 'checked' : ''} onchange="window.setFilter('hideDone', this.checked)">
            <span>Hide Done</span>
          </label>

          ${activeTab === 'gantt' ? `
            <div style="display:flex; align-items:center; gap:4px; margin-left:auto;">
              <span style="font-size:0.75rem; color:var(--text-muted)">Group By:</span>
              <button class="ctrl-btn ${filterState.groupBy === 'release' ? 'active' : ''}" onclick="window.setFilter('groupBy', 'release')">Release</button>
              <button class="ctrl-btn ${filterState.groupBy === 'bc' ? 'active' : ''}" onclick="window.setFilter('groupBy', 'bc')">Bounded Context</button>
            </div>` : ""}
        </div>

        ${filterState.linked ? `
          <div class="active-filter-chip">
            <span>Linked to: <b>${filterState.linked}</b></span>
            <button onclick="window.clearLinkedFilter()" title="Clear filter">&times;</button>
          </div>` : ""}
      </div>
    `;
  }

  function renderActiveView() {
    const container = document.getElementById("dashboard-content");
    if (!container) return;

    let html = renderFilterBar();
    if (activeTab === "gantt") html += renderGanttView();
    else if (activeTab === "kanban") html += renderKanbanView();
    else if (activeTab === "prds") html += renderPrdsView();
    else if (activeTab === "adrs") html += renderAdrsView();
    else if (activeTab === "personas") html += renderPersonasView();

    container.innerHTML = html;
  }

  // --- 1. Gantt Timeline View ---
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
                    <div class="gantt-item-row" onclick="openDrawer('${t.id}')">
                      <div style="display:flex; align-items:center; gap:10px; width:220px; flex-shrink:0;">
                        <span class="entity-pill ${statusCls}">${t.id}</span>
                        <span style="font-size:0.75rem; color:var(--text-muted); font-mono">${t.status}</span>
                      </div>
                      <div style="flex:1; min-width:0; padding-right:15px;">
                        <div style="font-size:0.84rem; font-weight:600; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${t.title}</div>
                        <div style="font-size:0.74rem; color:var(--text-muted); margin-top:2px;">
                          ${t.target_bc ? `<span style="color:#67e8f9; margin-right:8px;">BC: ${t.target_bc}</span>` : ""}
                          ${t.governing_prds && t.governing_prds.length ? `<span>PRD: ${t.governing_prds.join(", ")}</span>` : ""}
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

  // --- 2. Kanban Board View ---
  function renderKanbanView() {
    const tasks = getFilteredTasks();
    const columns = [
      { id: "Proposed", title: "Candidate Backlog", color: "#8b5cf6", border: "rgba(139,92,246,0.3)" },
      { id: "Refined", title: "Refined Buffer (Ready)", color: "#f59e0b", border: "rgba(245,158,11,0.3)" },
      { id: "Complete", title: "Complete / Shipped", color: "#10b981", border: "rgba(16,185,129,0.3)" },
    ];

    return `
      <div class="kanban-grid">
        ${columns.map(col => {
          if (filterState.hideDone && col.id === "Complete") return "";
          const items = tasks.filter(t => t.status === col.id);

          return `
            <div class="kanban-col">
              <div class="kanban-col-header" style="border-top: 3px solid ${col.color};">
                <span style="font-weight:700; color:#fff;">${col.title}</span>
                <span class="count-badge" style="background:${col.color}25; color:${col.color}">${items.length}</span>
              </div>
              <div class="kanban-cards-area">
                ${items.map(t => `
                  <div class="kanban-card" onclick="openDrawer('${t.id}')">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                      <span class="entity-pill pill-task" style="font-size:0.72rem;">${t.id}</span>
                      ${t.target_bc ? `<span style="font-size:0.7rem; color:#67e8f9; font-mono">BC: ${t.target_bc}</span>` : ""}
                    </div>
                    <h4 style="font-size:0.83rem; font-weight:600; color:#fff; line-height:1.35; margin-bottom:8px;">${t.title}</h4>
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.72rem; color:var(--text-muted); border-top:1px solid var(--border-subtle); padding-top:6px;">
                      <span>${(t.prs || []).length} PRs · ${(t.commits || []).length} commits</span>
                      ${t.dependencies && t.dependencies.length ? `<span title="Dependencies">⛓️ ${t.dependencies.length}</span>` : ""}
                    </div>
                  </div>`).join("")}
                ${items.length === 0 ? `<div style="padding:20px; text-align:center; color:var(--text-muted); font-size:0.78rem; font-style:italic;">No tasks in this lane</div>` : ""}
              </div>
            </div>`;
        }).join("")}
      </div>
    `;
  }

  // --- 3. PRDs & Feature Matrix View ---
  function renderPrdsView() {
    const prds = data.prds || [];
    const q = filterState.query.toLowerCase().trim();
    const filtered = prds.filter(p => !q || p.id.toLowerCase().includes(q) || p.title.toLowerCase().includes(q) || (p.problem_statement && p.problem_statement.toLowerCase().includes(q)));

    return `
      <div style="display:flex; flex-direction:column; gap:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h2 style="font-size:1.05rem; font-weight:700; color:#fff;">Product Requirement Documents (PRDs)</h2>
          <span style="font-size:0.78rem; color:var(--text-muted);">${filtered.length} specifications documented</span>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(360px, 1fr)); gap:16px;">
          ${filtered.map(p => `
            <div class="card-box" style="cursor:default;">
              <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                  <span class="entity-pill pill-prd" style="margin-bottom:4px;" onclick="openDrawer('${p.id}')">${p.id}</span>
                  <h3 style="font-size:0.95rem; font-weight:700; color:#fff; cursor:pointer;" onclick="openDrawer('${p.id}')">${p.title}</h3>
                </div>
                <span style="padding:2px 8px; border-radius:9999px; font-size:0.72rem; font-weight:700; background:rgba(244,63,94,0.2); color:#fda4af;">${p.status}</span>
              </div>

              ${p.problem_statement ? `<p style="font-size:0.78rem; color:#cbd5e1; line-height:1.5; margin:6px 0; overflow:hidden; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical;">${p.problem_statement}</p>` : ""}

              <div style="margin-top:auto; padding-top:10px; border-top:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.74rem; color:var(--text-muted);">${(p.tasks || []).length} implementing tasks</span>
                <div style="display:flex; gap:6px;">
                  <button class="ctrl-btn" onclick="window.filterByLinked('${p.id}', 'kanban')" title="Filter Kanban board by this PRD">📋 View Tasks</button>
                  <button class="ctrl-btn" onclick="openDrawer('${p.id}')">Inspect</button>
                </div>
              </div>
            </div>`).join("")}
        </div>
      </div>
    `;
  }

  // --- 4. ADR Architecture View ---
  function renderAdrsView() {
    const adrs = data.adrs || [];
    const q = filterState.query.toLowerCase().trim();
    const filtered = adrs.filter(a => !q || a.id.toLowerCase().includes(q) || a.title.toLowerCase().includes(q) || (a.domain && a.domain.toLowerCase().includes(q)) || (a.decision && a.decision.toLowerCase().includes(q)));

    return `
      <div style="display:flex; flex-direction:column; gap:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h2 style="font-size:1.05rem; font-weight:700; color:#fff;">Architectural Decision Records (ADRs)</h2>
          <span style="font-size:0.78rem; color:var(--text-muted);">${filtered.length} governance records</span>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(360px, 1fr)); gap:16px;">
          ${filtered.map(a => `
            <div class="card-box">
              <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                  <span class="entity-pill pill-adr" style="margin-bottom:4px;" onclick="openDrawer('${a.id}')">${a.id}</span>
                  <h3 style="font-size:0.95rem; font-weight:700; color:#fff; cursor:pointer;" onclick="openDrawer('${a.id}')">${a.title}</h3>
                </div>
                <span class="entity-pill" style="font-size:0.7rem; color:#a5b4fc;">${a.domain || 'Architecture'}</span>
              </div>

              ${a.decision ? `
                <div style="font-size:0.78rem; color:#cbd5e1; line-height:1.5; margin:6px 0;">
                  <strong style="color:#c4b5fd;">Decision:</strong> ${a.decision.substring(0, 140)}...
                </div>` : ""}

              <div style="margin-top:auto; padding-top:10px; border-top:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.74rem; color:var(--text-muted);">${(a.implementing_tasks || []).length} implementing tasks</span>
                <div style="display:flex; gap:6px;">
                  <button class="ctrl-btn" onclick="window.filterByLinked('${a.id}', 'kanban')" title="Filter Kanban board by this ADR">📋 View Tasks</button>
                  <button class="ctrl-btn" onclick="openDrawer('${a.id}')">Inspect</button>
                </div>
              </div>
            </div>`).join("")}
        </div>
      </div>
    `;
  }

  // --- 5. Personas & Stories Studio View ---
  function renderPersonasView() {
    const personas = data.personas || [];
    const stories = data.stories || [];

    return `
      <div style="display:flex; flex-direction:column; gap:20px;">
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px;">
          ${personas.map(p => `
            <div class="card-box" onclick="openDrawer('${p.id}')" style="cursor:pointer;">
              <div style="display:flex; align-items:center; gap:12px;">
                <div style="width:40px; height:40px; border-radius:10px; background:#f59e0b; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:1.1rem; color:#fff;">
                  ${(p.name || 'P')[0]}
                </div>
                <div>
                  <h3 style="font-size:0.95rem; font-weight:700; color:#fff;">${p.name}</h3>
                  <p style="font-size:0.74rem; color:var(--text-muted);">${p.role || ''}</p>
                </div>
              </div>
              <div style="margin-top:8px; font-size:0.76rem; color:#94a3b8;">
                ${(p.story_ids || []).length} desired user stories
              </div>
            </div>`).join("")}
        </div>

        <div style="display:flex; flex-direction:column; gap:12px; margin-top:10px;">
          <h3 style="font-size:0.95rem; font-weight:700; color:#fff;">User Stories Catalog</h3>
          <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:14px;">
            ${stories.map(s => `
              <div class="card-box" onclick="openDrawer('${s.id}')" style="cursor:pointer;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:4px;">
                  <span class="entity-pill pill-story" style="font-size:0.72rem;">${s.id}</span>
                  <span style="font-size:0.7rem; color:#67e8f9;">${s.persona || 'Alex'}</span>
                </div>
                <h4 style="font-size:0.85rem; font-weight:600; color:#fff; line-height:1.35; margin-bottom:6px;">${s.title}</h4>
                ${s.i_want ? `<p style="font-size:0.76rem; color:#cbd5e1; line-height:1.4;">${s.i_want}</p>` : ""}
              </div>`).join("")}
          </div>
        </div>
      </div>
    `;
  }
"""
