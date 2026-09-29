"""Git worktree lifecycle management for autonomous workers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def create_worktree(repo_root: Path, branch: str, worktree_dir: Path) -> None:
    """Robustly creates or resets an isolated git worktree branch."""
    # 1. Force remove worktree from git tracking if already registered
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_dir)],
        cwd=repo_root,
        capture_output=True,
    )
    # 2. Prune any stale administrative records in .git/worktrees/
    subprocess.run(["git", "worktree", "prune"], cwd=repo_root, capture_output=True)

    # 3. Clean up leftover directory if git worktree remove left anything behind
    if worktree_dir.exists():
        shutil.rmtree(worktree_dir, ignore_errors=True)

    # 4. Prune again to ensure git recognizes the directory is gone
    subprocess.run(["git", "worktree", "prune"], cwd=repo_root, capture_output=True)

    # 5. Delete existing branch if it exists so we can start clean from HEAD
    chk = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo_root,
    )
    if chk.returncode == 0:
        subprocess.run(["git", "branch", "-D", branch], cwd=repo_root, capture_output=True)

    # 6. Add worktree with -B to create or reset branch cleanly from HEAD
    add_res = subprocess.run(
        ["git", "worktree", "add", "-B", branch, str(worktree_dir), "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if add_res.returncode != 0:
        subprocess.run(["git", "worktree", "prune"], cwd=repo_root, capture_output=True)
        retry_res = subprocess.run(
            ["git", "worktree", "add", "-B", branch, str(worktree_dir), "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if retry_res.returncode != 0:
            err = retry_res.stderr.strip() or add_res.stderr.strip()
            raise RuntimeError(f"Failed to create worktree: {err}")


def cleanup_worktree(
    repo_root: Path,
    worktree_dir: Path,
    branch: str,
    delete_branch: bool = False,
) -> None:
    """Removes a worktree and optionally deletes its associated branch."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_dir)],
        cwd=repo_root,
        capture_output=True,
    )
    if worktree_dir.exists():
        shutil.rmtree(worktree_dir, ignore_errors=True)
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=repo_root,
        capture_output=True,
    )
    if delete_branch:
        subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=repo_root,
            capture_output=True,
        )
