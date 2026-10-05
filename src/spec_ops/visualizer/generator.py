"""Standalone single-file HTML bundle generator for the SpecOps visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester
from ..core.graph import build_graph_data, process_project_graph
from ..core.parser import SpecOpsParser, extract_frontmatter
from .lead_console import harvest_fleet_telemetry
from .radar_script import harvest_architecture_radar
from .security_metrics import harvest_security_posture
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

    tasks_payload = []
    for t in data.tasks:
        t_meta, _ = extract_frontmatter(t.raw_markdown) if t.raw_markdown else ({}, "")
        has_signed = t_meta.get("has_signed_commits")
        sig_status = str(t_meta.get("commit_signature_status") or "")
        tasks_payload.append(
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
                "signed_off_by": t.signed_off_by or str(t_meta.get("signed_off_by") or ""),
                "signed_off_at": t.signed_off_at or str(t_meta.get("signed_off_at") or ""),
                "has_signed_commits": has_signed,
                "commit_signature_status": sig_status,
                "file_path": _rel_path(config.root_dir, t.file_path),
                "commits": [
                    {
                        "hash": c.hash,
                        "author": c.author,
                        "date": c.date,
                        "subject": c.subject,
                        "signature_status": getattr(c, "signature_status", ""),
                        "is_signed": getattr(c, "is_signed", False),
                        "provenance": getattr(c, "provenance", ""),
                    }
                    for c in t.commits
                ],
            }
        )
    completed_tasks = [t for t in tasks_payload if t.get("status") == "Complete"]
    security_posture = harvest_security_posture(config, tasks=tasks_payload)
    architecture_radar = harvest_architecture_radar(config, data)
    superseded_map = architecture_radar.get("superseded_map", {})
    adr_titles = {a.id: a.title for a in data.adrs}

    adrs_payload = []
    for a in data.adrs:
        a_meta, _ = extract_frontmatter(a.raw_markdown) if a.raw_markdown else ({}, "")
        sup_by = str(a_meta.get("superseded_by") or superseded_map.get(a.id) or "")
        sup_title = adr_titles.get(sup_by, "")
        status = "Superseded" if (sup_by or a.status == "Superseded" or a_meta.get("status") == "Superseded") else (a.status or "Accepted")
        raw_amends = getattr(a, "amends", None) or a_meta.get("amends", [])
        amends_list = [str(x).upper() for x in raw_amends] if isinstance(raw_amends, list) else ([str(raw_amends).upper()] if raw_amends else [])
        raw_amended_by = getattr(a, "amended_by", None) or a_meta.get("amended_by", [])
        amended_by_list = [str(x).upper() for x in raw_amended_by] if isinstance(raw_amended_by, list) else ([str(raw_amended_by).upper()] if raw_amended_by else [])

        adrs_payload.append({
            "id": a.id,
            "title": a.title,
            "status": status,
            "domain": a.domain,
            "context": a.context,
            "decision": a.decision,
            "consequences": a.consequences,
            "implementing_tasks": a.implementing_tasks,
            "raw_markdown": a.raw_markdown,
            "superseded_by": sup_by,
            "superseded_by_title": sup_title,
            "supersedes": str(a_meta.get("supersedes") or getattr(a, "supersedes", "") or ""),
            "amends": amends_list,
            "amended_by": amended_by_list,
            "file_path": _rel_path(config.root_dir, a.file_path),
        })

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
        "tasks": tasks_payload,
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
        "adrs": adrs_payload,
        "bounded_contexts": [
            {
                "id": bc,
                "title": f"Bounded Context: {bc}",
                "tasks": [t.canonical_id for t in data.tasks if t.target_bc == bc],
            }
            for bc in sorted({t.target_bc for t in data.tasks if t.target_bc})
        ],
        "telemetry": harvest_fleet_telemetry(config),
        "security": security_posture,
        "uat": _harvest_uat(config),
        "architecture": architecture_radar,
    }


def _harvest_uat(config: SpecOpsConfig) -> dict[str, Any]:
    try:
        from ..prd.uat import harvest_uat_readiness

        return harvest_uat_readiness(config.root_dir)
    except Exception:
        return {"readiness_percentage": 0.0, "matrix": [], "signoffs": {}}


def generate_standalone_html(config: SpecOpsConfig, back_link: str = "../index.html") -> str:
    from .bundle import compile_bundle

    return compile_bundle(config, back_link=back_link)
