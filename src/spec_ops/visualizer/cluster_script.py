"""Client-side Bounded Context clustering, centroid force attraction, and boundary hull rendering."""
from __future__ import annotations

CLUSTER_JS = r"""
  const bcColorPalette = [
    "#ec4899", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b",
    "#3b82f6", "#a855f7", "#14b8a6", "#f43f5e", "#6366f1"
  ];

  const bcColorMap = {};
  function getBcColor(bcName) {
    if (!bcName) return "#64748b";
    if (!bcColorMap[bcName]) {
      const idx = Object.keys(bcColorMap).length % bcColorPalette.length;
      bcColorMap[bcName] = bcColorPalette[idx];
    }
    return bcColorMap[bcName];
  }

  function resolveNodeBc(node) {
    if (node.bc) return node.bc;
    if (node.type === "bc") return node.id;
    if (node.target_bc) return node.target_bc;

    // Check linked edges
    const connectedLinks = (links || []).filter(l => l.source === node || l.target === node);
    for (const l of connectedLinks) {
      const neighbor = l.source === node ? l.target : l.source;
      if (neighbor && neighbor.bc) return neighbor.bc;
    }
    return null;
  }

  // Pre-resolve BC on all nodes
  nodes.forEach(n => {
    n.resolvedBc = resolveNodeBc(n);
  });

  let bcCentroids = {};

  function computeBcCentroids() {
    let bcs = Array.from(new Set(nodes.map(n => n.resolvedBc || n.bc).filter(Boolean))).sort();
    if (bcs.length === 0 && data.bounded_contexts) {
      bcs = data.bounded_contexts.map(b => b.id || b.name).filter(Boolean);
    }
    if (bcs.length === 0) return {};

    const cx = (width || 1000) / 2;
    const cy = (height || 800) / 2;
    const radius = Math.min(width || 1000, height || 800) * 0.36;

    const centroids = {};
    bcs.forEach((bc, idx) => {
      const angle = (idx / bcs.length) * Math.PI * 2 - Math.PI / 2;
      centroids[bc] = {
        name: bc,
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        color: getBcColor(bc),
      };
    });
    return centroids;
  }

  bcCentroids = computeBcCentroids();

  function applyBcClusteringForces() {
    if (filterState.groupBy !== "bc" || currentLayout !== "network") return;
    if (!bcCentroids || Object.keys(bcCentroids).length === 0) {
      bcCentroids = computeBcCentroids();
    }

    nodes.forEach(n => {
      if (n === draggedNode) return;
      const bc = n.resolvedBc;
      if (bc && bcCentroids[bc]) {
        const c = bcCentroids[bc];
        n.vx += (c.x - n.x) * 0.0032;
        n.vy += (c.y - n.y) * 0.0032;
      }
    });
  }

  function hexToRgba(hex, alpha) {
    let clean = hex.replace("#", "");
    if (clean.length === 3) {
      clean = clean.split("").map(c => c + c).join("");
    }
    const num = parseInt(clean, 16);
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function drawBcHulls(ctx) {
    const shouldDrawHulls = (filterState.groupBy === "bc") || (currentLayout === "radial" || currentLayout === "flow") || (typeof activeTab !== "undefined" && (activeTab === "adrs" || activeTab === "radar"));
    if (!shouldDrawHulls) return;

    const bcGroups = {};
    nodes.forEach(n => {
      const bc = n.resolvedBc;
      if (!bc) return;
      if (typeof isNodeVisible === "function" && !isNodeVisible(n)) return;
      if (!bcGroups[bc]) bcGroups[bc] = [];
      bcGroups[bc].push(n);
    });

    Object.entries(bcGroups).forEach(([bc, members]) => {
      if (members.length === 0) return;

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      members.forEach(m => {
        if (m.x < minX) minX = m.x;
        if (m.x > maxX) maxX = m.x;
        if (m.y < minY) minY = m.y;
        if (m.y > maxY) maxY = m.y;
      });

      const pad = 34;
      const x = minX - pad;
      const y = minY - pad;
      const w = Math.max(90, (maxX - minX) + pad * 2);
      const h = Math.max(70, (maxY - minY) + pad * 2);
      const color = getBcColor(bc);

      ctx.save();
      // Draw background bounding hull
      ctx.fillStyle = hexToRgba(color, 0.045);
      ctx.strokeStyle = hexToRgba(color, 0.32);
      ctx.lineWidth = 1.4;
      ctx.setLineDash([5, 5]);

      if (typeof ctx.roundRect === "function") {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 14);
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        ctx.fill();
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // Draw BC Header Badge
      const labelText = `BOUNDED CONTEXT: ${bc.toUpperCase()} (${members.length})`;
      ctx.font = "bold 9.5px ui-monospace, SFMono-Regular, Menlo, monospace";
      const textWidth = ctx.measureText ? ctx.measureText(labelText).width : 130;
      const badgeW = textWidth + 16;
      const badgeH = 18;
      const badgeX = x + 10;
      const badgeY = y - 9;

      ctx.fillStyle = "rgba(11, 15, 25, 0.92)";
      ctx.strokeStyle = hexToRgba(color, 0.6);
      ctx.lineWidth = 1;
      if (typeof ctx.roundRect === "function") {
        ctx.beginPath();
        ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 4);
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.fillRect(badgeX, badgeY, badgeW, badgeH);
        ctx.strokeRect(badgeX, badgeY, badgeW, badgeH);
      }

      ctx.fillStyle = color;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(labelText, badgeX + 8, badgeY + badgeH / 2);

      ctx.restore();
    });
  }

  window.toggleBcClustering = function() {
    const nextGroup = filterState.groupBy === "bc" ? "release" : "bc";
    window.setFilter("groupBy", nextGroup);
    if (typeof wakePhysics === "function") wakePhysics();
  };

  window.getBcCentroids = function() {
    if (!bcCentroids || Object.keys(bcCentroids).length === 0) {
      bcCentroids = computeBcCentroids();
    }
    return bcCentroids;
  };

  window.drawBcHulls = drawBcHulls;
  window.getBcColor = getBcColor;
"""
