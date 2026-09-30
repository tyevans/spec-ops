"""Task dependency DAG engine, execution waves, and hierarchical tree formatting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from ..core.models import Task
from .tree_format import (
    build_forward_tree,
    build_prerequisite_tree,
    render_node_label,
    render_waves_panel,
)


def normalize_task_id(raw_id: str) -> str:
    """Normalizes task identifiers to canonical format (e.g. TASK-0045, SPIKE-0001)."""
    s = str(raw_id).strip()
    m = re.search(r"(\d+)", s)
    if not m:
        return s.upper()
    num = m.group(1).zfill(4)
    prefix = "SPIKE-" if "SPIKE" in s.upper() else "TASK-"
    return f"{prefix}{num}"


@dataclass
class TaskNodeState:
    task: Task
    canonical_id: str
    is_complete: bool
    is_ready: bool
    is_blocked: bool
    is_blocked_by_unknown: bool
    unsatisfied_dependencies: list[str] = field(default_factory=list)
    unlocked_dependents: list[str] = field(default_factory=list)
    wave: int = -1
    downstream_impact_count: int = 0


class TaskDependencyTreeEngine:
    """Computes dependency hierarchies, execution waves, choke points, and tree views."""

    def __init__(
        self, tasks: list[Task], completed_ids: set[str] | None = None
    ) -> None:
        self.tasks = tasks
        self.tasks_by_id: dict[str, Task] = {t.canonical_id: t for t in tasks}
        self.completed_ids: set[str] = {
            normalize_task_id(cid) for cid in (completed_ids or set())
        }

        # If completed_ids was not explicitly supplied, discover from tasks list
        if not self.completed_ids:
            for t in tasks:
                if t.status in ("Complete", "Graduated"):
                    self.completed_ids.add(t.canonical_id)

        self.upstream: dict[str, list[str]] = {}
        self.downstream: dict[str, list[str]] = {}
        self._build_adjacency()
        self.states = self._evaluate_node_states()
        self.cycles = self._detect_cycles()
        self.waves = self._compute_execution_waves()
        self._compute_downstream_impact()

    def _build_adjacency(self) -> None:
        """Constructs upstream (dependencies) and downstream (dependents) graphs."""
        for t in self.tasks:
            cid = t.canonical_id
            self.upstream.setdefault(cid, [])
            self.downstream.setdefault(cid, [])

        for t in self.tasks:
            cid = t.canonical_id
            for dep in t.dependencies:
                dep_cid = normalize_task_id(dep)
                if dep_cid not in self.upstream[cid]:
                    self.upstream[cid].append(dep_cid)
                self.downstream.setdefault(dep_cid, [])
                if cid not in self.downstream[dep_cid]:
                    self.downstream[dep_cid].append(cid)

    def _evaluate_node_states(self) -> dict[str, TaskNodeState]:
        """Classifies the readiness, completion, and blocker state for each task."""
        states: dict[str, TaskNodeState] = {}
        for t in self.tasks:
            cid = t.canonical_id
            is_comp = cid in self.completed_ids or t.status in ("Complete", "Graduated")
            unsatisfied = [
                dep
                for dep in self.upstream.get(cid, [])
                if dep not in self.completed_ids
            ]
            has_unknown_blocker = bool(t.blocker and t.blocker.question) or str(
                t.status
            ).startswith("Blocked")

            is_ready = (
                (not is_comp) and len(unsatisfied) == 0 and not has_unknown_blocker
            )
            is_blocked = (not is_comp) and (len(unsatisfied) > 0 or has_unknown_blocker)

            states[cid] = TaskNodeState(
                task=t,
                canonical_id=cid,
                is_complete=is_comp,
                is_ready=is_ready,
                is_blocked=is_blocked,
                is_blocked_by_unknown=has_unknown_blocker,
                unsatisfied_dependencies=unsatisfied,
                unlocked_dependents=list(self.downstream.get(cid, [])),
            )
        return states

    def _detect_cycles(self) -> list[list[str]]:
        """Finds any circular dependencies using depth-first search."""
        visited: set[str] = set()
        rec_stack: list[str] = []
        cycles: list[list[str]] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            for neighbor in self.upstream.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    idx = rec_stack.index(neighbor)
                    cycle = rec_stack[idx:] + [neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)
            rec_stack.pop()

        for node in list(self.upstream.keys()):
            if node not in visited:
                dfs(node)
        return cycles

    def _compute_execution_waves(self) -> list[list[str]]:
        """Partitions non-complete tasks into sequential execution waves."""
        waves: list[list[str]] = []
        simulated_complete = set(self.completed_ids)
        remaining = {cid for cid, s in self.states.items() if not s.is_complete}

        while remaining:
            wave: list[str] = []
            for cid in sorted(
                remaining, key=lambda x: self.states[x].task.priority_rank
            ):
                state = self.states[cid]
                # Blocked by an unknown cannot be in an unblocked wave until resolved
                if state.is_blocked_by_unknown:
                    continue
                deps = self.upstream.get(cid, [])
                if all(dep in simulated_complete for dep in deps):
                    wave.append(cid)

            if not wave:
                # Remainder are either cycles, blocked by unknowns, or orphaned deps
                break

            waves.append(wave)
            wave_num = len(waves) - 1
            for cid in wave:
                self.states[cid].wave = wave_num
                simulated_complete.add(cid)
                remaining.remove(cid)

        # Any leftover blocked items marked with wave -1 or latest+1
        return waves

    def _compute_downstream_impact(self) -> None:
        """Calculates total transitive downstream tasks unlocked by each task."""
        for cid, state in self.states.items():
            visited: set[str] = set()
            stack = list(self.downstream.get(cid, []))
            while stack:
                curr = stack.pop()
                if curr not in visited and curr != cid:
                    visited.add(curr)
                    stack.extend(self.downstream.get(curr, []))
            state.downstream_impact_count = len(visited)

    def get_choke_points(self, top_n: int = 5) -> list[TaskNodeState]:
        """Returns non-complete tasks that block the largest number of downstream tasks."""
        non_comp = [s for s in self.states.values() if not s.is_complete]
        non_comp.sort(key=lambda s: (-s.downstream_impact_count, s.task.priority_rank))
        return non_comp[:top_n]

    def render_node_label(self, cid: str) -> Text:
        """Renders rich badge and title for a task node."""
        return render_node_label(self.states, cid)

    def build_forward_tree(
        self, focus_id: str | None = None, include_completed: bool = False
    ) -> Tree:
        """Constructs forward execution tree (Unlocks / Flow view)."""
        return build_forward_tree(
            self, focus_id=focus_id, include_completed=include_completed
        )

    def build_prerequisite_tree(
        self, focus_id: str | None = None, include_completed: bool = False
    ) -> Tree:
        """Constructs reverse prerequisite tree (Blocked By view)."""
        return build_prerequisite_tree(
            self, focus_id=focus_id, include_completed=include_completed
        )

    def render_waves_panel(self) -> Panel:
        """Renders delivery horizons / execution waves table."""
        return render_waves_panel(self)

    def to_dict(self) -> dict[str, Any]:
        """Exports graph state, waves, and choke points as a JSON-serializable dictionary."""
        return {
            "completed_count": len(self.completed_ids),
            "waves": self.waves,
            "cycles": self.cycles,
            "choke_points": [
                {
                    "task_id": cp.canonical_id,
                    "title": cp.task.title,
                    "downstream_unlocked_count": cp.downstream_impact_count,
                    "status": cp.task.status,
                }
                for cp in self.get_choke_points(10)
            ],
            "tasks": {
                cid: {
                    "title": s.task.title,
                    "status": s.task.status,
                    "is_complete": s.is_complete,
                    "is_ready": s.is_ready,
                    "is_blocked": s.is_blocked,
                    "is_blocked_by_unknown": s.is_blocked_by_unknown,
                    "unsatisfied_dependencies": s.unsatisfied_dependencies,
                    "unlocked_dependents": s.unlocked_dependents,
                    "wave": s.wave,
                    "downstream_impact": s.downstream_impact_count,
                    "blocker": {
                        "question": s.task.blocker.question,
                        "type": s.task.blocker.type,
                        "spike_id": s.task.blocker.spike_id,
                    }
                    if s.task.blocker
                    else None,
                }
                for cid, s in self.states.items()
            },
        }
