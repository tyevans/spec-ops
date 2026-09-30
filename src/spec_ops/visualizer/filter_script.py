"""Client-side graph filtering, multi-hop reachability, perspective presets, and physics sleeping."""
from __future__ import annotations

FILTER_JS = r"""
  const ALL_ENTITY_TYPES = ["task", "story", "prd", "adr", "persona", "bc"];

  var graphFilterState = window.graphFilterState = window.graphFilterState || {
    types: new Set(ALL_ENTITY_TYPES),
    hops: "all",
    preset: "default",
  };

  let isPhysicsSleeping = false;
  let sleepFrameCounter = 0;

  function wakePhysics() {
    isPhysicsSleeping = false;
    sleepFrameCounter = 0;
    if (typeof updatePhysicsBtn === "function") updatePhysicsBtn();
  }

  function checkPhysicsSleep(totalVelocity) {
    if (!isPhysicsRunning || currentLayout !== "network" || draggedNode) {
      sleepFrameCounter = 0;
      return;
    }
    if (totalVelocity < 0.12) {
      sleepFrameCounter++;
      if (sleepFrameCounter > 40) {
        isPhysicsSleeping = true;
        if (typeof updatePhysicsBtn === "function") updatePhysicsBtn();
      }
    } else {
      sleepFrameCounter = 0;
    }
  }

  function computeReachableNodes(focusId, maxHops) {
    if (!focusId || maxHops === "all") return null;
    const hops = parseInt(maxHops, 10);
    if (isNaN(hops) || hops < 1) return null;

    const cleanFocus = String(focusId).toUpperCase();
    const startNode = nodes.find(n => matchNode(n, cleanFocus));
    if (!startNode) return null;

    const reachable = new Set([startNode.id]);
    let currentLevel = [startNode];

    for (let h = 0; h < hops; h++) {
      const nextLevel = [];
      currentLevel.forEach(curr => {
        links.forEach(l => {
          let neighbor = null;
          if (l.source.id === curr.id) neighbor = l.target;
          else if (l.target.id === curr.id) neighbor = l.source;

          if (neighbor && !reachable.has(neighbor.id)) {
            reachable.add(neighbor.id);
            nextLevel.push(neighbor);
          }
        });
      });
      currentLevel = nextLevel;
    }
    return reachable;
  }

  function isNodeVisible(n) {
    // 1. Entity type toggle
    if (!graphFilterState.types.has(n.type)) return false;

    // 2. Hide Done
    if (filterState.hideDone && n.type === "task" && n.status === "Complete") return false;

    // 3. Status filter
    if (filterState.status && filterState.status !== "all") {
      if (n.type === "task" && n.status !== filterState.status) return false;
      if (n.type === "prd" && n.status !== filterState.status) return false;
    }

    // 4. Bounded Context filter
    if (filterState.bc && filterState.bc !== "all") {
      const nodeBc = n.resolvedBc || n.bc;
      if (nodeBc !== filterState.bc && n.id !== filterState.bc) return false;
    }

    // 5. Linked filter
    if (filterState.linked) {
      const lid = filterState.linked.toUpperCase();
      const matchesSelf = n.id && n.id.toUpperCase().includes(lid);
      const connected = links.some(l => {
        const other = l.source === n ? l.target : (l.target === n ? l.source : null);
        return other && other.id && other.id.toUpperCase().includes(lid);
      });
      if (!matchesSelf && !connected) return false;
    }

    // 6. Search query
    if (searchQuery && typeof matchesSearch === "function" && !matchesSearch(n)) return false;

    // 7. Hop reachability filter
    if (graphFilterState.hops !== "all") {
      const targetEntity = focusedNodeId || (currentEntity && (currentEntity.id || currentEntity.name));
      if (targetEntity) {
        const reachable = computeReachableNodes(targetEntity, graphFilterState.hops);
        if (reachable && !reachable.has(n.id)) return false;
      }
    }

    return true;
  }

  function updateGraphToolbarUI() {
    const presetSelect = document.getElementById("graph-preset-select");
    if (presetSelect) presetSelect.value = graphFilterState.preset;

    const clusterBtn = document.getElementById("btn-cluster-bc");
    if (clusterBtn) {
      if (filterState.groupBy === "bc") clusterBtn.classList.add("active");
      else clusterBtn.classList.remove("active");
    }

    const bcSelect = document.getElementById("graph-bc-select");
    if (bcSelect) bcSelect.value = filterState.bc || "all";

    const statusSelect = document.getElementById("graph-status-select");
    if (statusSelect) statusSelect.value = filterState.status || "all";

    const hideDoneBtn = document.getElementById("graph-hide-done-btn");
    if (hideDoneBtn) {
      if (filterState.hideDone) hideDoneBtn.classList.add("active");
      else hideDoneBtn.classList.remove("active");
    }

    const hopSelect = document.getElementById("graph-hop-select");
    if (hopSelect) hopSelect.value = String(graphFilterState.hops);

    // Update entity type pills
    ALL_ENTITY_TYPES.forEach(t => {
      const pill = document.getElementById(`pill-toggle-${t}`);
      if (pill) {
        if (graphFilterState.types.has(t)) pill.classList.add("active");
        else pill.classList.remove("active");
      }
    });

    // Update count badge
    const countBadge = document.getElementById("graph-filter-count");
    if (countBadge) {
      const visibleNodes = nodes.filter(isNodeVisible).length;
      countBadge.textContent = `${visibleNodes} / ${nodes.length} nodes`;
    }
  }

  window.toggleTypeFilter = function(type) {
    if (graphFilterState.types.has(type)) {
      if (graphFilterState.types.size > 1) {
        graphFilterState.types.delete(type);
      }
    } else {
      graphFilterState.types.add(type);
    }
    graphFilterState.preset = "custom";
    updateGraphToolbarUI();
    wakePhysics();
    if (typeof updateUrl === "function" && !isSyncingFromUrl) updateUrl(false);
  };

  window.toggleHideDone = function() {
    filterState.hideDone = !filterState.hideDone;
    graphFilterState.preset = "custom";
    updateGraphToolbarUI();
    wakePhysics();
    if (typeof updateUrl === "function" && !isSyncingFromUrl) updateUrl(false);
  };

  window.setHopFilter = function(val) {
    graphFilterState.hops = val;
    graphFilterState.preset = "custom";
    updateGraphToolbarUI();
    wakePhysics();
    if (typeof updateUrl === "function" && !isSyncingFromUrl) updateUrl(false);
  };

  window.applyPerspectivePreset = function(presetKey) {
    graphFilterState.preset = presetKey;

    if (presetKey === "default") {
      graphFilterState.types = new Set(ALL_ENTITY_TYPES);
      graphFilterState.hops = "all";
      filterState.groupBy = "release";
      filterState.bc = "all";
      filterState.status = "all";
      filterState.hideDone = false;
      if (currentLayout !== "network" && typeof switchLayout === "function") switchLayout("network");
    } else if (presetKey === "bc") {
      graphFilterState.types = new Set(ALL_ENTITY_TYPES);
      graphFilterState.hops = "all";
      filterState.groupBy = "bc";
      if (currentLayout !== "network" && typeof switchLayout === "function") switchLayout("network");
    } else if (presetKey === "delivery") {
      graphFilterState.types = new Set(["task", "story", "prd"]);
      filterState.hideDone = true;
      filterState.status = "all";
      filterState.groupBy = "release";
      graphFilterState.hops = "all";
      if (currentLayout !== "network" && typeof switchLayout === "function") switchLayout("network");
    } else if (presetKey === "architecture") {
      graphFilterState.types = new Set(["prd", "adr", "bc", "story"]);
      graphFilterState.hops = "all";
      if (currentLayout !== "network" && typeof switchLayout === "function") switchLayout("network");
    } else if (presetKey === "flow") {
      graphFilterState.types = new Set(ALL_ENTITY_TYPES);
      graphFilterState.hops = "all";
      if (typeof switchLayout === "function") switchLayout("flow");
    }

    updateGraphToolbarUI();
    wakePhysics();
    if (typeof updateUrl === "function" && !isSyncingFromUrl) updateUrl(false);
  };

  window.resetAllFilters = function() {
    window.applyPerspectivePreset("default");
    searchQuery = "";
    filterState.query = "";
    const searchInput = document.getElementById("search-input");
    if (searchInput) searchInput.value = "";
    filterState.linked = null;
    updateGraphToolbarUI();
    wakePhysics();
    if (typeof updateUrl === "function" && !isSyncingFromUrl) updateUrl(false);
  };

  window.isNodeVisible = isNodeVisible;
  window.wakePhysics = wakePhysics;
  window.checkPhysicsSleep = checkPhysicsSleep;
  window.updateGraphToolbarUI = updateGraphToolbarUI;
  window.getGraphFilterState = function() { return graphFilterState; };
"""
