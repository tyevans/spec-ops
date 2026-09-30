"""Client-side URL hash routing and bidirectional state synchronization."""
from __future__ import annotations

from dataclasses import dataclass
import urllib.parse


@dataclass
class VisualizerUrlState:
    tab: str = "graph"
    query: str = ""
    status: str = "all"
    bc: str = "all"
    hide_done: bool = False
    group_by: str = "release"
    linked: str | None = None
    entity: str | None = None
    focus: str | None = None
    persona: str = "all"
    milestone: str = "all"
    types: list[str] | None = None
    hops: str = "all"
    preset: str | None = None


def parse_url_hash(hash_str: str) -> VisualizerUrlState:
    """Parse a browser URL hash string into structured visualizer state."""
    raw = hash_str
    if raw.startswith("#"):
        raw = raw[1:]
    if raw.startswith("/"):
        raw = raw[1:]

    if not raw:
        return VisualizerUrlState()

    if "=" not in raw and "&" not in raw:
        trimmed = raw.strip()
        return VisualizerUrlState(tab="graph", entity=trimmed if trimmed else None)

    params = urllib.parse.parse_qs(raw, keep_blank_values=True)

    def get_first(key: str, default: str = "") -> str:
        vals = params.get(key)
        return vals[0] if vals and vals[0] is not None else default

    raw_tab = get_first("tab", "graph").lower()
    if raw_tab == "canvas":
        raw_tab = "graph"
    valid_tabs = {"graph", "matrix", "gantt", "kanban", "prds", "adrs", "personas", "lead", "security"}
    tab = raw_tab if raw_tab in valid_tabs else "graph"

    q = get_first("q") or get_first("query")
    status = "all"
    bc = get_first("bc", "all")
    persona = get_first("persona", "all")

    filter_param = get_first("filter")
    if filter_param:
        if filter_param.startswith("bc:"):
            bc = filter_param[3:]
        elif filter_param.startswith("status:"):
            raw_s = filter_param[7:].lower()
            if raw_s == "complete":
                status = "Complete"
            elif raw_s == "refined":
                status = "Refined"
            elif raw_s == "proposed":
                status = "Proposed"
        elif filter_param.startswith("persona:"):
            persona = filter_param[8:]
        elif not q:
            q = filter_param

    raw_status = (get_first("status") or status).lower()
    if raw_status == "complete":
        status = "Complete"
    elif raw_status == "refined":
        status = "Refined"
    elif raw_status == "proposed":
        status = "Proposed"
    else:
        status = "all"

    raw_hide = (get_first("hideDone") or get_first("hide_done")).lower()
    hide_done = raw_hide in ("true", "1")

    raw_group = (get_first("groupBy") or get_first("group_by")).lower()
    group_by = "bc" if raw_group == "bc" else "release"

    linked = get_first("linked") or None
    entity = get_first("entity") or None
    focus = get_first("focus") or None

    milestone = get_first("milestone", "all")

    raw_types = get_first("types")
    types = [t.strip().lower() for t in raw_types.split(",") if t.strip()] if raw_types else None

    hops = get_first("hops", "all")
    preset = get_first("preset") or None

    return VisualizerUrlState(
        tab=tab,
        query=q,
        status=status,
        bc=bc,
        hide_done=hide_done,
        group_by=group_by,
        linked=linked,
        entity=entity,
        focus=focus,
        persona=persona,
        milestone=milestone,
        types=types,
        hops=hops,
        preset=preset,
    )


def serialize_url_hash(state: VisualizerUrlState) -> str:
    """Serialize a VisualizerUrlState into a canonical URL hash string."""
    parts: list[str] = [f"tab={urllib.parse.quote(state.tab or 'graph')}"]
    if state.query and state.query.strip():
        parts.append(f"q={urllib.parse.quote(state.query.strip())}")
    if state.status and state.status != "all":
        parts.append(f"status={urllib.parse.quote(state.status)}")
    if state.bc and state.bc != "all":
        parts.append(f"bc={urllib.parse.quote(state.bc)}")
    if state.hide_done:
        parts.append("hideDone=true")
    if state.group_by and state.group_by != "release":
        parts.append(f"groupBy={urllib.parse.quote(state.group_by)}")
    if state.persona and state.persona != "all":
        parts.append(f"persona={urllib.parse.quote(state.persona)}")
    if state.milestone and state.milestone != "all":
        parts.append(f"milestone={urllib.parse.quote(state.milestone)}")
    if state.linked:
        parts.append(f"linked={urllib.parse.quote(state.linked)}")
    if state.types:
        parts.append(f"types={urllib.parse.quote(','.join(state.types))}")
    if state.hops and state.hops != "all":
        parts.append(f"hops={urllib.parse.quote(state.hops)}")
    if state.preset:
        parts.append(f"preset={urllib.parse.quote(state.preset)}")
    if state.entity:
        parts.append(f"entity={urllib.parse.quote(state.entity)}")
    if state.focus:
        parts.append(f"focus={urllib.parse.quote(state.focus)}")
    return "#" + "&".join(parts)


