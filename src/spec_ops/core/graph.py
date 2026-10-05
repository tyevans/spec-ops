"""Relational graph builder and health metrics for SpecOps."""

from __future__ import annotations

import re
from typing import Any

from .models import (
    GraphData,
    GraphEdge,
    GraphNode,
    ProjectData,
    TraceabilityEdge,
)

STATUS_COLORS = {
    "Complete": "#10B981",
    "Refined": "#F59E0B",
    "Proposed": "#8B5CF6",
    "Accepted": "#06B6D4",
    "Shipped": "#10B981",
}


def link_personas_to_stories(data: ProjectData) -> None:
    p_by_name = {p.name.lower(): p for p in data.personas}
    p_by_id = {p.id.lower(): p for p in data.personas}
    for s in data.stories:
        p_str = s.persona.lower()
        matched = None
        for name, p in p_by_name.items():
            if name in p_str:
                matched = p
                break
        if not matched:
            matched = p_by_id.get(p_str.split()[0]) if p_str else None
        if matched and s.id not in matched.story_ids:
            matched.story_ids.append(s.id)


def link_tasks_to_entities(data: ProjectData) -> None:
    prds = {p.id: p for p in data.prds}
    tasks = {t.canonical_id: t for t in data.tasks}
    stories = {s.id: s for s in data.stories}
    adrs = {a.id: a for a in data.adrs}

    for prd in data.prds:
        for tid in prd.implementing_tasks:
            if tid in tasks and prd.id not in tasks[tid].governing_prds:
                tasks[tid].governing_prds.append(prd.id)

    for t in data.tasks:
        for prd_id in re.findall(r"PRD-\d+", t.raw_markdown, re.IGNORECASE) + t.governing_prds:
            cid = f"PRD-{prd_id.split('-')[-1].zfill(4)}"
            if cid not in t.governing_prds:
                t.governing_prds.append(cid)
            if cid in prds and t.canonical_id not in prds[cid].implementing_tasks:
                prds[cid].implementing_tasks.append(t.canonical_id)

        for us_id in re.findall(r"US-\d+", t.raw_markdown, re.IGNORECASE) + t.governing_stories:
            cid = f"US-{us_id.split('-')[-1].zfill(4)}"
            if cid not in t.governing_stories:
                t.governing_stories.append(cid)
            if cid in stories and t.canonical_id not in stories[cid].implementing_tasks:
                stories[cid].implementing_tasks.append(t.canonical_id)

        for adr_id in re.findall(r"ADR-\d+", t.raw_markdown, re.IGNORECASE) + t.governing_adrs:
            cid = f"ADR-{adr_id.split('-')[-1].zfill(4)}"
            if cid not in t.governing_adrs:
                t.governing_adrs.append(cid)
            if cid in adrs and t.canonical_id not in adrs[cid].implementing_tasks:
                adrs[cid].implementing_tasks.append(t.canonical_id)


def link_stories_to_prds(data: ProjectData) -> None:
    prds = {p.id: p for p in data.prds}
    stories = {s.id: s for s in data.stories}

    for prd in data.prds:
        for sid in prd.linked_stories:
            if sid in stories and not stories[sid].governing_prd:
                stories[sid].governing_prd = prd.id

    for s in data.stories:
        if s.governing_prd:
            cid = f"PRD-{s.governing_prd.split('-')[-1].zfill(4)}" if s.governing_prd.split('-')[-1].isdigit() else s.governing_prd
            if cid in prds and s.id not in prds[cid].linked_stories:
                prds[cid].linked_stories.append(s.id)


