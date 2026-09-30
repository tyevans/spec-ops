"""Live autonomous worker fleet telemetry harvester and aggregation engine (TASK-0070, US-0104)."""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig


@dataclass
class WorkerTelemetryRecord:
    """Individual worker telemetry state from isolated git worktrees."""

    task_id: str
    worktree_path: str
    branch: str
    status: str
    retries: str
    current_preflight_hook: str
    elapsed_runtime: str
    memory_usage: str
    cpu_usage: str
    stalled: bool
    title: str = ""
    active_preflight_check: str = ""
    attempt: str = ""
    failure_log: str = ""
    prompt_feedback: str = ""
    rescue_cmd: str = ""
    diff: str = ""
    handover_instructions: str = ""
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Converts record to structured telemetry dictionary."""
        tid = self.task_id
        return {
            "task_id": tid,
            "id": tid,
            "worktree_path": self.worktree_path,
            "worktree_dir": self.worktree_path,
            "branch": self.branch,
            "status": self.status,
            "retries": self.retries,
            "attempt": self.attempt or self.retries,
            "current_preflight_hook": self.current_preflight_hook,
            "active_preflight_check": self.active_preflight_check or self.current_preflight_hook,
            "elapsed_runtime": self.elapsed_runtime,
            "elapsed_seconds": self.elapsed_seconds,
            "memory_usage": self.memory_usage,
            "memory_mb": self.memory_mb,
            "cpu_usage": self.cpu_usage,
            "cpu_percent": self.cpu_percent,
            "stalled": self.stalled,
            "title": self.title,
            "task_title": self.title,
            "failure_log": self.failure_log,
            "prompt_feedback": self.prompt_feedback,
            "rescue_cmd": self.rescue_cmd or f"spec-ops rescue {tid}",
            "diff": self.diff,
            "handover_instructions": self.handover_instructions,
        }


def classify_worker_status(record: dict[str, Any]) -> str:
    """Classifies a worker into one of four mutually exclusive partitions:
    'completed', 'rescued', 'stalled', or 'active'.
    """
    raw_status = str(record.get("status", "")).strip().lower()

    if bool(record.get("completed", False)) or raw_status in ("complete", "completed", "done", "shipped"):
        return "completed"

    if bool(record.get("rescued", False)) or raw_status in (
        "rescued",
        "rescue_in_progress",
        "human_takeover",
        "taken_over",
    ):
        return "rescued"

    raw_attempt = str(record.get("attempt", "")).strip()
    raw_retries = str(record.get("retries", "")).strip()
    if (
        bool(record.get("stalled", False))
        or raw_status in ("stalled", "stalled: human takeover required", "failed", "deadlocked")
        or raw_attempt.startswith("3/3")
        or raw_retries.startswith("3/3")
    ):
        return "stalled"

    return "active"


def aggregate_fleet_telemetry(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregates worker fleet telemetry records into partition metrics and health stats.

    Invariant (ADR-0009):
    metrics['total'] == metrics['active'] + metrics['stalled'] + metrics['rescued'] + metrics['completed']
    """
    total = len(records)
    active_count = 0
    stalled_count = 0
    rescued_count = 0
    completed_count = 0
    stalled_tasks: list[str] = []
    total_memory_mb: float = 0.0
    total_cpu_percent: float = 0.0

    for r in records:
        cat = classify_worker_status(r)
        if cat == "completed":
            completed_count += 1
        elif cat == "rescued":
            rescued_count += 1
        elif cat == "stalled":
            stalled_count += 1
            tid = str(r.get("task_id") or r.get("id") or "").strip()
            if tid:
                stalled_tasks.append(tid)
        else:
            active_count += 1

        mem = r.get("memory_mb")
        if isinstance(mem, (int, float)) and mem > 0:
            total_memory_mb += float(mem)

        cpu = r.get("cpu_percent")
        if isinstance(cpu, (int, float)) and cpu > 0:
            total_cpu_percent += float(cpu)

    partition_sum = active_count + stalled_count + rescued_count + completed_count
    partition_valid = bool(partition_sum == total)

    avg_cpu = round(total_cpu_percent / total, 2) if total > 0 else 0.0

    return {
        "total": total,
        "active": active_count,
        "stalled": stalled_count,
        "rescued": rescued_count,
        "completed": completed_count,
        "partition_valid": partition_valid,
        "stalled_tasks": stalled_tasks,
        "total_memory_mb": round(total_memory_mb, 2),
        "avg_cpu_percent": avg_cpu,
        "records": records,
    }


