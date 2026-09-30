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
                "--pretty=format:%h%x1f%an%x1f%ad%x1f%s%x1f%G?%x1f%B%x1e",
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

        for block in raw_output.split("\x1e"):
            block = block.strip()
            if not block:
                continue

            parts = block.split("\x1f")
            if len(parts) < 4:
                continue

            chash = parts[0]
            author = parts[1]
            date = parts[2]
            subject = parts[3]
            sig_status = parts[4].strip() if len(parts) > 4 else ""
            is_signed = sig_status in ("G", "U")
            body = parts[5] if len(parts) > 5 else ""

            pr_numbers = re.findall(r"(?:pull request\s*#|PR\s*#|#)(\d+)", subject, re.IGNORECASE)
            formatted_prs = [f"#{pr}" for pr in set(pr_numbers)]

            trailers: dict[str, str] = {}
            for line in f"{subject}\n{body}".splitlines():
                tm = re.match(r"^([A-Za-z0-9][A-Za-z0-9_-]*)\s*:\s*(.+)$", line.strip())
                if tm:
                    trailers[tm.group(1).strip()] = tm.group(2).strip()

            prov_val = ""
            for tk, tv in trailers.items():
                if tk.lower() == "provenance":
                    prov_val = tv
                    break

            matched_tasks: set[str] = set()
            for m in re.findall(r"\btask[-_ ]?(\d+)\b", subject, re.IGNORECASE):
                matched_tasks.add(f"TASK-{m.zfill(4)}")
            for tk, tv in trailers.items():
                if tk.replace("_", "-").lower() in ("specops-task", "task-id", "task", "taskid"):
                    for m in re.findall(r"(?:TASK|SPIKE)?[-_ ]?0*(\d+)", tv, re.IGNORECASE):
                        if m:
                            prefix = "SPIKE-" if "SPIKE" in tv.upper() else "TASK-"
                            matched_tasks.add(f"{prefix}{m.zfill(4)}")

            commit = CommitInfo(
                hash=chash,
                author=author,
                date=date,
                subject=subject,
                prs=formatted_prs,
                signature_status=sig_status,
                is_signed=is_signed,
                provenance=prov_val,
                trailers=trailers,
            )

            for task_id in matched_tasks:
                if task_id not in result:
                    result[task_id] = ([], [])

                commits_list, prs_list = result[task_id]
                commits_list.append(commit)
                for pr in formatted_prs:
                    if pr not in prs_list:
                        prs_list.append(pr)

        return result
