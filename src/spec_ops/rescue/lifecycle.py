"""Git worktree lifecycle management and collision recovery."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def is_worktree_dirty(worktree_dir: Path) -> bool:
    """Checks whether a worktree contains uncommitted changes or untracked files."""
    if not worktree_dir.exists() or not worktree_dir.is_dir():
        return False
    git_file = worktree_dir / ".git"
    if not git_file.exists():
        return False
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return False
    return bool(res.stdout.strip())


def get_worktree_branch(worktree_dir: Path) -> str:
    """Detects current branch name for a given worktree directory."""
    if not worktree_dir.exists() or not worktree_dir.is_dir():
        return ""
    res = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return ""
    branch = res.stdout.strip()
    return "" if branch == "HEAD" else branch


def prune_git_worktrees(repo_root: Path) -> None:
    """Prunes stale git worktree administrative metadata."""
    subprocess.run(["git", "worktree", "prune"], cwd=repo_root, capture_output=True)


def create_worktree(
    repo_root: Path,
    branch: str,
    worktree_dir: Path,
    base_ref: str | None = None,
    check_dirty: bool = False,
) -> None:
    """Idempotently creates or resets an isolated git worktree branch.

    Inspects existing worktrees for uncommitted human rescue work before recreating.
    Prunes stale administrative records and recovers cleanly from branch collisions.
    """
    if worktree_dir.exists():
        if check_dirty and is_worktree_dirty(worktree_dir):
            raise RuntimeError(
                f"Cannot recreate worktree at {worktree_dir}: worktree contains uncommitted human rescue work."
            )
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=repo_root,
            capture_output=True,
        )
        prune_git_worktrees(repo_root)
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)
        prune_git_worktrees(repo_root)
    else:
        prune_git_worktrees(repo_root)

    # Check and delete existing branch to allow clean start from base_ref
    chk = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo_root,
    )
    target_base = base_ref
    if not target_base:
        chk_main = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/main"],
            cwd=repo_root,
        )
        target_base = "main" if chk_main.returncode == 0 else "HEAD"

    add_res = subprocess.run(
        ["git", "worktree", "add", "-B", branch, str(worktree_dir), target_base],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if add_res.returncode != 0:
        prune_git_worktrees(repo_root)
        retry_res = subprocess.run(
            ["git", "worktree", "add", "-B", branch, str(worktree_dir), target_base],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if retry_res.returncode != 0:
            err = retry_res.stderr.strip() or add_res.stderr.strip()
            raise RuntimeError(f"Failed to create worktree: {err}")

    # Propagate native git hooks to isolated worktree
    try:
        from ..scaffold.native_hooks import propagate_hooks_to_worktree

        propagate_hooks_to_worktree(repo_root, worktree_dir)
    except Exception:
        pass


def cleanup_worktree(
    repo_root: Path,
    worktree_dir: Path,
    branch: str = "",
    delete_branch: bool = False,
) -> None:
    """Removes a worktree, deletes transient branch, and purges ephemeral caches."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_dir)],
        cwd=repo_root,
        capture_output=True,
    )

    # Clean up temporary prompt files and ephemeral caches
    ephemeral_names = [
        "HANDOVER.md",
        ".task-prompt.md",
        ".task-review-prompt.md",
        ".pytest_cache",
        ".hypothesis",
        ".mutmut-cache",
    ]
    for name in ephemeral_names:
        p = worktree_dir / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)

    if worktree_dir.exists():
        shutil.rmtree(worktree_dir, ignore_errors=True)

    prune_git_worktrees(repo_root)

    if delete_branch and branch:
        subprocess.run(["git", "branch", "-D", branch], cwd=repo_root, capture_output=True)

    if worktree_dir.exists():
        raise RuntimeError(f"Worktree directory {worktree_dir} still exists on disk after teardown.")


def init_worktree_environment(repo_root: Path, worktree_dir: Path) -> list[str]:
    """Initializes workspace environment symlinks and configurations in a worktree."""
    initialized: list[str] = []
    venv_source = repo_root / ".venv"
    venv_target = worktree_dir / ".venv"
    if venv_source.exists() and not venv_target.exists():
        try:
            os.symlink(venv_source, venv_target, target_is_directory=True)
            initialized.append(".venv")
        except OSError:
            pass

    env_source = repo_root / ".env"
    env_target = worktree_dir / ".env"
    if env_source.exists() and not env_target.exists():
        try:
            os.symlink(env_source, env_target)
            initialized.append(".env")
        except OSError:
            pass

    try:
        from ..scaffold.native_hooks import propagate_hooks_to_worktree

        res = propagate_hooks_to_worktree(repo_root, worktree_dir)
        if res is not None:
            initialized.append("hooks")
    except Exception:
        pass

    return initialized
