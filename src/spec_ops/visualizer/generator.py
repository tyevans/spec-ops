"""Standalone single-file HTML bundle generator for the SpecOps visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester
from ..core.graph import build_graph_data, process_project_graph
from ..core.parser import SpecOpsParser
from .template import VISUALIZER_HTML_TEMPLATE


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
    return VISUALIZER_HTML_TEMPLATE.format(title=title, data_json=data_json)
