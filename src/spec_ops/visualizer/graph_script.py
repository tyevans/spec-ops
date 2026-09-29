"""Client-side graph layout, physics, and canvas rendering script."""

GRAPH_JS = r"""
  const data = window.PROJECT_DATA || {};
  const stats = data.health || {};

  const statMap = {
    "stat-tasks": stats.total_tasks || 0,
    "stat-stories": stats.total_stories || 0,
    "stat-prds": stats.total_prds || 0,
    "stat-adrs": stats.total_adrs || 0,
    "stat-edges": stats.total_edges || 0,
  };
  for (const [id, val] of Object.entries(statMap)) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  const canvas = document.getElementById("network-canvas");
  const ctx = canvas.getContext("2d");
  let width, height;

  let currentLayout = "network";
  let isPhysicsRunning = true;
  let panX = 0, panY = 0, zoom = 1;
  let isPanning = false, panStartX = 0, panStartY = 0;
  let draggedNode = null;
  let searchQuery = "";
  let focusedNodeId = null;
  function matchNode(n, cleanId) {
    if (!n || !n.id) return false;
    const nid = String(n.id).toUpperCase();
    if (nid === cleanId) return true;
    if (nid.replace("TASK-", "") === cleanId.replace("TASK-", "")) return true;
    if (nid.replace("ADR-", "") === cleanId.replace("ADR-", "")) return true;
    if (nid.replace("PRD-", "") === cleanId.replace("PRD-", "")) return true;
    if (nid.replace("US-", "") === cleanId.replace("US-", "")) return true;
    if (n.label && String(n.label).toUpperCase() === cleanId) return true;
    if (n.name && String(n.name).toUpperCase() === cleanId) return true;
    return false;
  }

  window.focusNode = function(nodeId, immediate = false) {
    if (!nodeId) {
      focusedNodeId = null;
      targetPanX = null;
      targetPanY = null;
      return;
    }
    const cleanId = String(nodeId).toUpperCase();
    const target = nodes.find(n => matchNode(n, cleanId));
    if (target) {
      focusedNodeId = target.id;
      const cw = width || (canvas && canvas.clientWidth) || 1000;
      const ch = height || (canvas && canvas.clientHeight) || 800;
      targetPanX = cw / 2 - target.x * zoom;
      targetPanY = ch / 2 - target.y * zoom;
      if (immediate || (typeof isSyncingFromUrl !== "undefined" && isSyncingFromUrl)) {
        panX = targetPanX;
        panY = targetPanY;
        targetPanX = null;
        targetPanY = null;
      }
    }
  };

  window.getFocusedNodeId = function() {
    return focusedNodeId;
  };

  window.getCameraState = function() {
    return { panX, panY, zoom, targetPanX, targetPanY, focusedNodeId };
  };

  function resize() {
    width = canvas.width = canvas.clientWidth;
    height = canvas.height = canvas.clientHeight;
  }
  window.addEventListener("resize", resize);
  resize();

  const rawNodes = data.nodes || [];
  const nodes = rawNodes.map((n, i) => {
    const angle = (i / Math.max(rawNodes.length, 1)) * Math.PI * 2;
    const r = 240 + (i % 3) * 60;
    let radius = 10;
    if (n.type === 'prd') radius = 16;
    else if (n.type === 'task') radius = 11;
    else if (n.type === 'bc') radius = 13;
    else if (n.type === 'persona') radius = 13;
    else if (n.type === 'adr') radius = 10;

    return {
      ...n,
      x: width / 2 + Math.cos(angle) * r,
      y: height / 2 + Math.sin(angle) * r,
      vx: 0,
      vy: 0,
      radius: radius,
    };
  });

  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const links = (data.edges || [])
    .map(e => ({
      source: nodeMap.get(e.source),
      target: nodeMap.get(e.target),
      relation: e.relation,
    }))
    .filter(l => l.source && l.target);

  function matchesSearch(node) {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (node.id && node.id.toLowerCase().includes(q)) ||
           (node.label && node.label.toLowerCase().includes(q)) ||
           (node.type && node.type.toLowerCase().includes(q)) ||
           (node.role && node.role.toLowerCase().includes(q)) ||
           (node.bc && node.bc.toLowerCase().includes(q));
  }

  let flowStages = [];

  function tick() {
    if (isPhysicsRunning && currentLayout === "network") {
      const nLen = nodes.length;
      for (let i = 0; i < nLen; i++) {
        for (let j = i + 1; j < nLen; j++) {
          const a = nodes[i], b = nodes[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          let distSq = dx * dx + dy * dy;
          if (distSq < 400000) {
            let dist = Math.sqrt(distSq) || 1;
            let rep = 1500 / (distSq + 120);
            let fx = (dx / dist) * rep;
            let fy = (dy / dist) * rep;
            a.vx -= fx; a.vy -= fy;
            b.vx += fx; b.vy += fy;
          }
        }
      }

      links.forEach(l => {
        let dx = l.target.x - l.source.x, dy = l.target.y - l.source.y;
        let dist = Math.hypot(dx, dy) || 1;
        let f = (dist - 110) * 0.016;
        let fx = (dx / dist) * f;
        let fy = (dy / dist) * f;
        l.source.vx += fx; l.source.vy += fy;
        l.target.vx -= fx; l.target.vy -= fy;
      });

      const cx = width / 2, cy = height / 2;
      nodes.forEach(n => {
        if (n === draggedNode) return;
        n.vx += (cx - n.x) * 0.0006;
        n.vy += (cy - n.y) * 0.0006;
        let speed = Math.hypot(n.vx, n.vy);
        if (speed > 8) {
          n.vx = (n.vx / speed) * 8;
          n.vy = (n.vy / speed) * 8;
        }
        n.x += n.vx; n.y += n.vy;
        n.vx *= 0.88; n.vy *= 0.88;
      });
    }

    if (targetPanX !== null && targetPanY !== null) {
      panX += (targetPanX - panX) * 0.15;
      panY += (targetPanY - panY) * 0.15;
      if (Math.hypot(targetPanX - panX, targetPanY - panY) < 1) {
        panX = targetPanX;
        panY = targetPanY;
        targetPanX = null;
        targetPanY = null;
      }
    }

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.translate(panX, panY);
    ctx.scale(zoom, zoom);

    if (currentLayout === "flow" && flowStages && flowStages.length > 0) {
      flowStages.forEach(st => {
        const midX = (st.xMin + st.xMax) / 2;
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
        ctx.font = "bold 10px ui-sans-serif, system-ui, sans-serif";
        ctx.fillText(st.title, midX, st.yMin - 12);
        ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
        ctx.font = "9px ui-monospace, monospace";
        ctx.fillText(st.count + (st.count === 1 ? " node" : " nodes"), midX, st.yMin);
      });
      ctx.textAlign = "left";
    }

    if (currentLayout === "radial") {
      const cx = width / 2, cy = height / 2;
      const rings = [160, 300, 460, 650, 840, 1020];
      ctx.setLineDash([4, 6]);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
      ctx.lineWidth = 1;
      rings.forEach(r => {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    links.forEach(l => {
      const highlighted = !searchQuery || (matchesSearch(l.source) || matchesSearch(l.target));
      ctx.strokeStyle = highlighted ? "rgba(255, 255, 255, 0.16)" : "rgba(255, 255, 255, 0.03)";
      ctx.lineWidth = highlighted ? 1.2 : 0.6;
      ctx.beginPath();
      ctx.moveTo(l.source.x, l.source.y);
      ctx.lineTo(l.target.x, l.target.y);
      ctx.stroke();
    });

    nodes.forEach(n => {
      const match = matchesSearch(n);
      ctx.globalAlpha = (!searchQuery || match) ? 1.0 : 0.15;
      ctx.fillStyle = n.color || "#8b5cf6";
      ctx.shadowColor = (match && searchQuery) ? "#38bdf8" : (n.color || "#8b5cf6");
      ctx.shadowBlur = (match && searchQuery) ? 16 : 6;

      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      if (focusedNodeId && matchNode(n, String(focusedNodeId).toUpperCase())) {
        const now = (typeof Date !== "undefined" && Date.now) ? Date.now() : 0;
        const pulse = Math.sin(now / 220) * 3.5;
        ctx.save();
        ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
        ctx.lineWidth = 2.5;
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 16;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 8 + pulse, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = "rgba(186, 230, 253, 0.95)";
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 3.5, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      ctx.fillStyle = "#e5e7eb";
      ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.fillText(n.id, n.x + n.radius + 4, n.y + 3);
      ctx.globalAlpha = 1.0;
    });

    ctx.restore();
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  function screenToWorld(sx, sy) {
    return { x: (sx - panX) / zoom, y: (sy - panY) / zoom };
  }

  canvas.addEventListener("mousedown", e => {
    targetPanX = null;
    targetPanY = null;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const { x, y } = screenToWorld(sx, sy);

    const clicked = nodes.find(n => Math.hypot(n.x - x, n.y - y) <= n.radius + 6);
    if (clicked) {
      draggedNode = clicked;
    } else {
      isPanning = true;
      panStartX = e.clientX - panX;
      panStartY = e.clientY - panY;
    }
  });

  window.addEventListener("mousemove", e => {
    if (draggedNode) {
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
      const { x, y } = screenToWorld(sx, sy);
      draggedNode.x = x; draggedNode.y = y;
      draggedNode.vx = 0; draggedNode.vy = 0;
    } else if (isPanning) {
      panX = e.clientX - panStartX;
      panY = e.clientY - panStartY;
    }
  });

  window.addEventListener("mouseup", () => {
    isPanning = false;
    draggedNode = null;
  });

  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    const newZoom = Math.max(0.15, Math.min(4.5, zoom * factor));
    panX = sx - (sx - panX) * (newZoom / zoom);
    panY = sy - (sy - panY) * (newZoom / zoom);
    zoom = newZoom;
  }, { passive: false });

  window.zoomIn = () => { zoom = Math.min(4.5, zoom * 1.25); };
  window.zoomOut = () => { zoom = Math.max(0.15, zoom / 1.25); };
  window.resetZoom = () => { panX = 0; panY = 0; zoom = 1; };

  document.getElementById("search-input").addEventListener("input", e => {
    searchQuery = e.target.value.trim();
    if (typeof filterState !== "undefined") {
      filterState.query = searchQuery;
    }
    if (typeof updateUrl === "function" && !isSyncingFromUrl) {
      updateUrl(false);
    }
  });
"""
