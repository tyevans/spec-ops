"""Dynamic Worker Lease Heartbeat and Zombie Claim Auto-Reclaimer.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0012; PRD-0004; US-0081; TASK-0166.
Target Bounded Context: worker. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime
import errno
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any

from ..backlog.queue import BacklogQueue, write_task_file
from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..core.parser import extract_frontmatter


def is_pid_alive(pid: int) -> bool:
    """Checks whether a given host operating system process ID is actively running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as err:
        return err.errno != errno.ESRCH


def parse_utc_timestamp(val: Any) -> datetime.datetime:
    """Safely converts string or datetime object to UTC datetime."""
    if isinstance(val, datetime.datetime):
        return val.replace(tzinfo=datetime.timezone.utc) if val.tzinfo is None else val.astimezone(datetime.timezone.utc)
    if isinstance(val, (int, float)):
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
    val_str = str(val).strip()
    try:
        return datetime.datetime.fromtimestamp(float(val_str), tz=datetime.timezone.utc)
    except ValueError:
        pass
    try:
        dt = datetime.datetime.fromisoformat(val_str)
        return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt.astimezone(datetime.timezone.utc)
    except ValueError:
        pass
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", val_str)
    if m:
        return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc)


@dataclass
class WorkerLease:
    """Cryptographic lease granted to an active worker for a claimed backlog task."""

    lease_token: str
    task_id: str
    worker_id: str
    pid: int
    created_at: str
    last_heartbeat: str
    expires_at: str
    ttl_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerLease:
        return cls(
            lease_token=data.get("lease_token", ""),
            task_id=data.get("task_id", ""),
            worker_id=data.get("worker_id", "spec-ops-worker"),
            pid=int(data.get("pid", 0)),
            created_at=data.get("created_at", ""),
            last_heartbeat=data.get("last_heartbeat", ""),
            expires_at=data.get("expires_at", ""),
            ttl_seconds=int(data.get("ttl_seconds", 300)),
            metadata=data.get("metadata", {}),
        )