def format_elapsed_runtime(seconds: float | int | None) -> str:
    """Formats elapsed seconds into human-readable duration string."""
    if seconds is None or seconds <= 0:
        return "0s"
    s = int(seconds)
    minutes = s // 60
    rem = s % 60
    if minutes > 0:
        return f"{minutes}m {rem}s"
    return f"{rem}s"


def format_memory_mb(mb: float | int | None) -> str:
    """Formats megabytes into human-readable string."""
    if mb is None or mb <= 0:
        return "0 MB"
    if mb >= 1024:
        return f"{round(mb / 1024.0, 1)} GB"
    return f"{round(mb, 1)} MB"


def format_cpu_percent(cpu: float | int | None) -> str:
    """Formats CPU percentage into human-readable string."""
    if cpu is None or cpu <= 0:
        return "0.0%"
    return f"{round(cpu, 1)}%"


def _load_backlog_titles(config: SpecOpsConfig) -> dict[str, str]:
    """Extracts task titles from project backlog for worktree enrichment."""
    task_titles: dict[str, str] = {}
    backlog_dir = getattr(config, "backlog_dir", None) or (config.root_dir / "docs" / "project" / "backlog")
    if not backlog_dir.exists():
        return task_titles

    for f in backlog_dir.rglob("*.md"):
        if f.name in ("PRIORITY.md", "ROADMAP.md", "README.md"):
            continue
        try:
            head = f.read_text(encoding="utf-8", errors="ignore")[:600]
            m_id = re.search(r"id:\s*['\"]?(\d+)['\"]?", head)
            m_title = re.search(r"title:\s*['\"]?([^'\"\n]+)['\"]?", head)
            if m_id and m_title:
                canon = f"TASK-{m_id.group(1).zfill(4)}"
                task_titles[canon] = m_title.group(1).strip()
        except Exception:
            pass
    return task_titles


