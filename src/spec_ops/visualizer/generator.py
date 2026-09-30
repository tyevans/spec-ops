"""Standalone single-file HTML bundle generator for the SpecOps visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester
from ..core.graph import build_graph_data, process_project_graph
from ..core.parser import SpecOpsParser
from .lead_console import harvest_fleet_telemetry
from .template import VISUALIZER_HTML_TEMPLATE


def _rel_path(root: Path, file_path: Path | None) -> str:
    if not file_path:
        return ""
    try:
        return str(file_path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(file_path)


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
            task.commits = commits
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
                "raw_markdown": t.raw_markdown,
                "file_path": _rel_path(config.root_dir, t.file_path),
                "commits": [
                    {
                        "hash": c.hash,
                        "author": c.author,
                        "date": c.date,
                        "subject": c.subject,
                        "prs": c.prs,
                    }
                    for c in t.commits
                ],
            }
            for t in data.tasks
        ],
        "personas": [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "quote": p.quote,
                "pain_points": p.pain_points,
                "goals": p.goals,
                "features": p.features,
                "story_ids": p.story_ids,
                "raw_markdown": p.raw_markdown,
                "file_path": _rel_path(config.root_dir, p.file_path),
            }
            for p in data.personas
        ],
        "stories": [
            {
                "id": s.id,
                "title": s.title,
                "status": s.status,
                "persona": s.persona,
                "feature": s.feature,
                "governing_prd": s.governing_prd,
                "as_a": s.as_a,
                "i_want": s.i_want,
                "so_that": s.so_that,
                "scenarios": s.scenarios,
                "implementing_tasks": s.implementing_tasks,
                "raw_markdown": s.raw_markdown,
                "file_path": _rel_path(config.root_dir, s.file_path),
            }
            for s in data.stories
        ],
        "prds": [
            {
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "target_persona": p.target_persona,
                "problem_statement": p.problem_statement,
                "outcomes": p.outcomes,
                "linked_stories": p.linked_stories,
                "tasks": p.implementing_tasks,
                "raw_markdown": p.raw_markdown,
                "file_path": _rel_path(config.root_dir, p.file_path),
            }
            for p in data.prds
        ],
        "adrs": [
            {
                "id": a.id,
                "title": a.title,
                "status": a.status,
                "domain": a.domain,
                "context": a.context,
                "decision": a.decision,
                "consequences": a.consequences,
                "implementing_tasks": a.implementing_tasks,
                "raw_markdown": a.raw_markdown,
                "file_path": _rel_path(config.root_dir, a.file_path),
            }
            for a in data.adrs
        ],
        "bounded_contexts": [
            {
                "id": bc,
                "title": f"Bounded Context: {bc}",
                "tasks": [t.canonical_id for t in data.tasks if t.target_bc == bc],
            }
            for bc in sorted({t.target_bc for t in data.tasks if t.target_bc})
        ],
        "telemetry": harvest_fleet_telemetry(config),
    }


def generate_standalone_html(config: SpecOpsConfig, back_link: str = "../index.html") -> str:
    from .bundle import compile_bundle

    return compile_bundle(config, back_link=back_link)
