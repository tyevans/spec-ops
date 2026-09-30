"""Automated backlog protection guardrails and accidental modification interception."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


def detect_backlog_modifications(
    worktree_dir: Path | str,
    backlog_path: str = "docs/project/backlog",
) -> list[str]:
    """Detects modified, staged, or untracked files under the shared backlog directory."""
    worktree_path = Path(worktree_dir).resolve()
    target_rel = backlog_path.strip("/")

    res = subprocess.run(
        ["git", "status", "--porcelain", "--", target_rel],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=True,
    )

    dirty_files: list[str] = []
    for line in res.stdout.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        path_part = line[3:].strip().strip('"')
        if " -> " in path_part:
            path_part = path_part.split(" -> ")[-1].strip().strip('"')
        if path_part.startswith(target_rel):
            dirty_files.append(path_part)

    return dirty_files


def sanitize_backlog_modifications(
    worktree_dir: Path | str,
    backlog_path: str = "docs/project/backlog",
    stage_legitimate: bool = True,
) -> list[str]:
    """Intercepts and reverts any changes in docs/project/backlog/ to protect shared state."""
    worktree_path = Path(worktree_dir).resolve()
    target_rel = backlog_path.strip("/")

    dirty = detect_backlog_modifications(worktree_path, backlog_path=target_rel)
    if dirty:
        subprocess.run(["git", "checkout", "HEAD", "--", target_rel], cwd=worktree_path, capture_output=True)
        subprocess.run(["git", "reset", "HEAD", "--", target_rel], cwd=worktree_path, capture_output=True)
        subprocess.run(["git", "clean", "-fd", "--", target_rel], cwd=worktree_path, capture_output=True)

    if stage_legitimate:
        stage_legitimate_files(worktree_path)

    return dirty


def stage_legitimate_files(
    worktree_dir: Path | str,
    allowed_dirs: Sequence[str] | None = None,
) -> list[str]:
    """Stages only functional source code and tests, keeping backlog un-staged."""
    worktree_path = Path(worktree_dir).resolve()

    subprocess.run(["git", "reset", "HEAD", "--", "docs/project/backlog"], cwd=worktree_path, capture_output=True)

    if allowed_dirs is not None:
        for d in allowed_dirs:
            dir_path = worktree_path / d
            if dir_path.exists():
                subprocess.run(["git", "add", d], cwd=worktree_path, capture_output=True, check=True)
    else:
        subprocess.run(["git", "add", "-A"], cwd=worktree_path, capture_output=True, check=True)
        subprocess.run(["git", "reset", "HEAD", "--", "docs/project/backlog"], cwd=worktree_path, capture_output=True)

    diff_cached = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in diff_cached.stdout.splitlines() if line.strip()]


def prepare_guardrailed_commit(
    worktree_dir: Path | str,
    commit_msg: str,
    allowed_dirs: Sequence[str] | None = None,
) -> tuple[bool, str]:
    """Sanitizes backlog modifications, stages legitimate files, and commits safely."""
    worktree_path = Path(worktree_dir).resolve()

    sanitize_backlog_modifications(worktree_path, stage_legitimate=False)
    staged = stage_legitimate_files(worktree_path, allowed_dirs=allowed_dirs)
    if not staged:
        return False, "No modifications staged to commit."

    res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=worktree_path, capture_output=True, text=True)
    if res.returncode != 0:
        return False, f"Git commit failed: {res.stderr.strip() or res.stdout.strip()}"

    return True, "Commit created cleanly with zero backlog modifications."