def generate_traceability_edges(data: ProjectData) -> list[TraceabilityEdge]:
    edges: list[TraceabilityEdge] = []
    add = edges.append

    # Persona desires Story
    for p in data.personas:
        for s in p.story_ids:
            add(TraceabilityEdge("persona", p.id, "story", s, "desires"))

    # Story specifies PRD
    for s in data.stories:
        if s.governing_prd:
            add(TraceabilityEdge("story", s.id, "prd", s.governing_prd, "specifies"))

    # PRD implements Task
    for prd in data.prds:
        for t in prd.implementing_tasks:
            add(TraceabilityEdge("prd", prd.id, "task", t, "implements"))

    # Task governed_by ADR, deploys_to BC, depends_on Task
    for t in data.tasks:
        for a in t.governing_adrs:
            add(TraceabilityEdge("task", t.canonical_id, "adr", a, "governed_by"))
        if t.target_bc:
            add(TraceabilityEdge("task", t.canonical_id, "bc", t.target_bc, "deploys_to"))
        for d in t.dependencies:
            clean = d.replace("TASK-", "").lstrip("0")
            dep_id = f"TASK-{clean.zfill(4)}" if clean else d
            add(TraceabilityEdge("task", t.canonical_id, "task", dep_id, "depends_on"))

    # ADR amends ADR and ADR supersedes ADR
    existing_adr_edges = {(e.source_id, e.target_id, e.relation) for e in edges}
    for a in data.adrs:
        for target_adr in a.amends:
            norm_target = f"ADR-{target_adr.split('-')[-1].zfill(4)}" if target_adr.startswith("ADR-") else target_adr
            if (a.id, norm_target, "amends") not in existing_adr_edges:
                add(TraceabilityEdge("adr", a.id, "adr", norm_target, "amends"))
                existing_adr_edges.add((a.id, norm_target, "amends"))
        for amending_adr in a.amended_by:
            norm_src = f"ADR-{amending_adr.split('-')[-1].zfill(4)}" if amending_adr.startswith("ADR-") else amending_adr
            if (norm_src, a.id, "amends") not in existing_adr_edges:
                add(TraceabilityEdge("adr", norm_src, "adr", a.id, "amends"))
                existing_adr_edges.add((norm_src, a.id, "amends"))
        if a.supersedes:
            norm_target = f"ADR-{a.supersedes.split('-')[-1].zfill(4)}" if a.supersedes.startswith("ADR-") else a.supersedes
            if (a.id, norm_target, "supersedes") not in existing_adr_edges:
                add(TraceabilityEdge("adr", a.id, "adr", norm_target, "supersedes"))
                existing_adr_edges.add((a.id, norm_target, "supersedes"))
        if a.superseded_by:
            norm_src = f"ADR-{a.superseded_by.split('-')[-1].zfill(4)}" if a.superseded_by.startswith("ADR-") else a.superseded_by
            if (norm_src, a.id, "supersedes") not in existing_adr_edges:
                add(TraceabilityEdge("adr", norm_src, "adr", a.id, "supersedes"))
                existing_adr_edges.add((norm_src, a.id, "supersedes"))

    data.edges = edges
    return edges


def compute_health_metrics(data: ProjectData, target_buffer: int = 10) -> dict[str, Any]:
    complete_count = sum(1 for t in data.tasks if t.status == "Complete")
    refined_count = sum(1 for t in data.tasks if t.status == "Refined")
    proposed_count = sum(1 for t in data.tasks if t.status == "Proposed")

    buffer_health = "OPTIMAL"
    if refined_count < target_buffer // 2:
        buffer_health = "UNDER_BUFFERED"
    elif refined_count > target_buffer * 2:
        buffer_health = "OVER_BUFFERED"

    metrics = {
        "total_tasks": len(data.tasks),
        "complete_tasks": complete_count,
        "refined_tasks": refined_count,
        "proposed_tasks": proposed_count,
        "total_stories": len(data.stories),
        "total_prds": len(data.prds),
        "total_adrs": len(data.adrs),
        "total_personas": len(data.personas),
        "total_edges": len(data.edges),
        "ready_buffer_health": buffer_health,
    }
    data.health_metrics = metrics
    return metrics


def build_graph_data(data: ProjectData) -> GraphData:
    nodes: list[GraphNode] = []

    for p in data.personas:
        nodes.append(GraphNode(p.id, p.name, "persona", "#F59E0B", role=p.role))

    for s in data.stories:
        nodes.append(GraphNode(s.id, s.title, "story", "#06B6D4", metadata={"persona": s.persona}))

    for prd in data.prds:
        nodes.append(GraphNode(prd.id, prd.title, "prd", "#F43F5E", status=prd.status))

    for t in data.tasks:
        color = STATUS_COLORS.get(t.status, "#8B5CF6")
        nodes.append(
            GraphNode(
                t.canonical_id,
                t.title,
                "task",
                color,
                status=t.status,
                bc=t.target_bc,
                prs=t.prs,
                metadata={"priority": t.priority_rank},
            )
        )

    seen_bcs = set()
    for t in data.tasks:
        if t.target_bc and t.target_bc not in seen_bcs:
            seen_bcs.add(t.target_bc)
            nodes.append(
                GraphNode(
                    t.target_bc,
                    f"BC: {t.target_bc}",
                    "bc",
                    "#EC4899",
                    bc=t.target_bc,
                )
            )

    for a in data.adrs:
        nodes.append(GraphNode(a.id, a.title, "adr", "#6366F1", domain=a.domain))

    edges = [
        GraphEdge(e.source_id, e.target_id, e.relation, e.source_type, e.target_type)
        for e in data.edges
    ]

    return GraphData(nodes=nodes, edges=edges)


def process_project_graph(data: ProjectData, target_buffer: int = 10) -> ProjectData:
    """Runs all linking, edge generation, and metrics on ProjectData."""
    link_personas_to_stories(data)
    link_tasks_to_entities(data)
    link_stories_to_prds(data)
    generate_traceability_edges(data)
    compute_health_metrics(data, target_buffer=target_buffer)
    return data