URL_ROUTER_JS = r"""
  var isSyncingFromUrl = false;

  function parseHash(hashStr) {
    let hash = hashStr !== undefined ? hashStr : window.location.hash;
    if (hash.startsWith("#")) hash = hash.substring(1);
    if (hash.startsWith("/")) hash = hash.substring(1);

    const params = new URLSearchParams(hash);

    const validTabs = ["graph", "matrix", "gantt", "kanban", "prds", "adrs", "personas", "lead", "security"];
    let rawTab = (params.get("tab") || "graph").toLowerCase();
    if (rawTab === "canvas") rawTab = "graph";
    let tab = validTabs.includes(rawTab) ? rawTab : "graph";

    let q = params.get("q") || params.get("query") || "";

    let status = "all";
    let bc = params.get("bc") || "all";
    let persona = params.get("persona") || "all";

    const filterParam = params.get("filter");
    if (filterParam) {
      if (filterParam.startsWith("bc:")) bc = filterParam.substring(3);
      else if (filterParam.startsWith("status:")) {
        const s = filterParam.substring(7).toLowerCase();
        if (s === "complete") status = "Complete";
        else if (s === "refined") status = "Refined";
        else if (s === "proposed") status = "Proposed";
      } else if (filterParam.startsWith("persona:")) persona = filterParam.substring(8);
      else if (!q) q = filterParam;
    }

    const rawStatus = (params.get("status") || status).toLowerCase();
    if (rawStatus === "complete") status = "Complete";
    else if (rawStatus === "refined") status = "Refined";
    else if (rawStatus === "proposed") status = "Proposed";

    const rawHideDone = params.get("hideDone") || params.get("hide_done");
    const hideDone = rawHideDone === "true" || rawHideDone === "1";

    const rawGroupBy = params.get("groupBy") || params.get("group_by");
    const groupBy = rawGroupBy === "bc" ? "bc" : "release";

    const rawTypes = params.get("types");
    let types = null;
    if (rawTypes) {
      types = rawTypes.split(",").map(t => t.trim().toLowerCase()).filter(Boolean);
    }

    const hops = params.get("hops") || "all";
    const preset = params.get("preset") || null;
    const linked = params.get("linked") || null;
    let focus = params.get("focus") || null;
    let entity = params.get("entity") || null;

    if (!entity && focus) entity = focus;

    if (!entity && hash && !hash.includes("=") && !hash.includes("&")) {
      const trimmed = hash.trim();
      if (trimmed) entity = trimmed;
    }

    const milestone = params.get("milestone") || "all";

    return { tab, q, status, bc, hideDone, groupBy, linked, entity, focus, persona, milestone, types, hops, preset };
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
    if (typeof matrixFilterState !== "undefined") {
      if (matrixFilterState.persona && matrixFilterState.persona !== "all") {
        parts.push(`persona=${encodeURIComponent(matrixFilterState.persona)}`);
      }
      if (matrixFilterState.milestone && matrixFilterState.milestone !== "all") {
        parts.push(`milestone=${encodeURIComponent(matrixFilterState.milestone)}`);
      }
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

    if (typeof matrixFilterState !== "undefined") {
      matrixFilterState.query = state.q || "";
      matrixFilterState.status = state.status || "all";
      matrixFilterState.bc = state.bc || "all";
      matrixFilterState.persona = state.persona || "all";
      matrixFilterState.milestone = state.milestone || "all";
    }

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

    const targetNode = state.focus || state.entity;
    if (targetNode && activeTab === "graph" && window.focusNode) {
      window.focusNode(targetNode, false, 1.5);
    }

    if (state.entity || state.focus) {
      window.openDrawer(state.entity || state.focus);
    } else {
      window.closeDrawer();
    }

    if (activeTab !== "graph") {
      renderActiveView();
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

ROUTING_JS = URL_ROUTER_JS
