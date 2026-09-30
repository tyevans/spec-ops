"""Client-side URL hash routing and bidirectional state synchronization."""
from __future__ import annotations

ROUTING_JS = r"""
  var isSyncingFromUrl = false;

  function parseHash(hashStr) {
    let hash = hashStr !== undefined ? hashStr : window.location.hash;
    if (hash.startsWith("#")) hash = hash.substring(1);
    if (hash.startsWith("/")) hash = hash.substring(1);

    const params = new URLSearchParams(hash);

    const validTabs = ["graph", "matrix", "gantt", "kanban", "prds", "adrs", "personas", "lead", "security"];
    let tab = (params.get("tab") || "graph").toLowerCase();
    if (!validTabs.includes(tab)) tab = "graph";

    const filter = params.get("filter") || "";
    const q = params.get("q") || params.get("query") || filter;

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

    const rawTypes = params.get("types");
    let types = null;
    if (rawTypes) {
      types = rawTypes.split(",").map(t => t.trim().toLowerCase()).filter(Boolean);
    }

    const hops = params.get("hops") || "all";
    const preset = params.get("preset") || null;

    const linked = params.get("linked") || null;
    let entity = params.get("entity") || null;

    if (!entity && hash && !hash.includes("=") && !hash.includes("&")) {
      const trimmed = hash.trim();
      if (trimmed) entity = trimmed;
    }

    return { tab, q, status, bc, hideDone, groupBy, linked, entity, types, hops, preset };
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
    if (typeof graphFilterState !== "undefined" && graphFilterState.types) {
      if (typeof ALL_ENTITY_TYPES !== "undefined" && graphFilterState.types.size < ALL_ENTITY_TYPES.length) {
        parts.push(`types=${encodeURIComponent(Array.from(graphFilterState.types).join(","))}`);
      }
      if (graphFilterState.hops && graphFilterState.hops !== "all") {
        parts.push(`hops=${encodeURIComponent(graphFilterState.hops)}`);
      }
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

    if (typeof graphFilterState !== "undefined") {
      if (state.types && Array.isArray(state.types) && state.types.length > 0) {
        graphFilterState.types = new Set(state.types);
      }
      if (state.hops) {
        graphFilterState.hops = state.hops;
      }
      if (state.groupBy === "bc") {
        graphFilterState.preset = "bc";
      } else if (state.preset) {
        graphFilterState.preset = state.preset;
      }
    }

    searchQuery = filterState.query;
    const searchInput = document.getElementById("search-input");
    if (searchInput) searchInput.value = filterState.query;

    if (typeof updateGraphToolbarUI === "function") {
      updateGraphToolbarUI();
    }
    if (typeof wakePhysics === "function") {
      wakePhysics();
    }

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
