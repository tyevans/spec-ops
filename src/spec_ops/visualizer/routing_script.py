"""Client-side URL hash routing and bidirectional state synchronization."""
from __future__ import annotations

ROUTING_JS = r"""
  var isSyncingFromUrl = false;

  function parseHash(hashStr) {
    let hash = hashStr !== undefined ? hashStr : window.location.hash;
    if (hash.startsWith("#")) hash = hash.substring(1);
    if (hash.startsWith("/")) hash = hash.substring(1);

    const params = new URLSearchParams(hash);

    const validTabs = ["graph", "gantt", "kanban", "prds", "adrs", "personas"];
    let tab = (params.get("tab") || "graph").toLowerCase();
    if (!validTabs.includes(tab)) tab = "graph";

    const q = params.get("q") || params.get("query") || "";

    const rawStatus = (params.get("status") || "all").toLowerCase();
    let status = "all";
    if (rawStatus === "complete") status = "Complete";
    else if (rawStatus === "refined") status = "Refined";
    else if (rawStatus === "proposed") status = "Proposed";

    const bc = params.get("bc") || "all";

    const rawHideDone = params.get("hideDone");
    const hideDone = rawHideDone === "true" || rawHideDone === "1";

    const rawGroupBy = params.get("groupBy");
    const groupBy = rawGroupBy === "bc" ? "bc" : "release";

    const linked = params.get("linked") || null;
    const entity = params.get("entity") || null;

    return { tab, q, status, bc, hideDone, groupBy, linked, entity };
  }

  function serializeHash() {
    const parts = [];
    parts.push(`tab=${encodeURIComponent(activeTab || "graph")}`);
    if (filterState.query && filterState.query.trim()) {
      parts.push(`q=${encodeURIComponent(filterState.query.trim())}`);
    }
    if (filterState.status && filterState.status !== "all") {
      parts.push(`status=${encodeURIComponent(filterState.status)}`);
    }
    if (filterState.bc && filterState.bc !== "all") {
      parts.push(`bc=${encodeURIComponent(filterState.bc)}`);
    }
    if (filterState.hideDone) {
      parts.push("hideDone=true");
    }
    if (filterState.groupBy && filterState.groupBy !== "release") {
      parts.push(`groupBy=${encodeURIComponent(filterState.groupBy)}`);
    }
    if (filterState.linked) {
      parts.push(`linked=${encodeURIComponent(filterState.linked)}`);
    }
    if (currentEntity && (currentEntity.id || currentEntity.name)) {
      parts.push(`entity=${encodeURIComponent(currentEntity.id || currentEntity.name)}`);
    }
    return "#" + parts.join("&");
  }

  function updateUrl(push = false) {
    if (isSyncingFromUrl) return;
    const newHash = serializeHash();
    if (window.location.hash !== newHash) {
      if (push) {
        history.pushState(null, "", newHash);
      } else {
        history.replaceState(null, "", newHash);
      }
    }
  }

  function applyState(state) {
    const targetTab = state.tab || "graph";
    internalSwitchTab(targetTab);

    filterState.query = state.q || "";
    filterState.status = state.status || "all";
    filterState.bc = state.bc || "all";
    filterState.hideDone = Boolean(state.hideDone);
    filterState.groupBy = state.groupBy || "release";
    filterState.linked = state.linked || null;

    searchQuery = filterState.query;
    const searchInput = document.getElementById("search-input");
    if (searchInput) searchInput.value = filterState.query;

    if (activeTab !== "graph") {
      renderActiveView();
    }

    if (state.entity) {
      window.openDrawer(state.entity);
      if (activeTab === "graph" && window.focusNode) {
        window.focusNode(state.entity);
      }
    } else {
      window.closeDrawer();
    }
  }

  function onHistoryChange() {
    isSyncingFromUrl = true;
    try {
      const state = parseHash(window.location.hash);
      applyState(state);
    } finally {
      isSyncingFromUrl = false;
    }
  }

  window.parseHash = parseHash;
  window.serializeHash = serializeHash;
  window.addEventListener("popstate", onHistoryChange);
  window.addEventListener("hashchange", onHistoryChange);

  (function initRouter() {
    const hash = window.location.hash;
    if (hash && hash.length > 1) {
      isSyncingFromUrl = true;
      try {
        const state = parseHash(hash);
        applyState(state);
      } finally {
        isSyncingFromUrl = false;
      }
    } else {
      history.replaceState(null, "", "#tab=graph");
    }
  })();
"""