class WorkerLeaseManager:
    """Manages process lease tokens, liveness heartbeats, and zombie claim reclamation."""

    def __init__(self, root_dir: Path | None = None, default_ttl_seconds: int = 300) -> None:
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.default_ttl_seconds = default_ttl_seconds
        self.leases_dir = self.root_dir / ".specops" / "worker_leases"

    def _clean_id(self, task_id: str) -> str:
        num = re.search(r"\d+", task_id)
        return f"TASK-{int(num.group(0)):04d}" if num else task_id.upper()

    def _lease_file(self, task_id: str) -> Path:
        cid = self._clean_id(task_id).lower()
        return self.leases_dir / f"{cid}.json"

    def create_lease(
        self,
        task_id: str,
        worker_id: str = "spec-ops-worker",
        pid: int | None = None,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerLease:
        """Assigns a new cryptographic lease token for a claimed task."""
        cid = self._clean_id(task_id)
        ttl = ttl_seconds or self.default_ttl_seconds
        token = secrets.token_hex(16)
        process_pid = pid if pid is not None else os.getpid()

        now = datetime.datetime.now(datetime.timezone.utc)
        expires = now + datetime.timedelta(seconds=ttl)

        lease = WorkerLease(
            lease_token=token,
            task_id=cid,
            worker_id=worker_id,
            pid=process_pid,
            created_at=now.isoformat(),
            last_heartbeat=now.isoformat(),
            expires_at=expires.isoformat(),
            ttl_seconds=ttl,
            metadata=metadata or {},
        )

        self.leases_dir.mkdir(parents=True, exist_ok=True)
        self._lease_file(cid).write_text(json.dumps(lease.to_dict(), indent=2), encoding="utf-8")
        return lease

    def get_lease(self, task_id: str) -> WorkerLease | None:
        """Retrieves active lease object for task if it exists on disk."""
        lf = self._lease_file(task_id)
        if not lf.exists():
            return None
        try:
            data = json.loads(lf.read_text(encoding="utf-8"))
            return WorkerLease.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def list_leases(self) -> list[WorkerLease]:
        """Lists all existing worker leases across the repository."""
        if not self.leases_dir.exists():
            return []
        leases: list[WorkerLease] = []
        for p in self.leases_dir.glob("task-*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                leases.append(WorkerLease.from_dict(data))
            except (json.JSONDecodeError, OSError):
                continue
        return leases

    def record_heartbeat(
        self,
        task_id: str,
        lease_token: str | None = None,
        now: datetime.datetime | None = None,
    ) -> WorkerLease | None:
        """Updates heartbeat timestamp and extends expiry window for active worker lease."""
        lease = self.get_lease(task_id)
        if not lease:
            return None
        if lease_token and lease.lease_token != lease_token:
            raise ValueError(f"Invalid lease token for task {task_id}.")

        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        expires = current_time + datetime.timedelta(seconds=lease.ttl_seconds)

        lease.last_heartbeat = current_time.isoformat()
        lease.expires_at = expires.isoformat()

        self.leases_dir.mkdir(parents=True, exist_ok=True)
        self._lease_file(task_id).write_text(json.dumps(lease.to_dict(), indent=2), encoding="utf-8")
        return lease

    def evaluate_lease(
        self,
        lease: WorkerLease,
        now: datetime.datetime | None = None,
    ) -> tuple[bool, str]:
        """Evaluates whether lease is currently active or a dead zombie claim."""
        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        expires_time = parse_utc_timestamp(lease.expires_at)
        pid_alive = is_pid_alive(lease.pid)

        # Monotonic timestamp check
        is_expired = current_time > expires_time

        if not is_expired and pid_alive:
            return True, "Active valid lease with live process"
        if not is_expired and not pid_alive:
            return False, f"Zombie lease: unexpired window but host PID {lease.pid} terminated"
        if is_expired and not pid_alive:
            return False, f"Zombie lease: expired and host PID {lease.pid} dead"
        return False, f"Expired lease: TTL lapsed (host PID {lease.pid} still exists)"

    def revoke_lease(self, task_id: str) -> bool:
        """Safely revokes and removes lease file from disk."""
        lf = self._lease_file(task_id)
        if lf.exists():
            try:
                lf.unlink()
                return True
            except OSError:
                return False
        return False

    def reclaim_zombies(
        self,
        dry_run: bool = False,
        now: datetime.datetime | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Reclaims dead worker claims and restores tasks to refined status."""
        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        backlog_dir = self.root_dir / "docs" / "project" / "backlog"
        queue = BacklogQueue(backlog_dir)

        all_tasks = {t.canonical_id: t for t in queue.list_all_tasks()}
        reclaimed: list[dict[str, Any]] = []
        active: list[dict[str, Any]] = []

        # 1. Evaluate known leases
        leases = self.list_leases()
        evaluated_cids: set[str] = set()

        for lease in leases:
            cid = lease.task_id
            evaluated_cids.add(cid)
            is_valid, reason = self.evaluate_lease(lease, now=current_time)

            if is_valid:
                active.append({
                    "task_id": cid,
                    "worker_id": lease.worker_id,
                    "pid": lease.pid,
                    "expires_at": lease.expires_at,
                    "status": "Active",
                    "reason": reason,
                })
            else:
                task = all_tasks.get(cid)
                if not dry_run:
                    self.revoke_lease(cid)
                    if task and task.status != "Complete":
                        task.claimed_by = ""
                        task.claimed_at = ""
                        task.heartbeat_at = ""
                        task.heartbeat = ""
                        task.status = "Refined"
                        write_task_file(task)
                reclaimed.append({
                    "task_id": cid,
                    "worker_id": lease.worker_id,
                    "pid": lease.pid,
                    "expires_at": lease.expires_at,
                    "status": "Reclaimed",
                    "reason": reason,
                })

        # 2. Check claimed tasks that have no active lease record
        for cid, task in all_tasks.items():
            if cid in evaluated_cids or task.status == "Complete":
                continue
            if task.claimed_by:
                # Task is claimed without a valid lease file -> candidate zombie
                reason = "Claimed task without registered lease token"
                if not dry_run:
                    task.claimed_by = ""
                    task.claimed_at = ""
                    task.heartbeat_at = ""
                    task.heartbeat = ""
                    task.status = "Refined"
                    write_task_file(task)
                reclaimed.append({
                    "task_id": cid,
                    "worker_id": task.claimed_by or "unknown",
                    "pid": 0,
                    "expires_at": "",
                    "status": "Reclaimed",
                    "reason": reason,
                })

        return reclaimed, active
