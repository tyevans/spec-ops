"""Repository hygiene and ephemeral artifact exclusion verifications. Governed by ADR-0021."""

from __future__ import annotations

from pathlib import Path
import subprocess


def assert_handover_excluded_from_git(repo_dir: Path | str, branch: str = "") -> tuple[bool, str]:
    """Asserts that HANDOVER.md has zero commits in target branch or git history."""
    target_repo = Path(repo_dir)
    cmd = ["git", "log", "--name-only", "--oneline"]
    if branch:
        cmd.append(f"main..{branch}")
    else:
        cmd.extend(["-n", "10"])

    res = subprocess.run(cmd, cwd=target_repo, capture_output=True, text=True)
    if res.returncode == 0:
        if "HANDOVER.md" in res.stdout:
            return False, "Ephemeral handover brief 'HANDOVER.md' was committed to git."
    return True, ""
