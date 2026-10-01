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

    subprocess.run(["git", "reset", "HEAD", "--", "docs/project/backlog", "HANDOVER.md"], cwd=worktree_path, capture_output=True)

    if allowed_dirs is not None:
        for d in allowed_dirs:
            dir_path = worktree_path / d
            if dir_path.exists():
                subprocess.run(["git", "add", d], cwd=worktree_path, capture_output=True, check=True)
    else:
        subprocess.run(["git", "add", "-A"], cwd=worktree_path, capture_output=True, check=True)
        subprocess.run(["git", "reset", "HEAD", "--", "docs/project/backlog", "HANDOVER.md"], cwd=worktree_path, capture_output=True)

    diff_cached = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in diff_cached.stdout.splitlines() if line.strip()]


def has_dependency_section_changes(worktree_path: Path, base_ref: str = "HEAD") -> bool:
    """Checks whether pyproject.toml modifications touch dependency definitions."""
    diff_res = subprocess.run(
        ["git", "diff", base_ref, "--", "pyproject.toml"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if diff_res.returncode != 0 or not diff_res.stdout.strip():
        return False
    dep_headers = (
        "[project.dependencies]",
        "dependencies =",
        "[project.optional-dependencies]",
        "[dependency-groups]",
        "[build-system",
    )
    for line in diff_res.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            if any(h in stripped for h in dep_headers):
                return True
    return False


def sanitize_unauthorized_dependency_modifications(
    worktree_dir: Path | str,
    allows_dependencies: bool = False,
) -> bool:
    """Reverts accidental non-dependency modifications to pyproject.toml if unauthorized."""
    if allows_dependencies:
        return False

    worktree_path = Path(worktree_dir).resolve()
    st = subprocess.run(
        ["git", "status", "--porcelain", "--", "pyproject.toml"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if not st.stdout.strip():
        return False

    # If actual dependencies were touched, leave it dirty so preflight correctly fails
    if has_dependency_section_changes(worktree_path):
        return False

    # Only non-dependency sections (e.g. [tool.mutmut]) were touched; revert to HEAD
    subprocess.run(["git", "checkout", "HEAD", "--", "pyproject.toml"], cwd=worktree_path, capture_output=True)
    subprocess.run(["git", "reset", "HEAD", "--", "pyproject.toml"], cwd=worktree_path, capture_output=True)
    return True


def sanitize_unauthorized_lockfile_mutations(
    worktree_dir: Path | str,
    allows_dependencies: bool = False,
) -> list[str]:
    """Reverts unauthorized modifications to protected lockfiles."""
    if allows_dependencies:
        return []
    from ..security.lockfile_sentinel import inspect_lockfile_sentinel

    result = inspect_lockfile_sentinel(
        worktree_dir,
        fix=True,
        task_allows_dependencies=allows_dependencies,
    )
    return result.remediated


def prepare_guardrailed_commit(
    worktree_dir: Path | str,
    commit_msg: str,
    allowed_dirs: Sequence[str] | None = None,
    allows_dependencies: bool = False,
) -> tuple[bool, str]:
    """Sanitizes backlog modifications, stages legitimate files, and commits safely."""
    worktree_path = Path(worktree_dir).resolve()

    sanitize_backlog_modifications(worktree_path, stage_legitimate=False)
    sanitize_unauthorized_dependency_modifications(worktree_path, allows_dependencies=allows_dependencies)
    sanitize_unauthorized_lockfile_mutations(worktree_path, allows_dependencies=allows_dependencies)
    handover = worktree_path / "HANDOVER.md"
    if handover.exists():
        handover.unlink()
    staged = stage_legitimate_files(worktree_path, allowed_dirs=allowed_dirs)
    if not staged:
        return False, "No modifications staged to commit."

    res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=worktree_path, capture_output=True, text=True)
    if res.returncode != 0:
        return False, f"Git commit failed: {res.stderr.strip() or res.stdout.strip()}"

    return True, "Commit created cleanly with zero backlog modifications."
