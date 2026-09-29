"""Standalone single-file HTML bundle generator for the SpecOps visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester
from ..core.graph import build_graph_data, process_project_graph
from ..core.parser import SpecOpsParser


def serialize_project_data(config: SpecOpsConfig) -> dict[str, Any]:
    parser = SpecOpsParser(config.project_docs_dir)
    data = parser.parse_all()
    process_project_graph(data, target_buffer=config.architecture.buffer_target)

    # Harvest git commits
    harvester = GitMetadataHarvester(config.root_dir)
    git_map = harvester.harvest()

    for task in data.tasks:
        if task.canonical_id in git_map:
            commits, prs = git_map[task.canonical_id]
            task.prs = list(dict.fromkeys(task.prs + prs))

    graph = build_graph_data(data)

    return {
        "project": {
            "name": config.project.name,
            "repo": config.project.repo,
        },
        "health": data.health_metrics,
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "type": n.type,
                "color": n.color,
                "status": n.status,
                "role": n.role,
                "domain": n.domain,
                "bc": n.bc,
                "prs": n.prs,
                "metadata": n.metadata,
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "source": e.source,
                "target": e.target,
                "relation": e.relation,
                "source_type": e.source_type,
                "target_type": e.target_type,
            }
            for e in graph.edges
        ],
        "tasks": [
            {
                "id": t.canonical_id,
                "title": t.title,
                "status": t.status,
                "dependencies": t.dependencies,
                "governing_adrs": t.governing_adrs,
                "governing_prds": t.governing_prds,
                "governing_stories": t.governing_stories,
                "target_bc": t.target_bc,
                "target_release": t.target_release,
                "prs": t.prs,
                "pr_url": t.pr_url,
                "priority_rank": t.priority_rank,
                "body": t.body,
            }
            for t in data.tasks
        ],
        "personas": [
            {"id": p.id, "name": p.name, "role": p.role, "story_ids": p.story_ids}
            for p in data.personas
        ],
        "stories": [
            {"id": s.id, "title": s.title, "persona": s.persona, "governing_prd": s.governing_prd}
            for s in data.stories
        ],
        "prds": [
            {"id": p.id, "title": p.title, "status": p.status, "tasks": p.implementing_tasks}
            for p in data.prds
        ],
        "adrs": [
            {"id": a.id, "title": a.title, "domain": a.domain}
            for a in data.adrs
        ],
    }


def generate_standalone_html(config: SpecOpsConfig) -> str:
    data_json = json.dumps(serialize_project_data(config))
    title = config.project.name

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SpecOps Visualizer</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(22, 30, 46, 0.85);
      --border: rgba(255, 255, 255, 0.1);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --accent-indigo: #6366f1;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 10;
    }}
    header h1 {{ font-size: 1.1rem; display: flex; align-items: center; gap: 8px; }}
    .badge {{ font-size: 0.75rem; padding: 2px 8px; border-radius: 9999px; background: rgba(6,182,212,0.15); color: var(--accent-cyan); }}
    .stats-bar {{ display: flex; gap: 16px; font-size: 0.85rem; color: var(--text-muted); }}
    .stats-bar span b {{ color: var(--text); }}
    main {{ flex: 1; display: flex; position: relative; overflow: hidden; }}
    #network-canvas {{ flex: 1; width: 100%; height: 100%; background: radial-gradient(circle at center, #111827 0%, #030712 100%); cursor: grab; }}
    #drawer {{
      position: absolute; right: 0; top: 0; bottom: 0; width: 440px;
      background: var(--card-bg); backdrop-filter: blur(16px);
      border-left: 1px solid var(--border); transform: translateX(100%);
      transition: transform 0.25s ease-out; display: flex; flex-direction: column; z-index: 20;
    }}
    #drawer.open {{ transform: translateX(0); }}
    .drawer-header {{ padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
    .drawer-body {{ padding: 20px; overflow-y: auto; flex: 1; font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap; }}
    .close-btn {{ cursor: pointer; background: transparent; border: none; color: var(--text-muted); font-size: 1.2rem; }}
  </style>
</head>
<body>
  <header>
    <h1>⚡ {title} <span class="badge">SpecOps</span></h1>
    <div class="stats-bar" id="stats">
      <span>Tasks: <b id="stat-tasks">0</b></span>
      <span>Stories: <b id="stat-stories">0</b></span>
      <span>PRDs: <b id="stat-prds">0</b></span>
      <span>ADRs: <b id="stat-adrs">0</b></span>
      <span>Edges: <b id="stat-edges">0</b></span>
    </div>
  </header>
  <main>
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
    function resize() {{
      width = canvas.width = canvas.clientWidth;
      height = canvas.height = canvas.clientHeight;
    }}
    window.addEventListener("resize", resize);
    resize();

    const nodes = window.PROJECT_DATA.nodes.map((n, i) => ({{
      ...n,
      x: width/2 + (Math.random() - 0.5) * width * 0.7,
      y: height/2 + (Math.random() - 0.5) * height * 0.7,
      vx: 0, vy: 0,
      radius: n.type === 'prd' ? 14 : (n.type === 'task' ? 10 : 8)
    }}));

    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const links = window.PROJECT_DATA.edges
      .map(e => ({{ source: nodeMap.get(e.source), target: nodeMap.get(e.target), relation: e.relation }}))
      .filter(l => l.source && l.target);

    function tick() {{
      // Simple force simulation
      for (let i = 0; i < nodes.length; i++) {{
        for (let j = i + 1; j < nodes.length; j++) {{
          const a = nodes[i], b = nodes[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          let dist = Math.hypot(dx, dy) || 1;
          if (dist < 120) {{
            let f = (120 - dist) / dist * 0.05;
            a.vx -= dx * f; a.vy -= dy * f;
            b.vx += dx * f; b.vy += dy * f;
          }}
        }}
      }}
      links.forEach(l => {{
        let dx = l.target.x - l.source.x, dy = l.target.y - l.source.y;
        let dist = Math.hypot(dx, dy) || 1;
        let f = (dist - 80) * 0.005;
        l.source.vx += dx * f; l.source.vy += dy * f;
        l.target.vx -= dx * f; l.target.vy -= dy * f;
      }});
      nodes.forEach(n => {{
        n.vx += (width/2 - n.x) * 0.0005;
        n.vy += (height/2 - n.y) * 0.0005;
        n.x += n.vx; n.y += n.vy;
        n.vx *= 0.88; n.vy *= 0.88;
      }});

      ctx.clearRect(0, 0, width, height);

      // Draw links
      ctx.lineWidth = 1;
      links.forEach(l => {{
        ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
        ctx.beginPath();
        ctx.moveTo(l.source.x, l.source.y);
        ctx.lineTo(l.target.x, l.target.y);
        ctx.stroke();
      }});

      // Draw nodes
      nodes.forEach(n => {{
        ctx.fillStyle = n.color || "#8b5cf6";
        ctx.shadowColor = n.color || "#8b5cf6";
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = "#e5e7eb";
        ctx.font = "10px monospace";
        ctx.fillText(n.id, n.x + n.radius + 4, n.y + 3);
      }});

      requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);

    function openDrawer(node) {{
      document.getElementById("drawer-title").textContent = node.id + ": " + node.label;
      const t = window.PROJECT_DATA.tasks.find(x => x.id === node.id);
      let content = "Type: " + node.type + "\\nStatus: " + (node.status || "N/A") + "\\n";
      if (t) {{
        content += "PRs: " + (t.prs.length ? t.prs.join(", ") : "None") + "\\n";
        content += "Dependencies: " + (t.dependencies.length ? t.dependencies.join(", ") : "None") + "\\n\\n";
        content += t.body;
      }}
      document.getElementById("drawer-content").textContent = content;
      document.getElementById("drawer").classList.add("open");
    }}
    function closeDrawer() {{
      document.getElementById("drawer").classList.remove("open");
    }}

    canvas.addEventListener("click", e => {{
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const clicked = nodes.find(n => Math.hypot(n.x - mx, n.y - my) <= n.radius + 4);
      if (clicked) openDrawer(clicked);
      else closeDrawer();
    }});
  </script>
</body>
</html>
"""
