"""Deterministic multi-criteria priority re-ranking and topological backlog ordering.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007; PRD-0005; US-0074.
Target Bounded Context: backlog. File length strictly under 400 lines.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.models import Task
from ..core.parser import extract_frontmatter, parse_priority_ranks
from ..core.topology import CycleResult, detect_cycles
from .queue import BacklogQueue


@dataclass(frozen=True)
class ScoringWeights:
    """Weights for multi-criteria priority scoring calculation."""

    blocker_weight: float = 10.0
    milestone_weight: float = 5.0
    risk_weight: float = 2.0


@dataclass
class PriorityInversion:
    """Represents a topological priority inversion where dependent precedes prerequisite."""

    dependent_id: str
    prerequisite_id: str
    dependent_rank: int
    prerequisite_rank: int

    def to_dict(self) -> dict[str, Any]:
        return {"dependent_id": self.dependent_id, "prerequisite_id": self.prerequisite_id, "dependent_rank": self.dependent_rank, "prerequisite_rank": self.prerequisite_rank}

    def __str__(self) -> str:
        return f"Priority inversion: {self.dependent_id} (rank {self.dependent_rank}) depends on {self.prerequisite_id} (rank {self.prerequisite_rank})"


@dataclass
class TaskScoreBreakdown:
    """Breakdown of calculated multi-criteria scores for a task."""

    canonical_id: str
    downstream_blockers: int
    milestone_horizon: int
    risk_score: int
    total_score: float

    def to_dict(self) -> dict[str, Any]:
        return {"canonical_id": self.canonical_id, "downstream_blockers": self.downstream_blockers, "milestone_horizon": self.milestone_horizon, "risk_score": self.risk_score, "total_score": self.total_score}


@dataclass
class ReorderResult:
    """Result of topological backlog re-ordering."""

    ordered_tasks: list[Task]
    inversions: list[PriorityInversion]
    cycles: list[CycleResult]
    is_valid: bool
    modified: bool
    scores: dict[str, TaskScoreBreakdown] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordered_tasks": [t.canonical_id for t in self.ordered_tasks],
            "inversions_count": len(self.inversions),
            "inversions": [inv.to_dict() for inv in self.inversions],
            "cycles_count": len(self.cycles),
            "is_valid": self.is_valid,
            "modified": self.modified,
            "scores": {k: v.to_dict() for k, v in self.scores.items()},
        }


def normalize_task_id(raw_id: str) -> str:
    """Normalizes raw identifiers to canonical TASK-XXXX or SPIKE-XXXX form."""
    clean = str(raw_id).upper().strip()
    m = re.match(r"^(TASK|SPIKE)[-_]?0*(\d+)$", clean)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(4)}"
    if clean.isdigit():
        return f"TASK-{clean.zfill(4)}"
    return clean


def calculate_priority_score(
    downstream_blocker_count: int,
    milestone_horizon: int,
    risk_score: int,
    weights: ScoringWeights | None = None,
) -> float:
    """Computes deterministic multi-criteria score. Higher score indicates higher priority."""
    w = weights if weights is not None else ScoringWeights()
    horizon_factor = max(0, 100 - milestone_horizon)
    return (
        (downstream_blocker_count * w.blocker_weight)
        + (horizon_factor * w.milestone_weight)
        + (risk_score * w.risk_weight)
    )


def extract_milestone_horizon(task: Task, meta: dict[str, Any] | None = None) -> int:
    """Extracts target milestone number or delivery horizon from task (default 100)."""
    candidates = [meta[k] for k in ("milestone", "target_release", "target_milestone") if meta and k in meta and meta[k] is not None]
    if task.target_release:
        candidates.append(task.target_release)
    for val in candidates:
        if isinstance(val, int):
            return val
        m = re.search(r"(\d+)", str(val))
        if m:
            return int(m.group(1))
    return 100


def extract_risk_score(task: Task, meta: dict[str, Any] | None = None) -> int:
    """Extracts architectural risk score from task metadata (1-4)."""
    candidates = [meta[k] for k in ("risk", "architectural_risk", "impact") if meta and k in meta and meta[k] is not None]
    for val in candidates:
        if isinstance(val, int):
            return max(1, min(5, val))
        s = str(val).lower().strip()
        levels = {"critical": 4, "crit": 4, "high": 3, "medium": 2, "med": 2, "low": 1}
        if s in levels:
            return levels[s]
        m = re.search(r"(\d+)", s)
        if m:
            return max(1, min(5, int(m.group(1))))
    return 2 if (getattr(task, "slice_type", "") == "spike" or task.canonical_id.startswith("SPIKE-")) else 1


def extract_pin(task: Task, meta: dict[str, Any] | None = None) -> tuple[bool, int | None]:
    """Extracts pinned boolean and explicit pin rank position (1-indexed)."""
    p_pin = meta.get("priority_pin", meta.get("pinned")) if meta else None
    if p_pin is None:
        p_pin = getattr(task, "priority_pin", None)
        if p_pin is None and getattr(task, "pinned", False):
            p_pin = True
    if p_pin is not None:
        if isinstance(p_pin, bool) and p_pin:
            return True, task.priority_rank if task.priority_rank < 999999 else None
        try:
            return True, int(p_pin)
        except (ValueError, TypeError):
            return True, None
    return False, None


def find_priority_inversions(tasks: list[Task], ranks: dict[str, int]) -> list[PriorityInversion]:
    """Detects all priority inversions in the given tasks based on current ranks."""
    inversions: list[PriorityInversion] = []
    for t in tasks:
        t_rank = ranks.get(t.canonical_id, 999999)
        for dep in t.dependencies:
            cid = normalize_task_id(dep)
            if cid in ranks and t_rank < ranks[cid]:
                inversions.append(
                    PriorityInversion(
                        dependent_id=t.canonical_id,
                        prerequisite_id=cid,
                        dependent_rank=t_rank,
                        prerequisite_rank=ranks[cid],
                    )
                )
    inversions.sort(key=lambda inv: (inv.dependent_rank, inv.prerequisite_rank))
    return inversions


class BacklogReranker:
    """Coordinates deterministic topological backlog re-ordering with multi-criteria scoring."""

    def __init__(self, backlog_dir: Path, weights: ScoringWeights | None = None):
        self.backlog_dir = backlog_dir.resolve()
        self.weights = weights or ScoringWeights()
        self.queue = BacklogQueue(self.backlog_dir)

    def list_tasks(self) -> list[Task]:
        """Discovers all backlog tasks preserving current priority ranks."""
        tasks = self.queue.list_all_tasks()
        tasks.sort(key=lambda t: (t.priority_rank, t.canonical_id))
        return tasks

    def _load_task_metadata(self, tasks: list[Task]) -> dict[str, dict[str, Any]]:
        meta_by_id: dict[str, dict[str, Any]] = {}
        for t in tasks:
            if t.file_path and t.file_path.exists():
                try:
                    meta, _ = extract_frontmatter(t.file_path.read_text(encoding="utf-8"))
                    meta_by_id[t.canonical_id] = meta
                except Exception:
                    meta_by_id[t.canonical_id] = {}
            else:
                meta_by_id[t.canonical_id] = {}
        return meta_by_id

    def detect_cycles(self, tasks: list[Task] | None = None) -> list[CycleResult]:
        """Checks the task graph for circular dependencies."""
        all_tasks = tasks if tasks is not None else self.list_tasks()
        task_ids = {t.canonical_id for t in all_tasks}
        adj = {
            t.canonical_id: [
                normalize_task_id(d)
                for d in t.dependencies
                if normalize_task_id(d) in task_ids and normalize_task_id(d) != t.canonical_id
            ]
            for t in all_tasks
        }
        return detect_cycles(adj)

    def detect_inversions(self, tasks: list[Task] | None = None) -> list[PriorityInversion]:
        """Finds all current priority inversions across tasks."""
        all_tasks = tasks if tasks is not None else self.list_tasks()
        ranks = parse_priority_ranks(self.backlog_dir) or {t.canonical_id: i for i, t in enumerate(all_tasks, 1)}
        return find_priority_inversions(all_tasks, ranks)

    def compute_scores(self, tasks: list[Task] | None = None) -> dict[str, TaskScoreBreakdown]:
        """Calculates multi-criteria weighted scores for each task."""
        all_tasks = tasks if tasks is not None else self.list_tasks()
        meta_by_id = self._load_task_metadata(all_tasks)
        task_ids = {t.canonical_id for t in all_tasks}

        dependents: dict[str, set[str]] = {t.canonical_id: set() for t in all_tasks}
        for t in all_tasks:
            for dep in t.dependencies:
                cid = normalize_task_id(dep)
                if cid in task_ids and cid != t.canonical_id:
                    dependents[cid].add(t.canonical_id)

        blocker_counts: dict[str, int] = {}
        for t in all_tasks:
            cid = t.canonical_id
            visited, queue = set(), deque(dependents.get(cid, set()))
            while queue:
                curr = queue.popleft()
                if curr not in visited:
                    visited.add(curr)
                    queue.extend(dependents.get(curr, set()) - visited)
            meta = meta_by_id.get(cid, {})
            explicit = meta.get("downstream_blockers", meta.get("blocker_count", 0))
            try:
                explicit_count = int(explicit)
            except (ValueError, TypeError):
                explicit_count = 0
            blocker_counts[cid] = max(len(visited), explicit_count)

        breakdowns: dict[str, TaskScoreBreakdown] = {}
        for t in all_tasks:
            cid = t.canonical_id
            meta = meta_by_id.get(cid, {})
            b_count = blocker_counts[cid]
            horizon = extract_milestone_horizon(t, meta)
            risk = extract_risk_score(t, meta)
            total = calculate_priority_score(b_count, horizon, risk, self.weights)
            breakdowns[cid] = TaskScoreBreakdown(cid, b_count, horizon, risk, total)
        return breakdowns

    def reorder(self, by_weights: bool = True, topological: bool = True) -> ReorderResult:
        """Deterministically orders tasks topologically with score tie-breaking and pin overrides."""
        tasks = self.list_tasks()
        if not tasks:
            return ReorderResult([], [], [], True, False)

        ranks = parse_priority_ranks(self.backlog_dir) or {t.canonical_id: i for i, t in enumerate(tasks, 1)}
        inversions = find_priority_inversions(tasks, ranks)
        cycles = self.detect_cycles(tasks)
        if cycles:
            return ReorderResult(tasks, inversions, cycles, False, False)

        meta_by_id = self._load_task_metadata(tasks)
        scores = self.compute_scores(tasks)
        task_ids = {t.canonical_id for t in tasks}
        prereqs = {
            t.canonical_id: [
                normalize_task_id(d)
                for d in t.dependencies
                if normalize_task_id(d) in task_ids and normalize_task_id(d) != t.canonical_id
            ]
            for t in tasks
        }
        pins = {t.canonical_id: extract_pin(t, meta_by_id.get(t.canonical_id)) for t in tasks}

        remaining, scheduled_ids, ordered = list(tasks), set(), []
        for pos in range(1, len(tasks) + 1):
            ready = [t for t in remaining if all(p in scheduled_ids for p in prereqs[t.canonical_id])]
            if not ready:
                break

            def candidate_key(t: Task) -> tuple[int, float, int, str]:
                cid = t.canonical_id
                is_pinned, pin_pos = pins[cid]
                if is_pinned and pin_pos == pos:
                    p_class = 0
                elif is_pinned and pin_pos is not None and pin_pos < pos:
                    p_class = 1
                else:
                    p_class = 2 if (not is_pinned or pin_pos is None) else 3
                t_score = scores[cid].total_score if cid in scores else 0.0
                t_rank = ranks.get(cid, 999999)
                return (p_class, -t_score, t_rank, cid) if by_weights else (p_class, float(t_rank), -t_score, cid)

            chosen = min(ready, key=candidate_key)
            ordered.append(chosen)
            scheduled_ids.add(chosen.canonical_id)
            remaining.remove(chosen)

        if remaining:
            ordered.extend(remaining)

        modified = [t.canonical_id for t in ordered] != [t.canonical_id for t in tasks]
        return ReorderResult(ordered, inversions, cycles, True, modified, scores)

    def format_priority_file(self, ordered_tasks: list[Task]) -> str:
        """Formats the updated PRIORITY.md content reflecting the ordered tasks."""
        priority_file = self.backlog_dir / "PRIORITY.md"
        header = "# Backlog Priority Index\n\nStrict sequential order of execution for engineering tasks.\n\n"
        existing_lines: dict[str, str] = {}
        if priority_file.exists():
            content = priority_file.read_text(encoding="utf-8")
            first_entry = re.search(r"^-\s*\*\*TASK-", content, re.MULTILINE | re.IGNORECASE)
            if first_entry:
                header = content[: first_entry.start()]
            for line in content.splitlines():
                m = re.search(r"TASK-0*(\d+)", line, re.IGNORECASE)
                if m:
                    existing_lines[f"TASK-{m.group(1).zfill(4)}"] = line

        lines: list[str] = []
        for t in ordered_tasks:
            cid = t.canonical_id
            folder = (
                t.file_path.parent.name
                if t.file_path and t.file_path.parent.name in ("complete", "refined", "proposed")
                else (
                    "refined"
                    if t.status in ("Refined", "Ready", "In-Progress", "Review")
                    else ("complete" if t.status in ("Complete", "Graduated") else "proposed")
                )
            )
            if cid in existing_lines:
                pat = re.compile(rf"(\*\*{cid}\s*\()(?:[^\)]+)(\)\*\*:\s*\[`?[^`\]]+`?\]\()(?:[^/]+)(/[^)]+\))", re.I)
                lines.append(pat.sub(rf"\g<1>{t.status}\g<2>{folder}\g<3>", existing_lines[cid]))
            else:
                stem = t.file_path.stem if t.file_path and t.file_path.name else t.slug
                filename = t.file_path.name if t.file_path and t.file_path.name else f"{stem}.md"
                lines.append(f"- **{cid} ({t.status})**: [`{stem}`]({folder}/{filename})")

        return header.rstrip() + "\n\n" + "\n".join(lines) + "\n"

    def apply(
        self,
        dry_run: bool = False,
        by_weights: bool = True,
        topological: bool = True,
    ) -> tuple[bool, str, ReorderResult]:
        """Executes re-ordering and updates PRIORITY.md unless dry-run is specified."""
        result = self.reorder(by_weights=by_weights, topological=topological)
        if not result.is_valid or result.cycles:
            cycle_desc = result.cycles[0].path_str if result.cycles else "Unknown cycle"
            return False, f"Cannot reorder backlog: circular dependency cycle detected: {cycle_desc}", result

        if dry_run:
            msg = f"Dry-run: detected {len(result.inversions)} priority inversion(s). Backlog re-ordering preview generated ({len(result.ordered_tasks)} tasks)."
            return True, msg, result

        if not result.modified and not result.inversions:
            return True, "Backlog is already topologically sorted with 0 priority inversions.", result

        new_content = self.format_priority_file(result.ordered_tasks)
        priority_file = self.backlog_dir / "PRIORITY.md"
        priority_file.write_text(new_content, encoding="utf-8")

        for idx, t in enumerate(result.ordered_tasks, start=1):
            t.priority_rank = idx

        return True, f"Successfully reordered PRIORITY.md (resolved {len(result.inversions)} priority inversion(s)).", result
