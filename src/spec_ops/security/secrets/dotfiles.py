"""Detection of sensitive dotfiles and untracked private keys."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .models import DotfileViolation
from .patterns import is_sensitive_dotfile

EXCLUDED_SCAN_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "site",
    ".pytest_cache",
    ".hypothesis",
    "__pycache__",
    ".worktrees",
})


def scan_dotfiles(root_dir: Path) -> list[DotfileViolation]:
    """Identifies sensitive dotfiles and private keys that are not ignored by .gitignore."""
    violations: list[DotfileViolation] = []
    is_git_repo = (root_dir / ".git").exists()

    for p in root_dir.rglob("*"):
        if not p.is_file() or any(part in EXCLUDED_SCAN_DIRS for part in p.parts):
            continue
        if not is_sensitive_dotfile(p.name):
            continue

        rel_path = p.relative_to(root_dir)

        if is_git_repo:
            chk = subprocess.run(
                ["git", "check-ignore", "-q", str(rel_path)],
                cwd=root_dir,
                capture_output=True,
            )
            if chk.returncode != 0:
                instructions = f"Action: Add '{rel_path}' to .gitignore and remove it from git staging."
                violations.append(DotfileViolation(file_path=str(rel_path), action_instructions=instructions))
            else:
                tracked = subprocess.run(
                    ["git", "ls-files", str(rel_path)],
                    cwd=root_dir,
                    capture_output=True,
                    text=True,
                )
                if tracked.stdout.strip():
                    instructions = f"Action: Remove tracked '{rel_path}' from git staging."
                    violations.append(DotfileViolation(file_path=str(rel_path), action_instructions=instructions))
        else:
            gitignore_path = root_dir / ".gitignore"
            ignored = False
            if gitignore_path.exists():
                gi_content = gitignore_path.read_text(encoding="utf-8")
                if p.name in gi_content:
                    ignored = True
            if not ignored:
                instructions = f"Action: Add '{rel_path}' to .gitignore."
                violations.append(DotfileViolation(file_path=str(rel_path), action_instructions=instructions))

    return violations
