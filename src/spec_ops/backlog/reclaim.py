"""Automated stalled worker claim reclamation and lease heartbeat engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009; PRD-0005; US-0077.
Target Bounded Context: backlog. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .lock import BacklogLock
from .queue import BacklogQueue, write_task_file

__all__ = [
    "StalledClaimInfo",
    "StalledClaimReclamationResult",
    "StalledClaimReclaimer",
    "reclaim_stalled_claims",
]


def _parse_iso_time(val: Any) -> datetime.datetime | None:
    """Safely converts ISO-formatted string, numeric timestamp, or date to UTC datetime."""
    if isinstance(val, (int, float)):
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
    if not isinstance(val, str) or not val.strip():
        return None
    val_clean = val.strip()
    try:
        return datetime.datetime.fromtimestamp(float(val_clean), tz=datetime.timezone.utc)
    except ValueError:
        pass
    try:
        dt = datetime.datetime.fromisoformat(val_clean)
        return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt.astimezone(datetime.timezone.utc)
    except ValueError:
        pass
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", val_clean)
    if m:
        return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=datetime.timezone.utc)
    return None


@dataclass
class StalledClaimInfo:
    """Telemetry and identity details for a claimed task."""

    task_id: str
    title: str
    claimed_by: str
    claimed_at: str = ""
    heartbeat_at: str = ""
    inactive_hours: float = 0.0
    worktree_dir: str = ""
    status: str = "Stalled"
    last_activity_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "claimed_by": self.claimed_by,
            "claimed_at": self.claimed_at,
            "heartbeat_at": self.heartbeat_at,
            "inactive_hours": round(self.inactive_hours, 2),
            "worktree_dir": self.worktree_dir,
            "status": self.status,
            "last_activity_source": self.last_activity_source,
        }


@dataclass
class StalledClaimReclamationResult:
    """Structured outcome of a stalled claim reclamation scan."""

    reclaimed_count: int
    reclaimed_ids: list[str]
    reclaimed_tasks: list[StalledClaimInfo]
    active_count: int
    active_tasks: list[StalledClaimInfo]
    timeout_hours: float
    dry_run: bool
    audit_trail: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reclaimed_count": self.reclaimed_count,
            "reclaimed_ids": self.reclaimed_ids,
            "reclaimed_tasks": [t.to_dict() for t in self.reclaimed_tasks],
            "active_count": self.active_count,
            "active_tasks": [t.to_dict() for t in self.active_tasks],
            "timeout_hours": self.timeout_hours,
            "dry_run": self.dry_run,
            "audit_trail": self.audit_trail,
        }

    def render_console(self, console: Console | None = None) -> None:
        con = console or Console()
        prefix = "[bold cyan][DRY RUN][/bold cyan] " if self.dry_run else ""
        if self.reclaimed_count == 0:
            con.print(f"✅ {prefix}[bold green]Zero stalled worker claims detected (timeout: {self.timeout_hours:.1f}h).[/bold green]")
            return

        action_msg = "Eligible for reclamation" if self.dry_run else "Successfully reclaimed"
        con.print(f"🔄 {prefix}[bold yellow]{action_msg} {self.reclaimed_count} stalled claim(s) (timeout: {self.timeout_hours:.1f}h):[/bold yellow]")
        table = Table(title=f"{prefix}Reclaimed Worker Leases", expand=True)
        table.add_column("Task ID", style="bold cyan")
        table.add_column("Title", style="white")
        table.add_column("Claimant", style="yellow")
        table.add_column("Inactive", style="magenta")
        table.add_column("Activity Source", style="dim")
        table.add_column("New Status", style="green")

        for t in self.reclaimed_tasks:
            table.add_row(t.task_id, t.title, t.claimed_by, f"{t.inactive_hours:.1f}h", t.last_activity_source or "claim", "Refined")
        con.print(table)


class StalledClaimReclaimer:
    """Evaluates task claims, monitors worker heartbeats, and reclaims expired leases."""

    def __init__(
        self,
        backlog_dir: Path,
        repo_root: Path | None = None,
        now: datetime.datetime | None = None,
    ):
        self.backlog_dir = backlog_dir.resolve()
        self.repo_root = (repo_root or self.backlog_dir.parent.parent).resolve()
        self.now = now or datetime.datetime.now(tz=datetime.timezone.utc)
        self.queue = BacklogQueue(self.backlog_dir)

    def _find_worktree_dir(self, task: Task) -> Path | None:
        if not self.repo_root:
            return None
        wt_parent = self.repo_root / ".worktrees"
        if not wt_parent.exists():
            return None
        num_str = task.canonical_id.split("-")[-1].lstrip("0") or "0"
        cand_dirs = [
            wt_parent / f"task-{task.id}",
            wt_parent / f"task-{num_str}",
            wt_parent / f"task-{num_str.zfill(4)}",
            wt_parent / f"task-{task.canonical_id.lower().replace('task-', '')}",
        ]
        return next((d for d in cand_dirs if d.exists() and d.is_dir()), None)

    def _get_heartbeat_time(self, task: Task, wt_dir: Path | None) -> tuple[datetime.datetime | None, str]:
        for attr in ("heartbeat_at", "heartbeat"):
            dt = _parse_iso_time(getattr(task, attr, None))
            if dt:
                return dt, "task frontmatter heartbeat"

        if wt_dir and wt_dir.exists() and wt_dir.is_dir():
            for name in (".heartbeat", ".specops-heartbeat", "heartbeat.json"):
                f = wt_dir / name
                if f.is_file():
                    try:
                        content = f.read_text(encoding="utf-8").strip()
                        if content.startswith("{"):
                            data = json.loads(content)
                            raw = data.get("heartbeat") or data.get("timestamp") or data.get("heartbeat_at")
                            dt = _parse_iso_time(raw)
                            if dt:
                                return dt, f"worktree {name}"
                        dt = _parse_iso_time(content)
                        if dt:
                            return dt, f"worktree {name}"
                    except Exception:
                        pass
        return None, ""

    def _get_worktree_git_time(self, wt_dir: Path | None) -> tuple[datetime.datetime | None, str]:
        if wt_dir and wt_dir.exists() and wt_dir.is_dir():
            try:
                res = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=wt_dir, capture_output=True, text=True, check=False)
                if res.returncode == 0 and res.stdout.strip().isdigit():
                    return datetime.datetime.fromtimestamp(int(res.stdout.strip()), tz=datetime.timezone.utc), "worktree git commit"
            except Exception:
                pass
        return None, ""

    def get_last_active_time(self, task: Task) -> tuple[datetime.datetime, str, str]:
        """Resolves most recent activity timestamp across heartbeat, git commits, claim time, and mtime."""
        wt_dir = self._find_worktree_dir(task)
        hb_dt, hb_src = self._get_heartbeat_time(task, wt_dir)
        hb_str = hb_dt.isoformat() if hb_dt else ""

        candidates: list[tuple[datetime.datetime, str]] = []
        if hb_dt:
            candidates.append((hb_dt, hb_src))

        git_dt, git_src = self._get_worktree_git_time(wt_dir)
        if git_dt:
            candidates.append((git_dt, git_src))

        for attr in ("claimed_at", "timestamp"):
            dt = _parse_iso_time(getattr(task, attr, None))
            if dt:
                candidates.append((dt, f"frontmatter {attr}"))

        if not candidates and task.file_path.exists():
            dt = datetime.datetime.fromtimestamp(task.file_path.stat().st_mtime, tz=datetime.timezone.utc)
            candidates.append((dt, "task file mtime"))

        if not candidates:
            return self.now, "fallback now", hb_str

        candidates.sort(key=lambda c: c[0])
        latest_dt, source = candidates[-1]
        return latest_dt, source, hb_str

    def evaluate_task_claim(self, task: Task, timeout_hours: float = 4.0) -> tuple[bool, StalledClaimInfo]:
        wt_dir = self._find_worktree_dir(task)
        rel_wt = str(wt_dir.relative_to(self.repo_root)) if wt_dir and wt_dir.is_relative_to(self.repo_root) else ""

        last_active, source, hb_str = self.get_last_active_time(task)
        elapsed_seconds = 0.0 if last_active > self.now else (self.now - last_active).total_seconds()
        inactive_hours = elapsed_seconds / 3600.0
        is_stalled = inactive_hours >= timeout_hours

        claim_info = StalledClaimInfo(
            task_id=task.canonical_id,
            title=task.title,
            claimed_by=task.claimed_by or "spec-ops-worker",
            claimed_at=getattr(task, "claimed_at", "") or getattr(task, "timestamp", ""),
            heartbeat_at=hb_str,
            inactive_hours=inactive_hours,
            worktree_dir=rel_wt,
            status="Stalled" if is_stalled else "Active",
            last_activity_source=source,
        )
        return is_stalled, claim_info

    def reclaim(self, timeout_hours: float = 4.0, dry_run: bool = False) -> StalledClaimReclamationResult:
        all_tasks = self.queue.list_all_tasks()
        claimed_tasks = [
            t for t in all_tasks
            if t.file_path.parent.name != "complete"
            and t.status.lower() != "complete"
            and (t.claimed_by or t.status.lower() in ("in-progress", "active") or t.claimed_at)
        ]

        stalled_tasks: list[tuple[Task, StalledClaimInfo]] = []
        active_claims: list[StalledClaimInfo] = []

        for t in claimed_tasks:
            is_stalled, info = self.evaluate_task_claim(t, timeout_hours=timeout_hours)
            if is_stalled:
                stalled_tasks.append((t, info))
            else:
                active_claims.append(info)

        reclaimed_tasks_info: list[StalledClaimInfo] = []
        reclaimed_ids: list[str] = []
        audit_trail: list[str] = []

        if not dry_run and stalled_tasks:
            with BacklogLock(self.repo_root).acquire():
                for t, info in stalled_tasks:
                    old_worker = t.claimed_by or "unknown-worker"
                    t.claimed_by = ""
                    t.claimed_at = ""
                    t.branch = ""
                    t.status = "Refined"
                    if hasattr(t, "heartbeat_at"):
                        t.heartbeat_at = ""
                    if hasattr(t, "heartbeat"):
                        t.heartbeat = ""

                    write_task_file(t)
                    folder_name = t.file_path.parent.name if t.file_path.parent.name in ("refined", "proposed") else "refined"
                    self.queue._sync_priority_file(t, "Refined", folder_name)

                    reclaimed_tasks_info.append(info)
                    reclaimed_ids.append(t.canonical_id)
                    audit_trail.append(
                        f"Reclaimed stalled claim for {t.canonical_id} (worker: {old_worker}, inactive: {info.inactive_hours:.1f}h >= {timeout_hours}h)"
                    )
        else:
            for t, info in stalled_tasks:
                reclaimed_tasks_info.append(info)
                reclaimed_ids.append(t.canonical_id)
                prefix = "[DRY RUN] " if dry_run else ""
                audit_trail.append(
                    f"{prefix}Would reclaim stalled claim for {t.canonical_id} (worker: {info.claimed_by}, inactive: {info.inactive_hours:.1f}h >= {timeout_hours}h)"
                )

        return StalledClaimReclamationResult(
            reclaimed_count=len(reclaimed_ids),
            reclaimed_ids=reclaimed_ids,
            reclaimed_tasks=reclaimed_tasks_info,
            active_count=len(active_claims),
            active_tasks=active_claims,
            timeout_hours=timeout_hours,
            dry_run=dry_run,
            audit_trail=audit_trail,
        )


def reclaim_stalled_claims(
    config_or_path: SpecOpsConfig | Path | None = None,
    timeout_hours: float = 4.0,
    dry_run: bool = False,
    now: datetime.datetime | None = None,
) -> StalledClaimReclamationResult:
    """Frontdoor entry point for stalled claim reclamation."""
    if isinstance(config_or_path, SpecOpsConfig):
        backlog_dir = config_or_path.backlog_dir
        repo_root = config_or_path.root_dir
    elif isinstance(config_or_path, Path):
        if config_or_path.name == "backlog":
            backlog_dir = config_or_path
            repo_root = config_or_path.parent.parent
        else:
            repo_root = config_or_path
            backlog_dir = config_or_path / "docs" / "project" / "backlog"
    else:
        from ..config.loader import load_config
        cfg = load_config()
        backlog_dir = cfg.backlog_dir
        repo_root = cfg.root_dir

    reclaimer = StalledClaimReclaimer(backlog_dir=backlog_dir, repo_root=repo_root, now=now)
    return reclaimer.reclaim(timeout_hours=timeout_hours, dry_run=dry_run)
