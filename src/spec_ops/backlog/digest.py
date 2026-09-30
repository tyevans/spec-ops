"""Automated daily standup curation digest generator engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0077.
Target Bounded Context: backlog. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import datetime
import re
import subprocess
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .blockers import list_project_blockers
from .digest_models import (
    BlockerItem,
    BufferSummary,
    CompletedThroughputItem,
    StandupDigest,
    WorkerLeaseItem,
    parse_window_to_hours,
)
from .queue import BacklogQueue
from .unblocker import normalize_task_id

__all__ = [
    "BlockerItem",
    "BufferSummary",
    "CompletedThroughputItem",
    "DailyStandupDigestGenerator",
    "StandupDigest",
    "WorkerLeaseItem",
    "generate_standup_digest",
    "parse_window_to_hours",
]


def _parse_iso_time(val: Any) -> datetime.datetime | None:
    """Safely converts ISO-formatted string or timestamp to UTC datetime."""
    if isinstance(val, (int, float)):
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
    if not isinstance(val, str) or not val.strip():
        return None
    val_clean = val.strip()
    try:
        dt = datetime.datetime.fromisoformat(val_clean)
        return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt.astimezone(datetime.timezone.utc)
    except ValueError:
        pass
    try:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", val_clean)
        if m:
            return datetime.datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=datetime.timezone.utc
            )
    except ValueError:
        pass
    return None


class DailyStandupDigestGenerator:
    """Collects backlog throughput, worker leases, blockers, and buffer telemetry."""

    def __init__(self, config: SpecOpsConfig, now: datetime.datetime | None = None):
        self.config = config
        self.root_dir = config.root_dir
        self.backlog_dir = config.backlog_dir
        self.now = now or datetime.datetime.now(tz=datetime.timezone.utc)
        self.queue = BacklogQueue(self.backlog_dir)

    def _get_task_completion_time(self, task: Task) -> datetime.datetime:
        """Finds task completion time from frontmatter, git log, or file mtime."""
        for attr in ("completed_at", "signed_off_at"):
            val = getattr(task, attr, None)
            dt = _parse_iso_time(val)
            if dt:
                return dt
        if getattr(task, "blocker", None) and task.blocker.resolved_at:
            dt = _parse_iso_time(task.blocker.resolved_at)
            if dt:
                return dt

        if (self.root_dir / ".git").exists() and task.file_path.exists():
            try:
                res = subprocess.run(
                    ["git", "log", "-1", "--format=%cI", "--", str(task.file_path)],
                    cwd=self.root_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    dt = _parse_iso_time(res.stdout.strip())
                    if dt:
                        return dt
            except Exception:
                pass

        if task.file_path.exists():
            mtime = task.file_path.stat().st_mtime
            return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)

        return self.now

    def _get_worktree_activity(self, task: Task, wt_dir: Path | None) -> tuple[float | None, bool]:
        """Calculates inactive hours and whether a worktree lease is stalled (>= 24h)."""
        if wt_dir and wt_dir.exists() and wt_dir.is_dir():
            try:
                res = subprocess.run(
                    ["git", "log", "-1", "--format=%ct"],
                    cwd=wt_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip().isdigit():
                    ts = int(res.stdout.strip())
                    commit_dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
                    hours = (self.now - commit_dt).total_seconds() / 3600.0
                    return hours, hours >= 24.0
            except Exception:
                pass

        for attr in ("claimed_at", "timestamp"):
            val = getattr(task, attr, None)
            dt = _parse_iso_time(val)
            if dt:
                hours = (self.now - dt).total_seconds() / 3600.0
                return hours, hours >= 24.0

        if task.file_path.exists():
            mtime = task.file_path.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
            hours = (self.now - dt).total_seconds() / 3600.0
            return hours, hours >= 24.0

        return None, False

    def generate(self, window: str = "24h") -> StandupDigest:
        window_hours = parse_window_to_hours(window)
        all_tasks = self.queue.list_all_tasks()
        completed_ids = self.queue.get_completed_task_ids()

        # 1. Partition tasks by primary status and stage with zero double-counting
        status_counts: dict[str, int] = {}
        for t in all_tasks:
            status_counts[t.status] = status_counts.get(t.status, 0) + 1

        completed_tasks = [t for t in all_tasks if t.file_path.parent.name == "complete" or t.status == "Complete"]
        refined_tasks = [
            t for t in all_tasks
            if t not in completed_tasks
            and (t.file_path.parent.name == "refined" or t.status in ("Refined", "Ready", "In-Progress"))
        ]
        proposed_tasks = [t for t in all_tasks if t not in completed_tasks and t not in refined_tasks]


        # 2. Completed throughput within window
        throughput_items: list[CompletedThroughputItem] = []
        for t in completed_tasks:
            ctime = self._get_task_completion_time(t)
            elapsed_hours = (self.now - ctime).total_seconds() / 3600.0
            if elapsed_hours <= window_hours:
                throughput_items.append(
                    CompletedThroughputItem(
                        task_id=t.canonical_id,
                        title=t.title,
                        completed_at=ctime.isoformat(),
                        target_bc=t.target_bc,
                    )
                )

        # 3. Active worker leases and stalled claim detection
        worker_leases: list[WorkerLeaseItem] = []
        wt_parent = self.root_dir / ".worktrees"
        for t in all_tasks:
            is_claimed = bool(t.claimed_by or t.status.lower() in ("in-progress", "active"))
            if not is_claimed:
                continue

            num_str = t.canonical_id.split("-")[-1].lstrip("0") or "0"
            cand_dirs = [
                wt_parent / f"task-{t.id}",
                wt_parent / f"task-{num_str}",
                wt_parent / f"task-{num_str.zfill(4)}",
            ]
            wt_dir = next((d for d in cand_dirs if d.exists() and d.is_dir()), None)

            dirty = False
            branch = t.branch
            if wt_dir:
                try:
                    res_dirty = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=wt_dir,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    dirty = bool(res_dirty.stdout.strip())
                except Exception:
                    dirty = False

                if not branch:
                    try:
                        res_b = subprocess.run(
                            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            cwd=wt_dir,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        b_str = res_b.stdout.strip()
                        if b_str and b_str != "HEAD":
                            branch = b_str
                    except Exception:
                        pass

            if not branch:
                clean_id = t.canonical_id.lower().replace("task-", "").replace("spike-", "")
                branch = f"{self.config.execution.git_branch_prefix}task-{clean_id}"

            hours_inactive, is_stalled = self._get_worktree_activity(t, wt_dir)
            rel_wt = str(wt_dir.relative_to(self.root_dir)) if wt_dir and wt_dir.is_relative_to(self.root_dir) else ""

            worker_leases.append(
                WorkerLeaseItem(
                    task_id=t.canonical_id,
                    title=t.title,
                    claimed_by=t.claimed_by or "spec-ops-worker",
                    branch=branch,
                    worktree_dir=rel_wt,
                    is_dirty=dirty,
                    last_activity_hours=hours_inactive,
                    is_stalled=is_stalled,
                    status="Stalled" if is_stalled else "Active",
                )
            )

        # 4. Blocker bottlenecks
        raw_blockers = list_project_blockers(self.backlog_dir)
        blocker_items: list[BlockerItem] = [
            BlockerItem(
                task_id=b["task_id"],
                title=b["title"],
                type=b["type"],
                question=b["question"],
                spike_id=b.get("spike_id", ""),
                raised_by=b.get("raised_by", ""),
                raised_at=b.get("raised_at", ""),
            )
            for b in raw_blockers
        ]

        # 5. Ready buffer capacity and candidate proposed tasks
        target = self.config.architecture.buffer_target
        threshold = self.config.architecture.buffer_warning_threshold
        ready_tasks = [
            t for t in all_tasks
            if t.status in ("Refined", "Ready")
            and not t.claimed_by
            and not t.status.startswith("Blocked")
            and all(normalize_task_id(dep) in completed_ids for dep in t.dependencies)
        ]
        ready_count = len(ready_tasks)

        if ready_count < target:
            buffer_status = "UNDER_BUFFERED"
            status_label = "Under-buffered"
            needed = target - ready_count
            buffer_action = f"Promote {needed} proposed tasks"
        elif ready_count > target:
            buffer_status = "OVER_BUFFERED"
            status_label = "Over-buffered"
            buffer_action = f"Drain {ready_count - target} tasks"
        else:
            buffer_status = "OPTIMAL"
            status_label = "Optimal"
            buffer_action = "On track"


        candidate_proposed: list[Task] = [
            t for t in proposed_tasks
            if not t.status.startswith("Blocked")
            and not (t.blocker and t.blocker.question and not t.blocker.resolution)
            and all(normalize_task_id(dep) in completed_ids for dep in t.dependencies)
        ]
        candidate_proposed.sort(key=lambda t: t.priority_rank)

        buffer_summary = BufferSummary(
            ready_count=ready_count,
            target=target,
            threshold=threshold,
            status=buffer_status,
            status_label=status_label,
            recommended_action=buffer_action,
            ready_tasks=[{"task_id": t.canonical_id, "title": t.title} for t in ready_tasks],
            candidate_proposed_tasks=[{"task_id": t.canonical_id, "title": t.title} for t in candidate_proposed],
        )

        # 6. Executive summary table
        stalled_leases = [l for l in worker_leases if l.is_stalled]
        if stalled_leases:
            sl = stalled_leases[0]
            hrs = f"{int(sl.last_activity_hours)}h no activity" if sl.last_activity_hours is not None else "stalled"
            stalled_state = f"{sl.task_id} ({hrs})"
            stalled_action = "Trigger human rescue"
        else:
            stalled_state = "None detected"
            stalled_action = "On track"

        velocity_action = "On track" if len(throughput_items) > 0 else "No recent completions"
        blocker_state = f"{len(blocker_items)} active blockers" if blocker_items else "0 active blockers"
        blocker_action = "Resolve blockers / Scaffold spike" if blocker_items else "On track"

        summary_table = [
            {
                "metric": "Ready Buffer Level",
                "current_state": f"{ready_count}/{target} ({status_label})",
                "recommended_action": buffer_action,
            },
            {
                "metric": f"Velocity ({window})",
                "current_state": f"{len(throughput_items)} tasks completed",
                "recommended_action": velocity_action,
            },
            {
                "metric": "Stalled Worktrees",
                "current_state": stalled_state,
                "recommended_action": stalled_action,
            },
            {
                "metric": "Blocker Bottlenecks",
                "current_state": blocker_state,
                "recommended_action": blocker_action,
            },
        ]

        metrics = {
            "total_tasks": len(all_tasks),
            "completed_count": len(completed_tasks),
            "refined_count": len(refined_tasks),
            "proposed_count": len(proposed_tasks),
            "status_counts": status_counts,
            "completed_in_window": len(throughput_items),
            "ready_buffer_count": ready_count,
            "target_buffer": target,
            "buffer_status": status_label,
            "active_leases_count": len(worker_leases),
            "stalled_leases_count": len(stalled_leases),
            "blockers_count": len(blocker_items),
            "candidate_proposed_count": len(candidate_proposed),
        }

        return StandupDigest(
            window=window,
            window_hours=window_hours,
            generated_at=self.now.isoformat(),
            summary_table=summary_table,
            metrics=metrics,
            completed_throughput=throughput_items,
            active_worker_leases=worker_leases,
            blocker_bottlenecks=blocker_items,
            ready_buffer=buffer_summary,
        )


def generate_standup_digest(
    config: SpecOpsConfig,
    window: str = "24h",
    fmt: str = "markdown",
    now: datetime.datetime | None = None,
) -> str:
    """Generates standup digest serialized as Markdown or JSON string."""
    generator = DailyStandupDigestGenerator(config, now=now)
    digest = generator.generate(window=window)
    if fmt == "json":
        return digest.to_json()
    return digest.to_markdown()
