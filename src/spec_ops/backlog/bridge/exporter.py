"""Backlog status snapshot exporter for executive roadmaps and stakeholder reviews (US-0079, ADR-0001)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...config.loader import load_config
from ...config.models import SpecOpsConfig
from ..queue import BacklogQueue


def export_backlog_snapshot(
    backlog_dir: Path,
    config: SpecOpsConfig | None = None,
    format: str = "markdown",
    output_path: Path | str | None = None,
) -> str:
    """Exports structured backlog status snapshot as a Diataxis reference document."""
    cfg = config or load_config(root_dir=backlog_dir.parent.parent)
    queue = BacklogQueue(backlog_dir)

    all_tasks = queue.list_all_tasks()
    completed_tasks = [t for t in all_tasks if t.status.lower() == "complete"]
    refined_tasks = [t for t in all_tasks if t.status.lower() in ("refined", "ready")]
    proposed_tasks = [t for t in all_tasks if t.status.lower() == "proposed"]

    total = len(all_tasks)
    completed_count = len(completed_tasks)
    refined_count = len(refined_tasks)
    proposed_count = len(proposed_tasks)

    burn_up_pct = round((completed_count / total * 100.0), 1) if total > 0 else 0.0

    buffer_target = 10
    if hasattr(cfg, "architecture") and hasattr(cfg.architecture, "buffer_target"):
        buffer_target = cfg.architecture.buffer_target

    if refined_count >= buffer_target:
        buffer_status = "Optimal [Green]"
    elif refined_count >= max(1, buffer_target // 2):
        buffer_status = "Adequate [Yellow]"
    else:
        buffer_status = "Starving [Red]"

    # Parse roadmap milestones if present
    roadmap_file = backlog_dir / "ROADMAP.md"
    milestones_data: list[dict[str, Any]] = []
    if roadmap_file.exists():
        from ...prd.exporter import parse_roadmap_file

        raw_milestones = parse_roadmap_file(roadmap_file)
        completed_ids = {t.canonical_id for t in completed_tasks}
        for m in raw_milestones:
            m_tasks = m.get("tasks", [])
            m_comp = [tid for tid in m_tasks if tid in completed_ids]
            m_total = len(m_tasks)
            m_pct = round((len(m_comp) / m_total * 100.0), 1) if m_total > 0 else 0.0
            milestones_data.append(
                {
                    "id": m.get("id", ""),
                    "title": m.get("title", ""),
                    "horizon": m.get("horizon", "Unscheduled"),
                    "status": m.get("status", "Active"),
                    "total_tasks": m_total,
                    "completed_tasks": len(m_comp),
                    "progress_pct": m_pct,
                }
            )

    if format.lower() == "json":
        data = {
            "total_tasks": total,
            "completed_tasks": completed_count,
            "refined_tasks": refined_count,
            "proposed_tasks": proposed_count,
            "burn_up_pct": burn_up_pct,
            "buffer_target": buffer_target,
            "buffer_status": buffer_status,
            "milestones": milestones_data,
        }
        content = json.dumps(data, indent=2)
    else:
        milestone_rows: list[str] = []
        if milestones_data:
            milestone_rows.append("| Milestone | Target Horizon | Status | Tasks | Completed | Progress |")
            milestone_rows.append("|---|---|---|---|---|---|")
            for m in milestones_data:
                milestone_rows.append(
                    f"| {m['id']}: {m['title']} | {m['horizon']} | {m['status']} | {m['total_tasks']} | {m['completed_tasks']} | {m['progress_pct']}% |"
                )
        else:
            milestone_rows.append("*No roadmap milestones configured in ROADMAP.md.*")

        milestone_table = "\n".join(milestone_rows)

        content = f"""# Reference: Backlog Status & Delivery Snapshot

Structured Diataxis reference document displaying completion burn-up, buffer health, and milestone delivery estimates.

## Completion Burn-up
- **Total Backlog Work Items**: {total}
- **Completed Tasks**: {completed_count} ({burn_up_pct}% delivered)
- **Refined Active Buffer**: {refined_count} tasks
- **Proposed Tasks**: {proposed_count} tasks

## Buffer Health
- **Refined Queue Target**: {buffer_target} tasks
- **Current Buffer Status**: {refined_count}/{buffer_target} ({buffer_status})

## Milestone Delivery Estimates
{milestone_table}
"""

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")

    return content
