"""Traceability audit, orphan work item detection, and bottleneck deadlock analysis.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007; PRD-0005; US-0016, US-0021.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import re
from typing import Any

from .models import ProjectData, Task
from .topology import DirectedGraph, detect_cycles


def audit_traceability(data: ProjectData) -> tuple[int, list[str]]:
    """Audits bidirectional graph linkages, missing references, boundaries, and cycles."""
    errors: list[str] = []
    stories_by_id = {s.id: s for s in data.stories}
    prds_by_id = {p.id: p for p in data.prds}
    personas_by_id = {p.id.lower(): p for p in data.personas}
    for p in data.personas:
        personas_by_id[p.name.lower()] = p

    # 1. Catch cross-entity circular reference traps & boundary inconsistencies between PRDs and Stories
    for prd in data.prds:
        for sid in prd.linked_stories:
            if sid in stories_by_id:
                story = stories_by_id[sid]
                if story.governing_prd and story.governing_prd != prd.id:
                    errors.append(
                        f"Inconsistent Traceability Boundary: {sid} is claimed by {prd.id} but specifies {story.governing_prd}."
                    )

    # 2. Check task links
    task_graph = DirectedGraph()
    for t in data.tasks:
        task_graph.add_node(t.canonical_id, type="task", status=t.status)
        for dep in t.dependencies:
            clean = dep.replace("TASK-", "").lstrip("0")
            dep_id = f"TASK-{clean.zfill(4)}" if clean else dep
            task_graph.add_edge(t.canonical_id, dep_id, relation="depends_on")

        # Check references in raw markdown or frontmatter
        reported_missing: set[str] = set()
        raw_story_refs = re.findall(r"(?:story:\s*|implements:\s*|\[)(US-\d+)", t.raw_markdown, re.IGNORECASE)
        for sref in raw_story_refs:
            norm_sid = f"US-{sref.split('-')[-1].zfill(4)}"
            if norm_sid not in stories_by_id and norm_sid not in reported_missing:
                reported_missing.add(norm_sid)
                task_filename = t.file_path.stem if t.file_path else t.canonical_id
                errors.append(
                    f"Graph Error: Task {task_filename} references missing story '{sref}'."
                )

        for sid in t.governing_stories:
            norm_sid = f"US-{sid.split('-')[-1].zfill(4)}" if sid.startswith("US-") else sid
            if norm_sid not in stories_by_id and norm_sid not in reported_missing:
                reported_missing.add(norm_sid)
                task_filename = t.file_path.stem if t.file_path else t.canonical_id
                errors.append(
                    f"Graph Error: Task {task_filename} references missing story '{sid}'."
                )

        if not t.governing_stories and not raw_story_refs:
            errors.append(f"Orphan Task: {t.canonical_id} lacks governing user story link.")

    # 3. Check story links
    for s in data.stories:
        if s.governing_prd:
            cid = f"PRD-{s.governing_prd.split('-')[-1].zfill(4)}" if s.governing_prd.split('-')[-1].isdigit() else s.governing_prd
            if cid not in prds_by_id:
                errors.append(f"Graph Error: Story {s.id} references missing PRD '{s.governing_prd}'.")
        else:
            errors.append(f"Orphan Story: {s.id} lacks governing PRD link.")

    # 4. Check PRD persona links
    for p in data.prds:
        persona_val = getattr(p, "target_persona", getattr(p, "persona", ""))
        if persona_val:
            matched = any(p_name in persona_val.lower() for p_name in personas_by_id)
            if not matched:
                errors.append(f"Orphan PRD: {p.id} references missing persona '{persona_val}'.")
        else:
            errors.append(f"Orphan PRD: {p.id} lacks target persona link.")

    # 5. Check task dependency cycles
    cycles = detect_cycles(task_graph)
    for c in cycles:
        if c.size == 2:
            errors.append(f"Cyclic Backlog Dependency Detected: {c.scc[0]} <-> {c.scc[1]}")
            errors.append(f"Cycle Path: {c.path_str}")
        else:
            errors.append(f"Cyclic Backlog Dependency Detected: Strongly Connected Component of size {c.size}")
            errors.append(f"Cycle Path: {c.path_str}")
        errors.append(f"Remediation: {c.remediation}.")

    if errors:
        return 1, errors

    return 0, ["Traceability Invariant Met: 100% graph connectivity with 0 orphan entities."]


def audit_bottlenecks(data: ProjectData, forecast: bool = False) -> tuple[int, list[str]]:
    """Analyzes high-fanout choke points, circular deadlocks, and ready buffer starvation."""
    lines: list[str] = []

    # Build task dependency graph
    task_graph = DirectedGraph()
    tasks_by_id = {t.canonical_id: t for t in data.tasks}
    for t in data.tasks:
        task_graph.add_node(t.canonical_id, type="task", status=t.status, title=t.title, bc=t.target_bc)
        for dep in t.dependencies:
            clean = dep.replace("TASK-", "").lstrip("0")
            dep_id = f"TASK-{clean.zfill(4)}" if clean else dep
            task_graph.add_edge(t.canonical_id, dep_id, relation="depends_on")

    # 1. Circular dependency deadlock detection
    cycles = detect_cycles(task_graph)
    if cycles:
        c = cycles[0]
        lines.append(f"Cyclic Backlog Dependency Detected: Strongly Connected Component of size {c.size}")
        lines.append(f"Directed cycle path: {c.path_str}")
        lines.append(f"Actionable suggestion: {c.remediation}.")
        return 1, lines

    # 2. Forecast mode
    if forecast:
        refined_unassigned = [t for t in data.tasks if t.status == "Refined" and not getattr(t, "assignee", None)]
        if len(refined_unassigned) <= 1:
            lines.append("Buffer Starvation Imminent: Ready queue will deplete in 1 cycle with zero unblocked candidates.")
            in_flight = [t.canonical_id for t in data.tasks if t.status in ("In Progress", "Claimed", "Refined")]
            if in_flight:
                lines.append(f"Suggested action: Immediately unblock or rescue in-flight tasks [{', '.join(in_flight)}] to replenish the ready buffer.")
            else:
                lines.append("Suggested action: Refine proposed backlog candidates via 'spec-ops curate'.")
            return 0, lines

    # 3. High-fanout choke point calculation
    # For each task, count downstream tasks that directly or transitively depend on it
    choke_data: list[tuple[str, int, int, str]] = []
    for tid, t in tasks_by_id.items():
        if t.status in ("Complete", "Graduated"):
            continue
        # Find downstream blocked tasks using BFS on rev_adj
        visited: set[str] = set()
        queue = [tid]
        depth_map: dict[str, int] = {tid: 0}
        while queue:
            curr = queue.pop(0)
            d = depth_map[curr]
            for dependent in task_graph.rev_adj.get(curr, []):
                if dependent not in visited:
                    visited.add(dependent)
                    depth_map[dependent] = d + 1
                    queue.append(dependent)

        if visited:
            max_depth = max(depth_map.values()) if depth_map else 0
            action = "Prioritize Refinement" if t.status == "Proposed" else "Expedite Execution"
            choke_data.append((tid, len(visited), max_depth, action))

    choke_data.sort(key=lambda x: (-x[1], -x[2], x[0]))

    if choke_data:
        top_choke = choke_data[0]
        lines.append("Prioritized Bottleneck Analysis:")
        lines.append(f"| Choke Task | Downstream Blocked Tasks | Critical Path Delay | Recommended Action    |")
        for tid, count, depth, action in choke_data:
            lines.append(
                f"| {tid:<10} | {f'{count} tasks':<24} | {f'{depth} delivery horizons':<19} | {action:<21} |"
            )
        lines.append(f"Highlights {top_choke[0]} as a primary choke point in the visualizer graph with a pulsing alert aura.")
    else:
        lines.append("No high-fanout choke points detected.")

    return 0, lines


def audit_graph_all(data: ProjectData) -> tuple[int, list[str]]:
    """Performs full graph audit: orphans, broken links, cycles, and bottleneck choke points."""
    code, trace_msgs = audit_traceability(data)
    _, bnk_msgs = audit_bottlenecks(data)
    all_msgs = trace_msgs + [""] + bnk_msgs
    return code, all_msgs
