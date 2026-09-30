"""Data models and serialization formatters for daily standup digest.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007; PRD-0005; US-0077.
Target Bounded Context: backlog. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


def parse_window_to_hours(window_str: str) -> float:
    """Parses a time window string (e.g. '24h', '48h', '7d', '1d', '30m') to float hours."""
    s = str(window_str).strip().lower()
    if not s:
        return 24.0
    units = [("d", 24.0), ("h", 1.0), ("m", 1.0 / 60.0), ("w", 168.0)]
    for suffix, factor in units:
        if s.endswith(suffix):
            try:
                return float(s[: -len(suffix)]) * factor
            except ValueError:
                return 24.0
    try:
        return float(s)
    except ValueError:
        return 24.0


@dataclass
class CompletedThroughputItem:
    task_id: str
    title: str
    completed_at: str
    target_bc: str


@dataclass
class WorkerLeaseItem:
    task_id: str
    title: str
    claimed_by: str
    branch: str
    worktree_dir: str
    is_dirty: bool
    last_activity_hours: float | None
    is_stalled: bool
    status: str


@dataclass
class BlockerItem:
    task_id: str
    title: str
    type: str
    question: str
    spike_id: str
    raised_by: str
    raised_at: str


@dataclass
class BufferSummary:
    ready_count: int
    target: int
    threshold: int
    status: str
    status_label: str
    recommended_action: str
    ready_tasks: list[dict[str, str]] = field(default_factory=list)
    candidate_proposed_tasks: list[dict[str, str]] = field(default_factory=list)


@dataclass
class StandupDigest:
    window: str
    window_hours: float
    generated_at: str
    summary_table: list[dict[str, str]]
    metrics: dict[str, Any]
    completed_throughput: list[CompletedThroughputItem]
    active_worker_leases: list[WorkerLeaseItem]
    blocker_bottlenecks: list[BlockerItem]
    ready_buffer: BufferSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "window_hours": self.window_hours,
            "generated_at": self.generated_at,
            "summary_table": self.summary_table,
            "metrics": self.metrics,
            "completed_throughput": [asdict(x) for x in self.completed_throughput],
            "active_worker_leases": [asdict(x) for x in self.active_worker_leases],
            "blocker_bottlenecks": [asdict(x) for x in self.blocker_bottlenecks],
            "ready_buffer": asdict(self.ready_buffer),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines: list[str] = [
            "# Daily Standup Curation Digest",
            f"Generated at: {self.generated_at} (Window: {self.window})",
            "",
            "## Executive Summary",
            "| Metric | Current State | Recommended Action |",
            "| :--- | :--- | :--- |",
        ]
        for row in self.summary_table:
            lines.append(f"| {row['metric']} | {row['current_state']} | {row['recommended_action']} |")

        lines.extend(["", f"## Completed Throughput ({self.window})"])
        if self.completed_throughput:
            for c in self.completed_throughput:
                bc_str = f" [BC: {c.target_bc}]" if c.target_bc else ""
                lines.append(f"- **{c.task_id}**: {c.title}{bc_str}")
        else:
            lines.append(f"Zero tasks completed within the last {self.window}.")

        lines.extend(["", "## Active Worker Leases"])
        if self.active_worker_leases:
            for l in self.active_worker_leases:
                act = f"{int(l.last_activity_hours)}h no activity" if l.last_activity_hours is not None else "active"
                tag = " [STALLED]" if l.is_stalled else ""
                wt = f" (Worktree: {l.worktree_dir})" if l.worktree_dir else ""
                lines.append(f"- **{l.task_id}**: Claimed by {l.claimed_by} on {l.branch}{wt} ({act}){tag}")
        else:
            lines.append("Zero active worker worktree claims.")

        lines.extend(["", "## Blocker Bottlenecks"])
        if self.blocker_bottlenecks:
            for b in self.blocker_bottlenecks:
                spk = f", Linked Spike: {b.spike_id}" if b.spike_id else ""
                lines.append(f"- **{b.task_id}**: {b.question} (Type: {b.type}{spk})")
        else:
            lines.append("Zero active blockers in project backlog.")

        lines.extend(["", "## Ready Buffer & Refinement Candidates"])
        lines.append(f"- **Buffer Level**: {self.ready_buffer.ready_count}/{self.ready_buffer.target} ({self.ready_buffer.status_label})")
        lines.append(f"- **Recommended Action**: {self.ready_buffer.recommended_action}")

        lines.append("")
        lines.append(f"### Candidate Proposed Tasks Ready for Immediate Refinement ({len(self.ready_buffer.candidate_proposed_tasks)})")
        if self.ready_buffer.candidate_proposed_tasks:
            for cand in self.ready_buffer.candidate_proposed_tasks:
                lines.append(f"- **{cand['task_id']}**: {cand['title']}")
        else:
            lines.append("Zero proposed tasks currently eligible for immediate refinement.")

        return "\n".join(lines)
