"""Proactive worktree disk quota monitor and orphan worktree pruning daemon."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from .lifecycle import get_worktree_branch, is_worktree_dirty, prune_git_worktrees
from .prune import calculate_directory_size, format_bytes

DEFAULT_QUOTA_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB


@dataclass
class WorktreeQuotaInfo:
    """Represents storage and lifecycle state for an isolated git worktree."""

    worktree_name: str
    worktree_dir: Path
    task_id: str
    task_status: str
    size_bytes: int
    last_modified: datetime
    last_modified_str: str
    is_dirty: bool
    is_merged: bool
    has_failure_history: bool
    branch: str
    is_eligible: bool
    skip_reason: str = ""


@dataclass
class QuotaAuditReport:
    """Summary of worktree storage consumption and quota threshold status."""

    worktrees: list[WorktreeQuotaInfo]
    total_size_bytes: int
    threshold_bytes: int
    threshold_exceeded: bool
    candidates_count: int
    reclaimable_bytes: int
    warning_message: str = ""


def parse_duration(duration_str: str) -> timedelta:
    """Parses duration strings like '7d', '24h', '1d', '30m', '3600s' into timedelta."""
    m = re.match(r"^(\d+)\s*([a-zA-Z]+)?$", duration_str.strip())
    if not m:
        raise ValueError(f"Invalid duration format: '{duration_str}'. Expected e.g. '7d', '24h', '1d', '30m'.")
    val, unit = int(m.group(1)), (m.group(2) or "d").lower()
    units: dict[str, str] = {
        "d": "days", "day": "days", "days": "days",
        "h": "hours", "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
        "m": "minutes", "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
        "s": "seconds", "sec": "seconds", "secs": "seconds", "second": "seconds", "seconds": "seconds",
        "w": "weeks", "wk": "weeks", "week": "weeks", "weeks": "weeks",
    }
    if unit not in units:
        raise ValueError(f"Unsupported duration unit '{unit}' in '{duration_str}'.")
    return timedelta(**{units[unit]: val})


def parse_threshold_bytes(threshold: str | int | None) -> int:
    """Parses threshold string (e.g. '5GB', '500MB') or integer into byte count."""
    if threshold is None:
        return DEFAULT_QUOTA_BYTES
    if isinstance(threshold, int):
        return threshold
    m = re.match(r"^([\d.]+)\s*([A-Z]+)?$", threshold.strip().upper())
    if not m:
        return DEFAULT_QUOTA_BYTES
    val, unit = float(m.group(1)), m.group(2) or "B"
    scales = {"GB": 1024**3, "G": 1024**3, "MB": 1024**2, "M": 1024**2, "KB": 1024, "K": 1024, "B": 1}
    return int(val * scales.get(unit, 1))


def get_worktree_mtime(worktree_dir: Path) -> datetime:
    """Finds latest modification datetime across files in a worktree directory."""
    latest = worktree_dir.stat().st_mtime
    try:
        for root, dirs, files in os.walk(worktree_dir):
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                fp = Path(root) / f
                try:
                    if not fp.is_symlink():
                        m = fp.stat().st_mtime
                        if m > latest:
                            latest = m
                except OSError:
                    pass
    except OSError:
        pass
    return datetime.fromtimestamp(latest, tz=timezone.utc)


def find_task_status_and_history(backlog_dir: Path, task_id: str) -> tuple[str, bool]:
    """Resolves task lifecycle status and verifies presence of failure memory."""
    clean_num = task_id.upper().replace("TASK-", "").lstrip("0") or "0"
    num_pattern = f"*{clean_num.zfill(4)}*"

    for folder, status_name in (("complete", "Complete"), ("refined", "Refined"), ("proposed", "Proposed")):
        target_dir = backlog_dir / folder
        if not target_dir.exists():
            continue
        for p in target_dir.glob(num_pattern):
            if p.is_file():
                has_fail = False
                try:
                    content = p.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        end_idx = content.find("\n---", 3)
                        if end_idx != -1:
                            data = yaml.safe_load(content[3:end_idx]) or {}
                            hist = data.get("failure_history") if isinstance(data, dict) else None
                            has_fail = isinstance(hist, list) and len(hist) > 0
                except Exception:
                    pass
                return status_name, has_fail
    return "Orphan", False


def check_worktree_merged_to_main(repo_root: Path, worktree_dir: Path, branch: str) -> bool:
    """Verifies whether changes on a worktree or branch have been merged into main."""
    chk_main = subprocess.run(["git", "rev-parse", "--verify", "refs/heads/main"], cwd=repo_root, capture_output=True)
    base_ref = "main" if chk_main.returncode == 0 else "master"

    if worktree_dir.exists() and worktree_dir.is_dir():
        rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=worktree_dir, capture_output=True, text=True)
        if rev.returncode == 0:
            mb = subprocess.run(
                ["git", "merge-base", "--is-ancestor", rev.stdout.strip(), base_ref],
                cwd=repo_root,
                capture_output=True,
            )
            if mb.returncode == 0:
                return True

    if branch:
        chk_b = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo_root)
        if chk_b.returncode == 0:
            mb = subprocess.run(
                ["git", "merge-base", "--is-ancestor", f"refs/heads/{branch}", base_ref],
                cwd=repo_root,
                capture_output=True,
            )
            if mb.returncode == 0:
                return True

    return False


def evaluate_prune_eligibility(
    info: WorktreeQuotaInfo,
    cutoff_time: datetime | None = None,
    force: bool = False,
) -> tuple[bool, str]:
    """Evaluates whether a worktree is safe to prune under ADR-0005 and ADR-0009 invariants."""
    if cutoff_time is not None and info.last_modified > cutoff_time:
        return False, f"Modified more recently than cutoff ({info.last_modified_str})"

    norm_status = info.task_status.strip().capitalize()
    if norm_status in ("Refined", "Proposed", "Active", "Inprogress", "In-progress"):
        if info.is_dirty:
            return False, (
                f"Worktree is dirty with active human modifications. "
                f"Run 'spec-ops rescue reset {info.task_id}' to force discard."
            )
        return False, f"Active uncompleted task ({info.task_status})"

    if info.is_dirty and not force:
        return False, (
            f"Worktree is dirty with active human modifications. "
            f"Run 'spec-ops rescue reset {info.task_id}' to force discard."
        )

    if norm_status != "Complete" and not (info.is_merged or info.has_failure_history) and not force:
        return False, "Worktree has unmerged changes and no failure memory. Use --force to prune."

    return True, ""


def inspect_worktree(
    repo_root: Path,
    backlog_dir: Path,
    worktree_path: Path,
    cutoff_time: datetime | None = None,
    force: bool = False,
) -> WorktreeQuotaInfo:
    """Inspects an individual worktree directory and extracts complete audit metadata."""
    name = worktree_path.name
    m = re.match(r"^task-(\d+)", name, re.IGNORECASE)
    tid_num = m.group(1).zfill(4) if m else "0000"
    task_id = f"TASK-{tid_num}" if m else name.upper()

    dirty = is_worktree_dirty(worktree_path)
    branch = get_worktree_branch(worktree_path) or f"feat/{task_id}"
    status, has_fail = find_task_status_and_history(backlog_dir, task_id)
    size = calculate_directory_size(worktree_path)
    mtime = get_worktree_mtime(worktree_path)
    merged = check_worktree_merged_to_main(repo_root, worktree_path, branch)

    info = WorktreeQuotaInfo(
        worktree_name=name,
        worktree_dir=worktree_path,
        task_id=task_id,
        task_status=status,
        size_bytes=size,
        last_modified=mtime,
        last_modified_str=mtime.strftime("%Y-%m-%d %H:%M"),
        is_dirty=dirty,
        is_merged=merged,
        has_failure_history=has_fail,
        branch=branch,
        is_eligible=False,
    )
    eligible, reason = evaluate_prune_eligibility(info, cutoff_time=cutoff_time, force=force)
    info.is_eligible = eligible
    info.skip_reason = reason
    return info


def audit_worktree_quotas(
    repo_root: Path,
    backlog_dir: Path,
    threshold_bytes: int = DEFAULT_QUOTA_BYTES,
) -> QuotaAuditReport:
    """Audits storage consumption across all worktrees in .worktrees/ and checks quota limits."""
    worktrees_parent = repo_root / ".worktrees"
    items: list[WorktreeQuotaInfo] = []

    if worktrees_parent.exists():
        for p in sorted(worktrees_parent.iterdir()):
            if p.is_dir():
                items.append(inspect_worktree(repo_root, backlog_dir, p))

    total_size = sum(i.size_bytes for i in items)
    exceeded = total_size > threshold_bytes
    candidates = [i for i in items if i.is_eligible]
    reclaimable = sum(c.size_bytes for c in candidates)

    warn_msg = ""
    if exceeded:
        warn_msg = (
            f"⚠️  PROACTIVE WARNING: Aggregate worktree storage ({format_bytes(total_size)}) "
            f"exceeds configured quota threshold ({format_bytes(threshold_bytes)})! "
            f"Run 'spec-ops rescue prune' to reclaim disk space."
        )

    return QuotaAuditReport(
        worktrees=items,
        total_size_bytes=total_size,
        threshold_bytes=threshold_bytes,
        threshold_exceeded=exceeded,
        candidates_count=len(candidates),
        reclaimable_bytes=reclaimable,
        warning_message=warn_msg,
    )


def format_quota_table(report: QuotaAuditReport) -> str:
    """Renders a tabular summary displaying directory sizes, statuses, and pruning candidates."""
    lines = [
        "Worktree Disk Quota & Storage Consumption:",
        f"{'Worktree':<26} {'Task ID':<14} {'Status':<12} {'Size':<12} {'Last Modified':<18} {'Eligible for Pruning'}",
        "-" * 98,
    ]
    for wt in report.worktrees:
        rel_dir = f".worktrees/{wt.worktree_name}"
        elig_str = "Yes (Candidate)" if wt.is_eligible else f"No ({wt.skip_reason or 'Protected'})"
        lines.append(
            f"{rel_dir:<26} {wt.task_id:<14} {wt.task_status:<12} {format_bytes(wt.size_bytes):<12} {wt.last_modified_str:<18} {elig_str}"
        )
    lines.append("-" * 98)
    lines.append(
        f"Total Worktree Storage: {format_bytes(report.total_size_bytes)} (Quota Threshold: {format_bytes(report.threshold_bytes)})"
    )
    lines.append(
        f"Candidates eligible for safe pruning: {report.candidates_count} "
        f"(Estimated reclaimable: {format_bytes(report.reclaimable_bytes)})"
    )
    if report.warning_message:
        lines.append("")
        lines.append(report.warning_message)
    return "\n".join(lines)


def run_prune(
    repo_root: Path,
    backlog_dir: Path,
    older_than: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[list[WorktreeQuotaInfo], list[WorktreeQuotaInfo], list[str]]:
    """Prunes eligible orphan/completed worktrees or previews disk reclamation in dry-run mode."""
    cutoff_time: datetime | None = None
    if older_than:
        duration = parse_duration(older_than)
        cutoff_time = datetime.now(timezone.utc) - duration

    worktrees_parent = repo_root / ".worktrees"
    pruned: list[WorktreeQuotaInfo] = []
    skipped: list[WorktreeQuotaInfo] = []
    warnings: list[str] = []

    if not worktrees_parent.exists():
        return pruned, skipped, warnings

    for p in sorted(worktrees_parent.iterdir()):
        if not p.is_dir():
            continue
        info = inspect_worktree(repo_root, backlog_dir, p, cutoff_time=cutoff_time, force=force)
        rel_dir = f".worktrees/{p.name}"

        if not info.is_eligible:
            skipped.append(info)
            if info.is_dirty:
                warnings.append(
                    f"Skipping {rel_dir}: Worktree is dirty with active human modifications. "
                    f"Run 'spec-ops rescue reset {info.task_id}' to force discard."
                )
            continue

        pruned.append(info)
        if dry_run:
            continue

        print(f"Identified {rel_dir} as an orphaned completed worktree.")
        subprocess.run(["git", "worktree", "remove", "--force", str(p)], cwd=repo_root, capture_output=True)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

        branches_to_try = {info.branch, f"feat/{info.task_id}", f"feat/{p.name}"}
        for b in branches_to_try:
            chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{b}"], cwd=repo_root)
            if chk.returncode == 0:
                subprocess.run(["git", "branch", "-D", b], cwd=repo_root, capture_output=True)

        prune_git_worktrees(repo_root)

    if not dry_run:
        prune_git_worktrees(repo_root)

    return pruned, skipped, warnings
