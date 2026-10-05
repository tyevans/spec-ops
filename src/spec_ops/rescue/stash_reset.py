"""Automated worktree stash and clean reset recovery engine (US-0081, ADR-0005, ADR-0020)."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.git_worktree import resolve_repo_root
from .lifecycle import get_worktree_branch, is_worktree_dirty


@dataclass
class RescueStashMetadata:
    """Metadata describing a preserved worktree rescue stash patch archive."""

    stash_id: str
    task_id: str
    timestamp: str
    branch: str
    patch_file: str
    modified_files: list[str] = field(default_factory=list)
    diff_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializes stash metadata into a dictionary."""
        return {
            "stash_id": self.stash_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "branch": self.branch,
            "patch_file": self.patch_file,
            "modified_files": list(self.modified_files),
            "diff_summary": self.diff_summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RescueStashMetadata:
        """Constructs stash metadata from a dictionary representation."""
        return cls(
            stash_id=str(data.get("stash_id", "")),
            task_id=str(data.get("task_id", "")),
            timestamp=str(data.get("timestamp", "")),
            branch=str(data.get("branch", "")),
            patch_file=str(data.get("patch_file", "")),
            modified_files=list(data.get("modified_files", [])),
            diff_summary=str(data.get("diff_summary", "")),
        )


@dataclass
class StashResetResult:
    """Outcome of a worktree clean reset and stash recovery operation."""

    success: bool
    stash_id: str | None
    is_clean: bool
    reset_commit: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Serializes result into dictionary format."""
        return {
            "success": self.success,
            "stash_id": self.stash_id,
            "is_clean": self.is_clean,
            "reset_commit": self.reset_commit,
            "message": self.message,
        }

    def summary(self) -> str:
        """Renders human-readable summary string."""
        status_str = "SUCCESS" if self.success else "FAILED"
        stash_str = f" [Stash: {self.stash_id}]" if self.stash_id else ""
        commit_str = f" @ {self.reset_commit[:7]}" if self.reset_commit else ""
        return f"[{status_str}] Clean: {self.is_clean}{commit_str}{stash_str} - {self.message}"


class WorktreeStashResetter:
    """Engine for creating rescue stashes, clean resets, and patch reapplication."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root

    @classmethod
    def _resolve_task_id(cls, worktree_dir: Path, task_id: str) -> str:
        if task_id:
            return task_id
        branch = get_worktree_branch(worktree_dir)
        m = re.search(r"TASK-\d+", branch, re.IGNORECASE)
        if m:
            return m.group(0).upper()
        m_dir = re.search(r"task-?(\d+)", worktree_dir.name, re.IGNORECASE)
        if m_dir:
            return f"TASK-{int(m_dir.group(1)):04d}"
        return "TASK-UNKNOWN"

    @classmethod
    def create_rescue_stash(
        cls, worktree_dir: Path, task_id: str = ""
    ) -> RescueStashMetadata | None:
        """Creates timestamped patch archive in .specops/rescue_stashes/ with diff summary."""
        if not is_worktree_dirty(worktree_dir):
            return None

        repo_root = resolve_repo_root(worktree_dir)
        stashes_dir = repo_root / ".specops" / "rescue_stashes"
        stashes_dir.mkdir(parents=True, exist_ok=True)
        gi = stashes_dir / ".gitignore"
        if not gi.exists():
            gi.write_text("*\n", encoding="utf-8")

        effective_task_id = cls._resolve_task_id(worktree_dir, task_id)
        branch = get_worktree_branch(worktree_dir) or "HEAD"
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_slug = now.strftime("%Y%m%d_%H%M%S")

        tid_clean = re.sub(r"[^a-zA-Z0-9_-]", "_", effective_task_id)
        base_stash_id = f"stash_{tid_clean}_{ts_slug}"
        stash_id = base_stash_id
        counter = 1
        while (stashes_dir / f"{stash_id}.json").exists():
            stash_id = f"{base_stash_id}_{counter}"
            counter += 1

        status_res = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        modified_files: list[str] = []
        untracked_files: list[str] = []
        for line in status_res.stdout.splitlines():
            if not line.strip():
                continue
            code, fname = line[:2], line[3:].strip()
            if " -> " in fname:
                fname = fname.split(" -> ")[-1].strip()
            if fname.startswith('"') and fname.endswith('"'):
                fname = fname[1:-1]
            if fname.startswith(".specops") or fname.startswith(".git"):
                continue
            modified_files.append(fname)
            if code == "??":
                untracked_files.append(fname)

        if untracked_files:
            subprocess.run(
                ["git", "-c", "core.quotepath=false", "add", "-N", "--"] + untracked_files,
                cwd=worktree_dir,
                capture_output=True,
            )

        diff_res = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--binary", "HEAD"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        patch_content = diff_res.stdout or subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--binary"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        ).stdout

        stat_res = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--stat", "HEAD"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        diff_summary = stat_res.stdout.strip() or f"{len(modified_files)} file(s) modified"

        patch_file = stashes_dir / f"{stash_id}.patch"
        patch_file.write_text(patch_content, encoding="utf-8")

        meta = RescueStashMetadata(
            stash_id=stash_id,
            task_id=effective_task_id,
            timestamp=timestamp,
            branch=branch,
            patch_file=str(patch_file.resolve()),
            modified_files=modified_files,
            diff_summary=diff_summary,
        )
        (stashes_dir / f"{stash_id}.json").write_text(
            json.dumps(meta.to_dict(), indent=2), encoding="utf-8"
        )
        return meta

    @classmethod
    def clean_reset(
        cls, worktree_dir: Path, stash: bool = True, task_id: str = ""
    ) -> StashResetResult:
        """Performs clean reset to HEAD, optionally stashing uncommitted changes first."""
        dirty = is_worktree_dirty(worktree_dir)
        stash_id: str | None = None

        if dirty and stash:
            meta = cls.create_rescue_stash(worktree_dir, task_id=task_id)
            if meta:
                stash_id = meta.stash_id

        reset_res = subprocess.run(
            ["git", "reset", "--hard", "HEAD"], cwd=worktree_dir, capture_output=True, text=True
        )
        if reset_res.returncode != 0:
            err = reset_res.stderr.strip() or "git reset failed"
            return StashResetResult(
                success=False,
                stash_id=stash_id,
                is_clean=False,
                reset_commit="",
                message=f"Failed to reset worktree: {err}",
            )

        subprocess.run(["git", "clean", "-fd"], cwd=worktree_dir, capture_output=True, text=True)
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=worktree_dir, capture_output=True, text=True
        ).stdout.strip()
        is_clean = not is_worktree_dirty(worktree_dir)

        if stash_id:
            msg = f"Worktree cleanly reset to HEAD ({commit[:7]}). Uncommitted modifications archived to rescue stash '{stash_id}'."
        elif dirty:
            msg = f"Worktree cleanly reset to HEAD ({commit[:7]}) without stashing."
        else:
            msg = f"Worktree already clean at HEAD ({commit[:7]})."

        return StashResetResult(
            success=is_clean,
            stash_id=stash_id,
            is_clean=is_clean,
            reset_commit=commit,
            message=msg,
        )

    @classmethod
    def list_rescue_stashes(
        cls, repo_root: Path, task_id: str | None = None
    ) -> list[RescueStashMetadata]:
        """Lists available rescue stashes, optionally filtered by task ID."""
        real_root = resolve_repo_root(repo_root)
        stashes_dir = real_root / ".specops" / "rescue_stashes"
        if not stashes_dir.exists() and (repo_root / ".specops" / "rescue_stashes").exists():
            stashes_dir = repo_root / ".specops" / "rescue_stashes"
        if not stashes_dir.exists() or not stashes_dir.is_dir():
            return []

        results: list[RescueStashMetadata] = []
        for meta_file in sorted(stashes_dir.glob("*.json")):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                meta = RescueStashMetadata.from_dict(data)
                if task_id:
                    tid_norm = task_id.upper().replace("TASK-", "").lstrip("0")
                    meta_norm = meta.task_id.upper().replace("TASK-", "").lstrip("0")
                    if task_id.upper() not in meta.task_id.upper() and tid_norm != meta_norm:
                        continue
                results.append(meta)
            except Exception:
                continue

        results.sort(key=lambda s: s.timestamp, reverse=True)
        return results

    @classmethod
    def apply_rescue_stash(
        cls, worktree_dir: Path, stash_id: str
    ) -> tuple[bool, str]:
        """Applies a previously created rescue stash to a worktree."""
        repo_root = resolve_repo_root(worktree_dir)
        stashes_dir = repo_root / ".specops" / "rescue_stashes"

        target_meta: RescueStashMetadata | None = None
        exact_json = stashes_dir / f"{stash_id}.json"
        if exact_json.exists():
            try:
                target_meta = RescueStashMetadata.from_dict(
                    json.loads(exact_json.read_text(encoding="utf-8"))
                )
            except Exception:
                pass

        if not target_meta:
            for s in cls.list_rescue_stashes(repo_root):
                if s.stash_id == stash_id or s.stash_id.startswith(stash_id) or stash_id in s.stash_id:
                    target_meta = s
                    break

        patch_path: Path | None = None
        if target_meta:
            cand = Path(target_meta.patch_file)
            patch_path = cand if cand.exists() else stashes_dir / f"{target_meta.stash_id}.patch"
        elif (stashes_dir / f"{stash_id}.patch").exists():
            patch_path = stashes_dir / f"{stash_id}.patch"

        if not patch_path or not patch_path.exists():
            return False, f"Rescue stash '{stash_id}' not found."

        res = subprocess.run(
            ["git", "-c", "core.quotepath=false", "apply", "--whitespace=nowarn", str(patch_path.resolve())],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            found_id = target_meta.stash_id if target_meta else stash_id
            return True, f"Successfully applied rescue stash '{found_id}'."
        err_msg = res.stderr.strip() or "git apply failed"
        return False, f"Failed to apply rescue stash '{stash_id}': {err_msg}"


def create_rescue_stash(
    worktree_dir: Path, task_id: str = ""
) -> RescueStashMetadata | None:
    """Functional wrapper for WorktreeStashResetter.create_rescue_stash."""
    return WorktreeStashResetter.create_rescue_stash(worktree_dir, task_id=task_id)


def clean_reset(
    worktree_dir: Path, stash: bool = True, task_id: str = ""
) -> StashResetResult:
    """Functional wrapper for WorktreeStashResetter.clean_reset."""
    return WorktreeStashResetter.clean_reset(worktree_dir, stash=stash, task_id=task_id)


def list_rescue_stashes(
    repo_root: Path, task_id: str | None = None
) -> list[RescueStashMetadata]:
    """Functional wrapper for WorktreeStashResetter.list_rescue_stashes."""
    return WorktreeStashResetter.list_rescue_stashes(repo_root, task_id=task_id)


def apply_rescue_stash(worktree_dir: Path, stash_id: str) -> tuple[bool, str]:
    """Functional wrapper for WorktreeStashResetter.apply_rescue_stash."""
    return WorktreeStashResetter.apply_rescue_stash(worktree_dir, stash_id)