def harvest_fleet_telemetry(config: SpecOpsConfig) -> list[dict[str, Any]]:
    """Harvests active worker telemetry from isolated git worktrees."""
    worktrees_parent = config.root_dir / ".worktrees"
    if not worktrees_parent.exists():
        return []

    task_titles = _load_backlog_titles(config)
    telemetry: list[dict[str, Any]] = []

    for p in sorted(worktrees_parent.iterdir()):
        if not p.is_dir():
            continue
        m = re.match(r"^task-(\d+)", p.name)
        if not m:
            continue

        tid_num = m.group(1).zfill(4)
        tid = f"TASK-{tid_num}"
        title = task_titles.get(tid, "")

        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=p,
            capture_output=True,
            text=True,
        )
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 and branch_res.stdout.strip() else f"feat/task-{tid_num}"

        diff_text = ""
        try:
            dres = subprocess.run(["git", "diff", "HEAD~1"], cwd=p, capture_output=True, text=True)
            if dres.returncode == 0 and dres.stdout.strip():
                diff_text = dres.stdout
            else:
                dres2 = subprocess.run(["git", "diff"], cwd=p, capture_output=True, text=True)
                if dres2.returncode == 0:
                    diff_text = dres2.stdout
        except Exception:
            pass

        worker_json = p / ".specops" / "worker.json"
        telemetry_json = p / ".telemetry.json"
        prompt_file = p / ".task-prompt.md"

        status = "Executing"
        attempt = "1/3"
        active_check = "uv run pytest"
        failure_log = ""
        prompt_feedback = ""
        stalled = False
        memory_mb = 128.0
        cpu_percent = 12.0
        elapsed_seconds = 0.0

        if worker_json.exists():
            try:
                wdata = json.loads(worker_json.read_text(encoding="utf-8"))
                status = wdata.get("status", status)
                attempt = str(wdata.get("attempt") or wdata.get("retries") or attempt)
                active_check = wdata.get("active_preflight_check") or wdata.get("current_preflight_hook") or active_check
                stalled = bool(wdata.get("stalled", False))
                failure_log = wdata.get("failure_log", "")
                title = wdata.get("title") or wdata.get("task_title") or title
                memory_mb = float(wdata.get("memory_mb", memory_mb))
                cpu_percent = float(wdata.get("cpu_percent", cpu_percent))
                elapsed_seconds = float(wdata.get("elapsed_seconds", elapsed_seconds))
            except Exception:
                pass
        elif telemetry_json.exists():
            try:
                tdata = json.loads(telemetry_json.read_text(encoding="utf-8"))
                status = tdata.get("status", status)
                attempt = str(tdata.get("attempt") or tdata.get("retries") or attempt)
                active_check = tdata.get("active_preflight_check") or tdata.get("current_preflight_hook") or active_check
                stalled = bool(tdata.get("stalled", False))
                failure_log = tdata.get("failure_log", "")
                title = tdata.get("title") or tdata.get("task_title") or title
                memory_mb = float(tdata.get("memory_mb", memory_mb))
                cpu_percent = float(tdata.get("cpu_percent", cpu_percent))
                elapsed_seconds = float(tdata.get("elapsed_seconds", elapsed_seconds))
            except Exception:
                pass
        if prompt_file.exists():
            text = prompt_file.read_text(encoding="utf-8", errors="ignore")
            prompt_feedback = text

            if not failure_log:
                if "## Preflight Failure Feedback" in text:
                    failure_log = text.split("## Preflight Failure Feedback")[-1].strip()
                elif "## Architectural Review Feedback" in text:
                    failure_log = text.split("## Architectural Review Feedback")[-1].strip()

            if not worker_json.exists() and not telemetry_json.exists():
                att_match = re.search(r"\(Attempt\s+(\d+)\)", text, re.IGNORECASE)
                if att_match:
                    att_num = int(att_match.group(1))
                    attempt = f"{att_num}/3"
                    if att_num >= 3:
                        stalled = True
                        status = "Stalled: Human Takeover Required"
                    elif att_num > 1:
                        status = "Self-Healing"
                elif "stalled" in text.lower():
                    stalled = True
                    status = "Stalled: Human Takeover Required"
                    attempt = "3/3"

                if "file limit" in text.lower() or "file length" in text.lower():
                    active_check = "Fixing file limit"
                elif "spec-ops health" in text.lower():
                    active_check = "spec-ops health"
                elif "pytest" in text.lower():
                    active_check = "uv run pytest"

        if elapsed_seconds <= 0.0:
            try:
                mtime = prompt_file.stat().st_mtime if prompt_file.exists() else p.stat().st_mtime
                elapsed_seconds = max(0.0, time.time() - mtime)
            except Exception:
                elapsed_seconds = 0.0

        if stalled or status == "Stalled" or attempt.startswith("3/3"):
            stalled = True
            status = "Stalled: Human Takeover Required"

        rel_path = f".worktrees/{p.name}"
        record = WorkerTelemetryRecord(
            task_id=tid,
            title=title,
            worktree_path=rel_path,
            branch=branch,
            status=status,
            retries=attempt,
            attempt=attempt,
            current_preflight_hook=active_check,
            active_preflight_check=active_check,
            elapsed_runtime=format_elapsed_runtime(elapsed_seconds),
            elapsed_seconds=elapsed_seconds,
            memory_usage=format_memory_mb(memory_mb),
            memory_mb=memory_mb,
            cpu_usage=format_cpu_percent(cpu_percent),
            cpu_percent=cpu_percent,
            stalled=stalled,
            failure_log=failure_log,
            prompt_feedback=prompt_feedback,
            rescue_cmd=f"spec-ops rescue {tid}",
            diff=diff_text,
            handover_instructions=(
                f"1. Run CLI command: spec-ops rescue {tid}\n"
                f"2. Inspect preflight failure feedback and git diff\n"
                f"3. Complete and merge: spec-ops rescue {tid} --complete"
            ),
        )
        telemetry.append(record.to_dict())

    return telemetry
