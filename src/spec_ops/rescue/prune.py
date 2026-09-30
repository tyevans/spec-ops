"""Worktree garbage collection, orphan detection, and zero-pollution pruning."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .lifecycle import get_worktree_branch, is_worktree_dirty, prune_git_worktrees


@dataclass
class PruneCandidate:
    """Represents a worktree inspected for garbage collection."""

    task_id: str
    worktree_dir: Path
    branch: str
    size_bytes: int
    is_dirty: bool
    task_status: str | None
    is_eligible: bool
    skip_reason: str = ""


def is_prune_candidate(is_dirty: bool, task_status: str | None) -> bool:
    """Evaluates whether a worktree is eligible for safe pruning.

    Invariant (ADR-0009): Worktrees that are dirty OR assigned to active uncompleted
    tasks (Refined, Proposed, In-Progress) are NEVER eligible for pruning.
    """
    if is_dirty:
        return False
    if task_status is not None:
        normalized = task_status.strip().capitalize()
        if normalized in ("Refined", "Proposed", "Active", "Inprogress", "In-progress"):
            return False
        if normalized == "Complete":
            return True
        return False
    return True


def calculate_directory_size(dir_path: Path) -> int:
    """Calculates total size in bytes of files within directory without traversing symlinks."""
    total = 0
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    for root, _dirs, files in os.walk(dir_path):
        for f in files:
            fp = Path(root) / f
            try:
                if not fp.is_symlink():
                    total += fp.stat().st_size
            except OSError:
                pass
    return total


def format_bytes(num_bytes: int) -> str:
    """Formats byte counts into clean human-readable units."""
    if num_bytes >= 1024**3:
        return f"{num_bytes / (1024**3):.1f} GB"
    if num_bytes >= 1024**2:
        return f"{num_bytes / (1024**2):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} B"


def _find_task_status(backlog_dir: Path, task_id: str) -> str | None:
    """Determines task lifecycle state across backlog folders."""
    clean_num = task_id.upper().replace("TASK-", "").lstrip("0")
    if not clean_num:
        clean_num = "0"
    num_pattern = f"*{clean_num.zfill(4)}*"

    # 1. Complete check
    complete_dir = backlog_dir / "complete"
    if complete_dir.exists():
        for p in complete_dir.glob(num_pattern):
            if p.is_file():
                return "Complete"

    # 2. Refined check
    refined_dir = backlog_dir / "refined"
    if refined_dir.exists():
        for p in refined_dir.glob(num_pattern):
            if p.is_file():
                return "Refined"

    # 3. Proposed check
    proposed_dir = backlog_dir / "proposed"
    if proposed_dir.exists():
        for p in proposed_dir.glob(num_pattern):
            if p.is_file():
                return "Proposed"

    return None


def scan_worktree_candidates(
    repo_root: Path,
    backlog_dir: Path,
) -> tuple[list[PruneCandidate], list[str]]:
    """Scans .worktrees/ and categorizes each for safe pruning."""
    worktrees_parent = repo_root / ".worktrees"
    candidates: list[PruneCandidate] = []
    warnings: list[str] = []

    if not worktrees_parent.exists():
        return candidates, warnings

    for p in sorted(worktrees_parent.iterdir()):
        if not p.is_dir():
            continue
        m = re.match(r"^task-(\d+)", p.name, re.IGNORECASE)
        tid_num = m.group(1).zfill(4) if m else "0000"
        task_id = f"TASK-{tid_num}" if m else p.name.upper()

        dirty = is_worktree_dirty(p)
        branch = get_worktree_branch(p)
        if not branch:
            # Fall back to conventional branch naming
            branch = f"feat/{task_id}"

        status = _find_task_status(backlog_dir, task_id)
        size = calculate_directory_size(p)
        eligible = is_prune_candidate(is_dirty=dirty, task_status=status)

        skip_reason = ""
        rel_path = f".worktrees/{p.name}"
        if dirty:
            skip_reason = "dirty with active modifications"
            warnings.append(
                f"Skipping {rel_path}: Worktree is dirty with active human modifications. "
                f"Run 'spec-ops rescue reset {task_id}' to force discard."
            )
        elif not eligible:
            skip_reason = f"active uncompleted task ({status})"

        candidates.append(
            PruneCandidate(
                task_id=task_id,
                worktree_dir=p,
                branch=branch,
                size_bytes=size,
                is_dirty=dirty,
                task_status=status,
                is_eligible=eligible,
                skip_reason=skip_reason,
            )
        )

    return candidates, warnings


def prune_worktrees(
    repo_root: Path,
    backlog_dir: Path,
    dry_run: bool = False,
) -> tuple[list[PruneCandidate], list[str]]:
    """Executes zero-pollution pruning or dry-run evaluation."""
    candidates, warnings = scan_worktree_candidates(repo_root, backlog_dir)
    pruned: list[PruneCandidate] = []

    for cand in candidates:
        if not cand.is_eligible:
            continue

        pruned.append(cand)
        if dry_run:
            continue

        rel_dir = f".worktrees/{cand.worktree_dir.name}"
        print(f"Identified {rel_dir} as an orphaned completed worktree.")

        # 1. Force remove worktree
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(cand.worktree_dir)],
            cwd=repo_root,
            capture_output=True,
        )
        if cand.worktree_dir.exists():
            shutil.rmtree(cand.worktree_dir, ignore_errors=True)

        # 2. Delete branch if exists
        branches_to_try = {cand.branch, f"feat/{cand.task_id}", f"feat/{cand.worktree_dir.name}"}
        for b in branches_to_try:
            chk = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{b}"],
                cwd=repo_root,
            )
            if chk.returncode == 0:
                subprocess.run(["git", "branch", "-D", b], cwd=repo_root, capture_output=True)

        # 3. Prune git worktree records
        prune_git_worktrees(repo_root)

    if not dry_run:
        prune_git_worktrees(repo_root)

    return pruned, warnings
