"""Git metadata harvester for linking commits and PRs to backlog tasks."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .models import CommitInfo


class GitMetadataHarvester:
    """Harvests Git commits and Pull Request tags associated with backlog tasks."""

    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir).resolve()

    def harvest(self) -> dict[str, tuple[list[CommitInfo], list[str]]]:
        """Harvest commits and PR numbers mapped by canonical task ID (e.g. 'TASK-0041')."""
        result: dict[str, tuple[list[CommitInfo], list[str]]] = {}

        if not shutil.which("git"):
            return result

        git_dir = self.root_dir / ".git"
        if not git_dir.exists() and not (self.root_dir / ".git").is_file():
            return result

        try:
            cmd = [
                "git",
                "log",
                "--pretty=format:%h%x09%an%x09%ad%x09%s",
                "--date=short",
                "-n",
                "600",
            ]
            raw_output = subprocess.check_output(
                cmd,
                cwd=str(self.root_dir),
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return result

        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 4:
                continue

            chash, author, date, subject = parts[0], parts[1], parts[2], parts[3]

            pr_numbers = re.findall(r"(?:pull request\s*#|PR\s*#|#)(\d+)", subject, re.IGNORECASE)
            formatted_prs = [f"#{pr}" for pr in set(pr_numbers)]

            task_matches = re.findall(r"\btask[-_ ]?(\d+)\b", subject, re.IGNORECASE)
            for m in set(task_matches):
                task_id = f"TASK-{m.zfill(4)}"
                commit = CommitInfo(
                    hash=chash,
                    author=author,
                    date=date,
                    subject=subject,
                    prs=formatted_prs,
                )

                if task_id not in result:
                    result[task_id] = ([], [])

                commits_list, prs_list = result[task_id]
                commits_list.append(commit)
                for pr in formatted_prs:
                    if pr not in prs_list:
                        prs_list.append(pr)

        return result
