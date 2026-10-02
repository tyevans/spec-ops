"""Cryptographic git tree digest calculation. Governed by ADR-0021."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess


def compute_git_tree_digest(
    repo_root: Path | str,
    allow_uncommitted: bool = False,
) -> tuple[str, bool, list[str]]:
    """Calculates canonical SHA-256 tree digest across git-tracked repository files."""
    root = Path(repo_root).resolve()
    errors: list[str] = []

    # 1. Check for uncommitted working tree modifications
    res_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if res_status.returncode != 0:
        return "", False, [f"Failed to check git status: {res_status.stderr.strip()}"]

    has_diffs = bool(res_status.stdout.strip())
    if has_diffs and not allow_uncommitted:
        return (
            "",
            False,
            ["Repository contains uncommitted diffs or untracked changes; clean tree invariant required."],
        )

    # 2. Get list of tracked files
    res_files = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if res_files.returncode != 0:
        return "", False, [f"Failed to enumerate tracked files: {res_files.stderr.strip()}"]

    hasher = hashlib.sha256()
    lines = sorted(line.strip() for line in res_files.stdout.splitlines() if line.strip())

    for line in lines:
        parts = line.split(None, 3)
        if len(parts) == 4:
            rel_path = parts[3]
            file_path = root / rel_path
            if file_path.is_file():
                try:
                    file_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
                    hasher.update(f"{rel_path}:{file_sha}\n".encode("utf-8"))
                except OSError as e:
                    errors.append(f"Unreadable file {rel_path}: {e}")
            else:
                hasher.update(f"{rel_path}:deleted\n".encode("utf-8"))

    if errors:
        return "", False, errors

    return hasher.hexdigest(), not has_diffs, []
