"""Client-side graph layout algorithms (Flow DAG, Radial Radar, Force Network)."""

LAYOUTS_JS = r"""
  function fitFlowView() {
    if (!nodes || nodes.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.forEach(n => {
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    });
    minX -= 30; maxX += 90; minY -= 50; maxY += 40;
    const graphW = Math.max(100, maxX - minX);
    const graphH = Math.max(100, maxY - minY);
    const fitZoom = Math.min(1.0, Math.min((width - 60) / graphW, (height - 80) / graphH));
    zoom = Math.max(0.2, fitZoom);
    panX = width / 2 - ((minX + maxX) / 2) * zoom;
    panY = height / 2 - ((minY + maxY) / 2) * zoom;
  }

  function computeFlowLayout() {
    const colOrder = ["persona", "story", "prd", "task", "adr", "bc"];
    const stageTitles = {
      persona: "PERSONAS",
      story: "STORIES",
      prd: "PRDS",
      task: "TASKS",
      adr: "ADRS",
      bc: "BOUNDED CONTEXTS"
    };

    const buckets = {};
    colOrder.forEach(t => { buckets[t] = []; });
    nodes.forEach(n => {
      const b = buckets[n.type] || buckets["task"];
      b.push(n);
    });

    const nodePrdMap = {};
    links.forEach(l => {
      const s = l.source, t = l.target;
      if (s && t) {
        if (s.type === "story" && t.type === "prd") nodePrdMap[s.id] = t.id;
        else if (t.type === "story" && s.type === "prd") nodePrdMap[t.id] = s.id;
        else if (s.type === "task" && t.type === "prd" && !nodePrdMap[s.id]) nodePrdMap[s.id] = t.id;
        else if (t.type === "task" && s.type === "prd" && !nodePrdMap[t.id]) nodePrdMap[t.id] = s.id;
      }
    });

    buckets["persona"].sort((a, b) => a.id.localeCompare(b.id));
    buckets["story"].sort((a, b) => {
      const prdA = nodePrdMap[a.id] || "ZZZ", prdB = nodePrdMap[b.id] || "ZZZ";
      return prdA.localeCompare(prdB) || a.id.localeCompare(b.id);
    });
    buckets["prd"].sort((a, b) => a.id.localeCompare(b.id));
    buckets["task"].sort((a, b) => {
      const prdA = nodePrdMap[a.id] || "ZZZ", prdB = nodePrdMap[b.id] || "ZZZ";
      return prdA.localeCompare(prdB) || a.id.localeCompare(b.id);
    });
    buckets["adr"].sort((a, b) => a.id.localeCompare(b.id));
    buckets["bc"].sort((a, b) => a.id.localeCompare(b.id));

    const usableH = Math.max(height - 180, 600);
    const rowSpacing = 36;
    const targetMaxRows = Math.max(14, Math.min(22, Math.floor(usableH / rowSpacing)));

    const stageConfig = {};
    let totalCols = 0;
    colOrder.forEach(t => {
      const count = buckets[t].length;
      const numCols = count === 0 ? 0 : Math.max(1, Math.ceil(count / targetMaxRows));
      stageConfig[t] = { count, numCols };
      totalCols += numCols;
    });

    const subColWidth = 115, stageGap = 70;
    const activeStages = colOrder.filter(t => stageConfig[t].count > 0);
    const totalW = totalCols * subColWidth + Math.max(0, activeStages.length - 1) * stageGap;
    let currX = Math.max(80, (width - totalW) / 2);
    const startY = 110;

    let maxStageRows = 1;
    activeStages.forEach(t => {
      maxStageRows = Math.max(maxStageRows, Math.ceil(stageConfig[t].count / stageConfig[t].numCols));
    });
    const layoutH = maxStageRows * rowSpacing;

    flowStages = [];

    colOrder.forEach(type => {
      const arr = buckets[type];
      const { count, numCols } = stageConfig[type];
      if (count === 0) return;

      const stageW = numCols * subColWidth;
      const stageRows = Math.ceil(count / numCols);
      const stageH = stageRows * rowSpacing;
      const offsetY = startY + (layoutH - stageH) / 2;

      flowStages.push({
        type: type,
        title: stageTitles[type] || type.toUpperCase(),
        count: count,
        xMin: currX,
        xMax: currX + stageW - 20,
        yMin: startY - 20,
        yMax: startY + layoutH + 20,
      });

      if (type === "prd") {
        const prdAvgY = {};
        arr.forEach(p => {
          const linkedStories = [];
          links.forEach(l => {
            if (l.source === p && l.target.type === "story") linkedStories.push(l.target);
            else if (l.target === p && l.source.type === "story") linkedStories.push(l.source);
          });
          if (linkedStories.length > 0) {
            prdAvgY[p.id] = linkedStories.reduce((sum, s) => sum + s.y, 0) / linkedStories.length;
          }
        });
        let lastY = -Infinity;
        arr.forEach((n, i) => {
          const targetY = prdAvgY[n.id] !== undefined ? prdAvgY[n.id] : (offsetY + (i + 0.5) * (stageH / arr.length));
          const safeY = Math.max(targetY, lastY + 44);
          n.x = currX + 20; n.y = safeY; n.vx = 0; n.vy = 0;
          lastY = safeY;
        });
      } else if (numCols === 1 && arr.length > 1) {
        const step = (layoutH - rowSpacing) / (arr.length - 1);
        arr.forEach((n, i) => {
          n.x = currX + 20;
          n.y = startY + rowSpacing / 2 + i * step;
          n.vx = 0; n.vy = 0;
        });
      } else {
        arr.forEach((n, i) => {
          const colIdx = numCols > 1 ? (i % numCols) : 0;
          const rowIdx = numCols > 1 ? Math.floor(i / numCols) : i;
          n.x = currX + colIdx * subColWidth + 20;
          n.y = offsetY + (rowIdx + 0.5) * rowSpacing;
          n.vx = 0; n.vy = 0;
        });
      }

      currX += stageW + stageGap;
    });
  }

  function computeRadialLayout() {
    const rings = { persona: 160, prd: 300, story: 460, task: 650, adr: 840, bc: 1020 };
    const buckets = {};
    Object.keys(rings).forEach(t => { buckets[t] = []; });
    nodes.forEach(n => {
      const b = buckets[n.type] || buckets["task"];
      b.push(n);
    });

    const cx = width / 2, cy = height / 2;
    Object.keys(rings).forEach(type => {
      const arr = buckets[type];
      const r = rings[type];
      arr.forEach((n, i) => {
        const angle = (i / Math.max(arr.length, 1)) * 2 * Math.PI - Math.PI / 2;
        n.x = cx + Math.cos(angle) * r;
        n.y = cy + Math.sin(angle) * r;
        n.vx = 0; n.vy = 0;
      });
    });
  }

  window.switchLayout = function(layout) {
    currentLayout = layout;
    ["network", "flow", "radial"].forEach(l => {
      const btn = document.getElementById("btn-layout-" + l);
      if (btn) {
        if (l === layout) btn.classList.add("active");
        else btn.classList.remove("active");
      }
    });

    if (layout === "flow") {
      isPhysicsRunning = false;
      computeFlowLayout();
      fitFlowView();
    } else if (layout === "radial") {
      isPhysicsRunning = false;
      computeRadialLayout();
    } else {
      isPhysicsRunning = true;
      nodes.forEach(n => {
        n.vx += (Math.random() - 0.5) * 6;
        n.vy += (Math.random() - 0.5) * 6;
      });
    }
    updatePhysicsBtn();
  };

  window.togglePhysics = function() {
    isPhysicsRunning = !isPhysicsRunning;
    updatePhysicsBtn();
  };

  function updatePhysicsBtn() {
    const btn = document.getElementById("btn-physics-toggle");
    if (btn) btn.textContent = isPhysicsRunning ? "⏸️ Freeze" : "▶️ Run";
  }

  window.shufflePhysics = function() {
    isPhysicsRunning = true;
    updatePhysicsBtn();
    nodes.forEach(n => {
      n.vx += (Math.random() - 0.5) * 14;
      n.vy += (Math.random() - 0.5) * 14;
    });
  };

  window.resetZoom = () => {
    if (currentLayout === "flow") {
      fitFlowView();
    } else {
      panX = 0; panY = 0; zoom = 1;
    }
  };

  window.addEventListener("resize", () => {
    if (currentLayout === "flow") {
      computeFlowLayout();
      fitFlowView();
    } else if (currentLayout === "radial") {
      computeRadialLayout();
    }
  });
"""
