"""HTML, CSS, and Canvas JavaScript template for the SpecOps visualizer."""

VISUALIZER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SpecOps Visualizer</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(19, 26, 42, 0.9);
      --border: rgba(255, 255, 255, 0.12);
      --text: #f3f4f6;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 10px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 10;
      gap: 16px;
    }}
    .header-left {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .nav-back-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      text-decoration: none;
      font-size: 0.82rem;
      font-weight: 600;
      transition: all 0.15s;
    }}
    .nav-back-btn:hover {{
      background: rgba(59, 130, 246, 0.2);
      border-color: var(--primary);
      color: #fff;
    }}
    header h1 {{ font-size: 1.05rem; display: flex; align-items: center; gap: 8px; white-space: nowrap; }}
    .badge {{ font-size: 0.72rem; padding: 2px 8px; border-radius: 9999px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; }}
    .search-box {{
      flex: 1;
      max-width: 320px;
      position: relative;
    }}
    .search-box input {{
      width: 100%;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 12px;
      color: #fff;
      font-size: 0.85rem;
      outline: none;
    }}
    .search-box input:focus {{ border-color: var(--primary); }}
    .stats-bar {{ display: flex; gap: 14px; font-size: 0.82rem; color: var(--text-muted); align-items: center; white-space: nowrap; }}
    .stats-bar span b {{ color: var(--text); }}
    main {{ flex: 1; display: flex; position: relative; overflow: hidden; }}
    #network-canvas {{ flex: 1; width: 100%; height: 100%; background: radial-gradient(circle at center, #111827 0%, #030712 100%); cursor: grab; }}
    #network-canvas:active {{ cursor: grabbing; }}
    .legend {{
      position: absolute;
      top: 16px;
      left: 16px;
      background: var(--card-bg);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 0.75rem;
      z-index: 5;
      display: flex;
      flex-direction: column;
      gap: 6px;
      pointer-events: none;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; color: var(--text-muted); }}
    .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    .hint-bar {{
      position: absolute;
      bottom: 16px;
      left: 16px;
      background: rgba(15, 23, 42, 0.75);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 0.75rem;
      color: var(--text-muted);
      pointer-events: none;
    }}
    .zoom-controls {{
      position: absolute;
      bottom: 16px;
      right: 16px;
      display: flex;
      gap: 6px;
      z-index: 5;
    }}
    .zoom-btn {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
      width: 32px;
      height: 32px;
      border-radius: 6px;
      font-size: 1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .zoom-btn:hover {{ background: rgba(255, 255, 255, 0.15); }}
    #drawer {{
      position: absolute; right: 0; top: 0; bottom: 0; width: 440px;
      background: var(--card-bg); backdrop-filter: blur(16px);
      border-left: 1px solid var(--border); transform: translateX(100%);
      transition: transform 0.25s ease-out; display: flex; flex-direction: column; z-index: 20;
    }}
    #drawer.open {{ transform: translateX(0); }}
    .drawer-header {{ padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
    .drawer-body {{ padding: 20px; overflow-y: auto; flex: 1; font-size: 0.88rem; line-height: 1.6; white-space: pre-wrap; }}
    .close-btn {{ cursor: pointer; background: transparent; border: none; color: var(--text-muted); font-size: 1.2rem; }}
  </style>
</head>
<body>
  <header>
    <div class="header-left">
      <a href="../index.html" class="nav-back-btn">← Back to Docs</a>
      <h1>⚡ {title} <span class="badge">Visualizer</span></h1>
    </div>
    <div class="search-box">
      <input type="text" id="search-input" placeholder="Search entities (e.g. TASK, Alex, PRD)...">
    </div>
    <div class="stats-bar" id="stats">
      <span>Tasks: <b id="stat-tasks">0</b></span>
      <span>Stories: <b id="stat-stories">0</b></span>
      <span>PRDs: <b id="stat-prds">0</b></span>
      <span>ADRs: <b id="stat-adrs">0</b></span>
      <span>Edges: <b id="stat-edges">0</b></span>
    </div>
  </header>
  <main>
    <div class="legend">
      <div class="legend-item"><span class="legend-dot" style="background:#F59E0B"></span> Persona</div>
      <div class="legend-item"><span class="legend-dot" style="background:#06B6D4"></span> Story</div>
      <div class="legend-item"><span class="legend-dot" style="background:#F43F5E"></span> PRD</div>
      <div class="legend-item"><span class="legend-dot" style="background:#10B981"></span> Complete Task</div>
      <div class="legend-item"><span class="legend-dot" style="background:#F59E0B"></span> Refined Task</div>
      <div class="legend-item"><span class="legend-dot" style="background:#8B5CF6"></span> Proposed Task</div>
      <div class="legend-item"><span class="legend-dot" style="background:#6366F1"></span> ADR</div>
      <div class="legend-item"><span class="legend-dot" style="background:#EC4899"></span> Bounded Context</div>
    </div>
    <div class="hint-bar">
      Scroll to Zoom · Drag canvas to Pan · Drag nodes to move · Click to inspect
    </div>
    <div class="zoom-controls">
      <button class="zoom-btn" onclick="zoomIn()">+</button>
      <button class="zoom-btn" onclick="zoomOut()">−</button>
      <button class="zoom-btn" onclick="resetZoom()" title="Reset">⟲</button>
    </div>
    <canvas id="network-canvas"></canvas>
    <div id="drawer">
      <div class="drawer-header">
        <h3 id="drawer-title">Entity Details</h3>
        <button class="close-btn" onclick="closeDrawer()">&times;</button>
      </div>
      <div class="drawer-body" id="drawer-content"></div>
    </div>
  </main>
  <script>
    window.PROJECT_DATA = {data_json};

    const stats = window.PROJECT_DATA.health || {{}};
    document.getElementById("stat-tasks").textContent = stats.total_tasks || 0;
    document.getElementById("stat-stories").textContent = stats.total_stories || 0;
    document.getElementById("stat-prds").textContent = stats.total_prds || 0;
    document.getElementById("stat-adrs").textContent = stats.total_adrs || 0;
    document.getElementById("stat-edges").textContent = stats.total_edges || 0;

    const canvas = document.getElementById("network-canvas");
    const ctx = canvas.getContext("2d");
    let width, height;

    let panX = 0, panY = 0, zoom = 1;
    let isPanning = false, panStartX = 0, panStartY = 0;
    let draggedNode = null;
    let searchQuery = "";

    function resize() {{
      width = canvas.width = canvas.clientWidth;
      height = canvas.height = canvas.clientHeight;
    }}
    window.addEventListener("resize", resize);
    resize();

    const nodes = window.PROJECT_DATA.nodes.map((n, i) => {{
      const angle = (i / window.PROJECT_DATA.nodes.length) * Math.PI * 2;
      const r = 260 + (i % 3) * 60;
      return {{
        ...n,
        x: width/2 + Math.cos(angle) * r,
        y: height/2 + Math.sin(angle) * r,
        vx: 0, vy: 0,
        radius: n.type === 'prd' ? 16 : (n.type === 'task' ? 11 : (n.type === 'bc' ? 12 : 9))
      }};
    }});

    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const links = window.PROJECT_DATA.edges
      .map(e => ({{ source: nodeMap.get(e.source), target: nodeMap.get(e.target), relation: e.relation }}))
      .filter(l => l.source && l.target);

    function matchesSearch(node) {{
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (node.id && node.id.toLowerCase().includes(q)) ||
             (node.label && node.label.toLowerCase().includes(q)) ||
             (node.type && node.type.toLowerCase().includes(q)) ||
             (node.role && node.role.toLowerCase().includes(q));
    }}

    function tick() {{
      for (let i = 0; i < nodes.length; i++) {{
        for (let j = i + 1; j < nodes.length; j++) {{
          const a = nodes[i], b = nodes[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          let dist = Math.hypot(dx, dy) || 1;
          if (dist < 180) {{
            let rep = 1200 / (dist * dist + 80);
            let fx = (dx / dist) * rep;
            let fy = (dy / dist) * rep;
            a.vx -= fx; a.vy -= fy;
            b.vx += fx; b.vy += fy;
          }}
        }}
      }}

      links.forEach(l => {{
        let dx = l.target.x - l.source.x, dy = l.target.y - l.source.y;
        let dist = Math.hypot(dx, dy) || 1;
        let f = (dist - 110) * 0.015;
        let fx = (dx / dist) * f;
        let fy = (dy / dist) * f;
        l.source.vx += fx; l.source.vy += fy;
        l.target.vx -= fx; l.target.vy -= fy;
      }});

      nodes.forEach(n => {{
        if (n === draggedNode) return;
        n.vx += (width/2 - n.x) * 0.0006;
        n.vy += (height/2 - n.y) * 0.0006;
        let speed = Math.hypot(n.vx, n.vy);
        if (speed > 8) {{
          n.vx = (n.vx / speed) * 8;
          n.vy = (n.vy / speed) * 8;
        }}
        n.x += n.vx; n.y += n.vy;
        n.vx *= 0.88; n.vy *= 0.88;
      }});

      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(panX, panY);
      ctx.scale(zoom, zoom);

      links.forEach(l => {{
        const isHighlighted = !searchQuery || (matchesSearch(l.source) || matchesSearch(l.target));
        ctx.strokeStyle = isHighlighted ? "rgba(255, 255, 255, 0.16)" : "rgba(255, 255, 255, 0.03)";
        ctx.lineWidth = isHighlighted ? 1.2 : 0.6;
        ctx.beginPath();
        ctx.moveTo(l.source.x, l.source.y);
        ctx.lineTo(l.target.x, l.target.y);
        ctx.stroke();
      }});

      nodes.forEach(n => {{
        const match = matchesSearch(n);
        const alpha = (!searchQuery || match) ? 1.0 : 0.15;
        ctx.globalAlpha = alpha;

        ctx.fillStyle = n.color || "#8b5cf6";
        if (match && searchQuery) {{
          ctx.shadowColor = "#38bdf8";
          ctx.shadowBlur = 16;
        }} else {{
          ctx.shadowColor = n.color || "#8b5cf6";
          ctx.shadowBlur = 6;
        }}

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = "#e5e7eb";
        ctx.font = "10px monospace";
        ctx.fillText(n.id, n.x + n.radius + 4, n.y + 3);
        ctx.globalAlpha = 1.0;
      }});

      ctx.restore();
      requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);

    function screenToWorld(sx, sy) {{
      return {{
        x: (sx - panX) / zoom,
        y: (sy - panY) / zoom
      }};
    }}

    canvas.addEventListener("mousedown", e => {{
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
      const {{ x, y }} = screenToWorld(sx, sy);

      const clicked = nodes.find(n => Math.hypot(n.x - x, n.y - y) <= n.radius + 6);
      if (clicked) {{
        draggedNode = clicked;
      }} else {{
        isPanning = true;
        panStartX = e.clientX - panX;
        panStartY = e.clientY - panY;
      }}
    }});

    window.addEventListener("mousemove", e => {{
      if (draggedNode) {{
        const rect = canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
        const {{ x, y }} = screenToWorld(sx, sy);
        draggedNode.x = x;
        draggedNode.y = y;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
      }} else if (isPanning) {{
        panX = e.clientX - panStartX;
        panY = e.clientY - panStartY;
      }}
    }});

    window.addEventListener("mouseup", () => {{
      isPanning = false;
      draggedNode = null;
    }});

    canvas.addEventListener("wheel", e => {{
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.15 : 0.87;
      const newZoom = Math.max(0.2, Math.min(4.0, zoom * factor));
      panX = sx - (sx - panX) * (newZoom / zoom);
      panY = sy - (sy - panY) * (newZoom / zoom);
      zoom = newZoom;
    }}, {{ passive: false }});

    function zoomIn() {{ zoom = Math.min(4.0, zoom * 1.25); }}
    function zoomOut() {{ zoom = Math.max(0.2, zoom / 1.25); }}
    function resetZoom() {{ panX = 0; panY = 0; zoom = 1; }}

    document.getElementById("search-input").addEventListener("input", e => {{
      searchQuery = e.target.value.trim();
    }});

    function openDrawer(node) {{
      document.getElementById("drawer-title").textContent = node.id + ": " + node.label;
      let content = "🏷️ Type: " + node.type.toUpperCase() + "\\n";
      if (node.status) content += "📌 Status: " + node.status + "\\n";
      if (node.role) content += "👤 Role: " + node.role + "\\n";
      if (node.bc) content += "📦 Bounded Context: " + node.bc + "\\n";

      const t = (window.PROJECT_DATA.tasks || []).find(x => x.id === node.id);
      if (t) {{
        if (t.dependencies && t.dependencies.length) content += "🔗 Dependencies: " + t.dependencies.join(", ") + "\\n";
        if (t.governing_adrs && t.governing_adrs.length) content += "⚖️ Governing ADRs: " + t.governing_adrs.join(", ") + "\\n";
        if (t.governing_stories && t.governing_stories.length) content += "📖 Stories: " + t.governing_stories.join(", ") + "\\n";
        if (t.prs && t.prs.length) content += "🔀 PRs: " + t.prs.join(", ") + "\\n";
        content += "\\n---\\n\\n" + (t.body || "");
      }}
      const s = (window.PROJECT_DATA.stories || []).find(x => x.id === node.id);
      if (s) {{
        if (s.persona) content += "👤 Persona: " + s.persona + "\\n";
        if (s.governing_prd) content += "🎯 PRD: " + s.governing_prd + "\\n";
      }}
      const p = (window.PROJECT_DATA.prds || []).find(x => x.id === node.id);
      if (p) {{
        if (p.tasks && p.tasks.length) content += "🔨 Tasks: " + p.tasks.join(", ") + "\\n";
      }}
      document.getElementById("drawer-content").textContent = content;
      document.getElementById("drawer").classList.add("open");
    }}

    function closeDrawer() {{
      document.getElementById("drawer").classList.remove("open");
    }}

    canvas.addEventListener("click", e => {{
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
      const {{ x, y }} = screenToWorld(sx, sy);
      const clicked = nodes.find(n => Math.hypot(n.x - x, n.y - y) <= n.radius + 6);
      if (clicked) openDrawer(clicked);
    }});
  </script>
</body>
</html>
"""
