"""Interactive milestone planning studio, workload balancing, and capacity simulation.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0025.
Target Bounded Context: backlog. Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
import json
import math
from pathlib import Path
import re
from typing import Any

from rich.console import Console
from rich.table import Table

from ..config.loader import SpecOpsConfig
from ..core.migration import canonicalize_task_id, parse_frontmatter_and_body
from .milestone_studio_sync import (
    atomic_write,
    sync_roadmap_milestone,
    update_task_frontmatter_milestone,
)
from .rollover import matches_milestone


@dataclass
class TaskAllocation:
    task_id: str
    title: str
    status: str
    stage: str
    milestone: str
    execution_lane: str
    dependencies: list[str]
    file_path: Path

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["file_path"] = str(self.file_path)
        return d


@dataclass
class FeasibilitySimulation:
    milestone_id: str
    total_tasks: int
    completed_tasks: int
    remaining_tasks: int
    rolling_velocity_weekly: float
    dependency_depth: int
    confidence_intervals: dict[str, Any]
    bottlenecks: list[str] = field(default_factory=list)
    is_feasible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StudioPlanResult:
    milestones: dict[str, list[TaskAllocation]]
    execution_lanes: dict[str, list[TaskAllocation]]
    unassigned: list[TaskAllocation]
    simulations: dict[str, FeasibilitySimulation] = field(default_factory=dict)
    saved: bool = False
    updated_tasks: list[str] = field(default_factory=list)
    updated_roadmap: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix": {
                "milestones": {
                    ms: [t.to_dict() for t in ts] for ms, ts in self.milestones.items()
                },
                "execution_lanes": {
                    lane: [t.to_dict() for t in ts]
                    for lane, ts in self.execution_lanes.items()
                },
                "unassigned": [t.to_dict() for t in self.unassigned],
            },
            "simulations": {
                ms: sim.to_dict() for ms, sim in self.simulations.items()
            },
            "saved": self.saved,
            "updated_tasks": self.updated_tasks,
            "updated_roadmap": self.updated_roadmap,
        }


class MilestoneStudio:
    """Domain service for interactive milestone planning and workload simulation."""

    def __init__(self, config: SpecOpsConfig) -> None:
        self.config = config
        self.backlog_dir = config.backlog_dir
        self.roadmap_path = config.backlog_dir / "ROADMAP.md"

    def collect_tasks(self) -> list[TaskAllocation]:
        """Scans backlog tasks across refined, proposed, and complete stages."""
        tasks: list[TaskAllocation] = []
        stages = [
            ("refined", self.backlog_dir / "refined"),
            ("proposed", self.backlog_dir / "proposed"),
            ("complete", self.backlog_dir / "complete"),
        ]
        roadmap_map = self._parse_roadmap_assignments()

        for stage, sdir in stages:
            if not sdir.exists():
                continue
            for f in sorted(sdir.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                meta, _, _ = parse_frontmatter_and_body(content)
                if not meta or "id" not in meta:
                    continue
                cid = canonicalize_task_id(meta["id"])
                title = str(meta.get("title", f.stem))
                status = str(meta.get("status", stage.capitalize()))
                ms = str(
                    meta.get("milestone")
                    or meta.get("target_milestone")
                    or meta.get("target_release")
                    or roadmap_map.get(cid, "Unassigned")
                )
                lane = str(meta.get("execution_lane") or meta.get("execution_profile") or "agent-autonomous")
                deps = [canonicalize_task_id(d) for d in meta.get("dependencies", []) if d]
                tasks.append(
                    TaskAllocation(
                        task_id=cid,
                        title=title,
                        status=status,
                        stage=stage,
                        milestone=ms,
                        execution_lane=lane,
                        dependencies=deps,
                        file_path=f,
                    )
                )
        return tasks

    def _parse_roadmap_assignments(self) -> dict[str, str]:
        if not self.roadmap_path.exists():
            return {}
        assignments: dict[str, str] = {}
        current_ms = ""
        for line in self.roadmap_path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^##\s+(?:Milestone\s+)?([A-Za-z0-9\-]+)(?::\s*([^(\n]+))?", line, re.IGNORECASE)
            if m:
                current_ms = (m.group(1) or "").strip()
            elif current_ms:
                for tid in re.findall(r"`?(TASK-\d+)`?", line):
                    assignments[canonicalize_task_id(tid)] = current_ms
        return assignments

    def load_rolling_velocity(self) -> float:
        """Loads weekly throughput velocity from metrics or task history."""
        vel_json = self.config.root_dir / ".spec-ops" / "metrics" / "velocity.json"
        if vel_json.exists():
            try:
                data = json.loads(vel_json.read_text(encoding="utf-8"))
                ht = data.get("metrics", {}).get("hybrid_total", {})
                v = ht.get("tasks_per_week")
                if v and float(v) > 0:
                    return round(float(v), 1)
            except Exception:
                pass
        complete_dir = self.backlog_dir / "complete"
        if complete_dir.exists():
            count = len(list(complete_dir.glob("*.md")))
            if count > 0:
                return round(max(1.0, float(count) / 2.0), 1)
        return 5.0

    def simulate_feasibility(
        self,
        milestone_id: str,
        tasks: list[TaskAllocation],
        velocity: float,
    ) -> FeasibilitySimulation:
        """Computes capacity confidence intervals and detects dependency bottlenecks."""
        ms_tasks = [t for t in tasks if matches_milestone(t.milestone, milestone_id) or t.milestone == milestone_id]
        total = len(ms_tasks)
        completed = sum(1 for t in ms_tasks if t.status.lower() in ("complete", "graduated", "shipped"))
        remaining = total - completed

        # Compute dependency depth among remaining tasks
        rem_tasks = {t.task_id: t for t in ms_tasks if t.status.lower() not in ("complete", "graduated", "shipped")}
        depth_memo: dict[str, int] = {}

        def get_depth(tid: str, visited: set[str]) -> int:
            if tid in depth_memo:
                return depth_memo[tid]
            if tid not in rem_tasks or tid in visited:
                return 1
            visited.add(tid)
            d = 1 + max([get_depth(dep, visited.copy()) for dep in rem_tasks[tid].dependencies if dep in rem_tasks] or [0])
            depth_memo[tid] = d
            return d

        max_depth = max([get_depth(tid, set()) for tid in rem_tasks] or [1 if rem_tasks else 0])

        daily_v = max(0.1, velocity / 7.0)
        p50_days = math.ceil(remaining / (daily_v * 1.0)) if remaining > 0 else 0
        p80_days = math.ceil(remaining / (daily_v * 0.8)) if remaining > 0 else 0
        p95_days = math.ceil(remaining / (daily_v * 0.6)) if remaining > 0 else 0

        today = date.today()
        ci = {
            "p50": {"days": p50_days, "projected_date": (today + timedelta(days=p50_days)).isoformat()},
            "p80": {"days": p80_days, "projected_date": (today + timedelta(days=p80_days)).isoformat()},
            "p95": {"days": p95_days, "projected_date": (today + timedelta(days=p95_days)).isoformat()},
        }

        bottlenecks: list[str] = []
        if max_depth >= 4:
            bottlenecks.append(
                f"Prerequisite dependency chain depth of {max_depth} levels exceeds concurrency threshold; serial execution path will delay target horizon."
            )

        completed_all = {t.task_id for t in tasks if t.status.lower() in ("complete", "graduated", "shipped")}
        for t in rem_tasks.values():
            for dep in t.dependencies:
                if dep not in completed_all and dep not in rem_tasks:
                    bottlenecks.append(f"{t.task_id} blocked by uncompleted external prerequisite {dep}.")

        is_feasible = len(bottlenecks) == 0 and (remaining == 0 or velocity >= 1.0)
        return FeasibilitySimulation(
            milestone_id=milestone_id,
            total_tasks=total,
            completed_tasks=completed,
            remaining_tasks=remaining,
            rolling_velocity_weekly=velocity,
            dependency_depth=max_depth,
            confidence_intervals=ci,
            bottlenecks=bottlenecks,
            is_feasible=is_feasible,
        )

    def execute(
        self,
        simulate: bool = False,
        assignments: list[str] | None = None,
        save: bool = False,
        non_interactive: bool = False,
    ) -> StudioPlanResult:
        """Executes milestone planning studio, parsing assignments and synchronizing state."""
        tasks = self.collect_tasks()
        tasks_by_id = {t.task_id: t for t in tasks}
        velocity = self.load_rolling_velocity()
        updated_tasks: list[str] = []
        updated_roadmap = False

        if assignments:
            for item in assignments:
                if "=" not in item:
                    continue
                raw_tid, raw_ms = item.split("=", 1)
                cid = canonicalize_task_id(raw_tid.strip())
                profile = None
                ms = raw_ms.strip()
                if ":" in ms:
                    ms, profile = ms.split(":", 1)
                elif "@" in ms:
                    ms, profile = ms.split("@", 1)

                if cid in tasks_by_id:
                    t = tasks_by_id[cid]
                    t.milestone = ms
                    if profile:
                        t.execution_lane = profile
                    if save:
                        content = t.file_path.read_text(encoding="utf-8")
                        mod, new_content = update_task_frontmatter_milestone(content, ms, profile)
                        if mod:
                            atomic_write(t.file_path, new_content)
                            updated_tasks.append(cid)
                        sync_roadmap_milestone(self.roadmap_path, cid, t.title, ms)
                        updated_roadmap = True

        ms_map: dict[str, list[TaskAllocation]] = {}
        lane_map: dict[str, list[TaskAllocation]] = {
            "agent-autonomous": [],
            "human-lead": [],
            "hybrid-pair": [],
        }
        unassigned: list[TaskAllocation] = []

        for t in tasks:
            if not t.milestone or t.milestone.lower() == "unassigned":
                unassigned.append(t)
            else:
                ms_map.setdefault(t.milestone, []).append(t)
            lane_map.setdefault(t.execution_lane, []).append(t)

        simulations: dict[str, FeasibilitySimulation] = {}
        target_milestones = list(ms_map.keys())
        if simulate or not non_interactive:
            for ms_id in target_milestones:
                simulations[ms_id] = self.simulate_feasibility(ms_id, tasks, velocity)

        return StudioPlanResult(
            milestones=ms_map,
            execution_lanes=lane_map,
            unassigned=unassigned,
            simulations=simulations,
            saved=save,
            updated_tasks=updated_tasks,
            updated_roadmap=updated_roadmap,
        )

    def render(self, result: StudioPlanResult) -> None:
        """Renders rich terminal tables for milestone allocations and feasibility simulation."""
        console = Console()
        console.print("\n[bold cyan]=== SpecOps Interactive Milestone Planning Studio ===[/bold cyan]")

        # Allocation Matrix
        t_matrix = Table(title="Milestone Allocation Matrix", header_style="bold magenta")
        t_matrix.add_column("Milestone", style="bold")
        t_matrix.add_column("Tasks", justify="right")
        t_matrix.add_column("Lanes Breakdown", style="dim")
        t_matrix.add_column("Key Deliverables")

        for ms, ts in result.milestones.items():
            lanes = f"agent:{sum(1 for x in ts if 'agent' in x.execution_lane)} human:{sum(1 for x in ts if 'human' in x.execution_lane)}"
            sample = ", ".join(f"{x.task_id} ({x.title[:20]})" for x in ts[:3])
            t_matrix.add_row(ms, str(len(ts)), lanes, sample)

        if result.unassigned:
            t_matrix.add_row("Unassigned Pool", str(len(result.unassigned)), "-", ", ".join(x.task_id for x in result.unassigned[:4]))
        console.print(t_matrix)

        # Execution Lanes
        t_lanes = Table(title="Workload Balancing: Execution Lanes", header_style="bold green")
        t_lanes.add_column("Execution Lane", style="bold")
        t_lanes.add_column("Assigned Tasks", justify="right")
        t_lanes.add_column("Sample Work Items")
        for lane, ts in result.execution_lanes.items():
            t_lanes.add_row(lane, str(len(ts)), ", ".join(x.task_id for x in ts[:5]))
        console.print(t_lanes)

        # Feasibility Simulations
        if result.simulations:
            t_sim = Table(title="Feasibility Simulation (Empirical Capacity)", header_style="bold yellow")
            t_sim.add_column("Milestone")
            t_sim.add_column("Remaining")
            t_sim.add_column("Depth", justify="right")
            t_sim.add_column("P50 (Nominal)")
            t_sim.add_column("P80 (Standard)")
            t_sim.add_column("P95 (Conservative)")
            t_sim.add_column("Feasibility & Bottlenecks")

            for ms, sim in result.simulations.items():
                p50 = f"{sim.confidence_intervals['p50']['days']}d ({sim.confidence_intervals['p50']['projected_date']})"
                p80 = f"{sim.confidence_intervals['p80']['days']}d ({sim.confidence_intervals['p80']['projected_date']})"
                p95 = f"{sim.confidence_intervals['p95']['days']}d ({sim.confidence_intervals['p95']['projected_date']})"
                b_str = "✅ Feasible" if sim.is_feasible else f"⚠️ Bottlenecks: {'; '.join(sim.bottlenecks)}"
                t_sim.add_row(ms, str(sim.remaining_tasks), str(sim.dependency_depth), p50, p80, p95, b_str)
            console.print(t_sim)

        if result.saved:
            console.print(f"[bold green]✅ Atomically synchronized {len(result.updated_tasks)} task(s) and ROADMAP.md[/bold green]")
