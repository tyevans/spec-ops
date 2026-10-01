"""Selective worktree patch takeover and partial file salvage engine (US-0088)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from ..backlog.queue import BacklogQueue
from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..worker.integration import rebase_with_inference_healing, squash_merge_and_commit
from ..worker.merge_lock import MergeLockManager
from .lifecycle import cleanup_worktree, get_worktree_branch


def normalize_task_id(task_id_input: str) -> tuple[str, str]:
    """Returns (canonical_id, tid_num) e.g. ('TASK-0018', '0018')."""
    clean = str(task_id_input).upper().replace("TASK-", "").lstrip("0")
    tid_num = clean.zfill(4) if clean else "0000"
    return f"TASK-{tid_num}", tid_num


def get_rescue_branch_name(task_id_input: str, worktree_dir: Path | None = None) -> str:
    """Returns canonical rescue branch name (e.g. 'rescue/task-0018' or existing 'rescue/TASK-0018')."""
    canonical_id, tid_num = normalize_task_id(task_id_input)
    default_branch = f"rescue/task-{tid_num}"
    if worktree_dir and worktree_dir.exists():
        chk_upper = subprocess.run(
            ["git", "branch", "--list", f"rescue/{canonical_id}"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if chk_upper.stdout.strip():
            return f"rescue/{canonical_id}"
        chk_lower = subprocess.run(
            ["git", "branch", "--list", default_branch],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if chk_lower.stdout.strip():
            return default_branch
    return default_branch


def get_staged_files(worktree_dir: Path) -> list[str]:
    """Returns list of staged relative file paths in git index."""
    res = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return []
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def get_untracked_files(worktree_dir: Path) -> list[str]:
    """Returns list of untracked file paths in worktree."""
    res = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return []
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def ensure_rescue_branch(worktree_dir: Path, task_id_input: str) -> tuple[bool, str]:
    """Switches to or provisions clean human rescue branch."""
    rescue_branch = get_rescue_branch_name(task_id_input, worktree_dir)
    curr_res = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    curr_branch = curr_res.stdout.strip() if curr_res.returncode == 0 else ""
    if curr_branch == rescue_branch:
        return True, rescue_branch

    branch_list = subprocess.run(
        ["git", "branch", "--list", rescue_branch],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if branch_list.stdout.strip():
        co_res = subprocess.run(["git", "checkout", rescue_branch], cwd=worktree_dir, capture_output=True, text=True)
    else:
        co_res = subprocess.run(["git", "checkout", "-b", rescue_branch], cwd=worktree_dir, capture_output=True, text=True)

    if co_res.returncode != 0:
        return False, f"Failed to switch to rescue branch {rescue_branch}: {co_res.stderr.strip()}"
    return True, rescue_branch


def _normalize_paths(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for p in paths:
        if "," in p:
            for sub in p.split(","):
                clean = sub.strip().strip("'\"")
                if clean:
                    normalized.append(clean)
        else:
            clean = p.strip().strip("'\"")
            if clean:
                normalized.append(clean)
    return normalized


def salvage_files(worktree_dir: Path, task_id_input: str, files: list[str]) -> tuple[bool, str]:
    """Resets index and stages exclusively the specified files on rescue branch."""
    ok, branch_or_err = ensure_rescue_branch(worktree_dir, task_id_input)
    if not ok:
        return False, branch_or_err

    subprocess.run(["git", "reset", "HEAD"], cwd=worktree_dir, capture_output=True)

    norm_paths = _normalize_paths(files)
    if not norm_paths:
        return False, "No file paths specified for salvage."

    for p in norm_paths:
        full_path = worktree_dir / p
        if not full_path.exists():
            return False, f"File to salvage does not exist: {p}"
        add_res = subprocess.run(["git", "add", "--", p], cwd=worktree_dir, capture_output=True, text=True)
        if add_res.returncode != 0:
            return False, f"Failed to stage {p}: {add_res.stderr.strip()}"

    staged = get_staged_files(worktree_dir)
    return True, f"Selectively salvaged {len(staged)} file(s) into rescue branch '{branch_or_err}'."


def salvage_task(config: SpecOpsConfig, task_id_input: str, files: list[str]) -> tuple[bool, str]:
    """Entry point for spec-ops rescue salvage <task-id> --files <paths>."""
    canonical_id, tid_num = normalize_task_id(task_id_input)
    worktree_dir = config.root_dir / ".worktrees" / f"task-{tid_num}"
    if not worktree_dir.exists():
        return False, f"Worktree not found for {canonical_id} at {worktree_dir}."
    return salvage_files(worktree_dir, task_id_input, files)


def patch_files(worktree_dir: Path, task_id_input: str, include_files: list[str]) -> tuple[bool, str]:
    """Incrementally stages files into rescue index without unstaging existing files."""
    ok, branch_or_err = ensure_rescue_branch(worktree_dir, task_id_input)
    if not ok:
        return False, branch_or_err

    norm_paths = _normalize_paths(include_files)
    if not norm_paths:
        return False, "No file paths specified to include in patch."

    for p in norm_paths:
        full_path = worktree_dir / p
        if not full_path.exists():
            return False, f"File to include does not exist: {p}"
        add_res = subprocess.run(["git", "add", "--", p], cwd=worktree_dir, capture_output=True, text=True)
        if add_res.returncode != 0:
            return False, f"Failed to stage {p}: {add_res.stderr.strip()}"

    staged = get_staged_files(worktree_dir)
    return True, f"Staged {len(norm_paths)} file(s) into rescue changeset. Staged files: {', '.join(staged)}."


def patch_task(config: SpecOpsConfig, task_id_input: str, include_files: list[str]) -> tuple[bool, str]:
    """Entry point for spec-ops rescue patch <task-id> --include <file>."""
    canonical_id, tid_num = normalize_task_id(task_id_input)
    worktree_dir = config.root_dir / ".worktrees" / f"task-{tid_num}"
    if not worktree_dir.exists():
        return False, f"Worktree not found for {canonical_id} at {worktree_dir}."
    return patch_files(worktree_dir, task_id_input, include_files)


def format_salvage_commit_message(
    task: Any,
    author: str | None = None,
    rescued_by: str | None = None,
) -> str:
    """Formats conventional squash commit message with structured dual-custody trailers."""
    canonical_id, tid_num = normalize_task_id(getattr(task, "canonical_id", "") or getattr(task, "id", ""))
    title = str(getattr(task, "title", "Core Domain Models")).strip()
    title_clean = re.sub(r"^(?:feat|refactor|spike|fix)\s*:\s*", "", title, flags=re.IGNORECASE).strip()
    if not title_clean:
        title_clean = "Salvaged Models and Logic"

    slice_type = getattr(task, "slice_type", None) or "feat"
    subject = f"{slice_type}(task-{tid_num}): {title_clean}"
    if not subject.endswith("(rescued)"):
        subject = f"{subject} (rescued)"

    author_val = author or "Morgan <agent@specops.local>"
    claimant = os.environ.get("SPECOPS_CLAIMANT", "Riley")
    rescued_by_val = rescued_by or os.environ.get("SPECOPS_RESCUED_BY") or (
        claimant if ("<" in claimant or "@" in claimant) else f"{claimant} <developer@company.com>"
    )

    trailers = [
        f"SpecOps-Task: {canonical_id}",
        f"Author: {author_val}",
        f"Rescued-By: {rescued_by_val}",
        "Provenance: agent-human-hybrid",
    ]
    stories = getattr(task, "governing_stories", None) or getattr(task, "governing_story", None)
    if stories:
        trailers.append(f"SpecOps-Story: {', '.join(stories) if isinstance(stories, list) else str(stories)}")
    prds = getattr(task, "governing_prds", None) or getattr(task, "governing_prd", None)
    if prds:
        trailers.append(f"SpecOps-PRD: {', '.join(prds) if isinstance(prds, list) else str(prds)}")
    adrs = getattr(task, "governing_adrs", None) or getattr(task, "governing_adr", None)
    if adrs:
        trailers.append(f"SpecOps-ADR: {', '.join(adrs) if isinstance(adrs, list) else str(adrs)}")

    return f"{subject}\n\n" + "\n".join(trailers) + "\n"


def run_curated_preflight(
    config: SpecOpsConfig,
    worktree_dir: Path,
    task: Task | None = None,
) -> tuple[bool, str]:
    """Executes preflight verification solely against the curated staging area."""
    from .handover import purge_ephemeral_handover_artifacts
    from .incremental_runner import clear_step_cache

    purge_ephemeral_handover_artifacts(worktree_dir)
    clear_step_cache(worktree_dir)

    stash_res = subprocess.run(
        ["git", "stash", "push", "--keep-index", "-u", "-m", "spec-ops-salvage-preflight"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    stashed = "Saved" in stash_res.stdout or "Saved" in stash_res.stderr

    try:
        from ..backlog.worker import BacklogWorkerEngine

        worker_engine = BacklogWorkerEngine(config)
        ok, log = worker_engine.run_preflight(worktree_dir, task=task)
        if not ok:
            if stashed:
                subprocess.run(["git", "stash", "pop"], cwd=worktree_dir, capture_output=True)
            return False, log

        if stashed:
            subprocess.run(["git", "stash", "drop"], cwd=worktree_dir, capture_output=True)
        return True, log
    except Exception as exc:
        if stashed:
            subprocess.run(["git", "stash", "pop"], cwd=worktree_dir, capture_output=True)
        return False, f"Preflight execution exception: {exc}"


def complete_salvage(
    config: SpecOpsConfig,
    task_id_input: str | None = None,
    author: str | None = None,
    rescued_by: str | None = None,
) -> tuple[bool, str]:
    """Runs curated preflight, commits with dual-custody trailers, squash-merges into main, and completes task."""
    repo_root = config.root_dir
    worktree_dir: Path | None = None

    if task_id_input:
        canonical_id, tid_num = normalize_task_id(task_id_input)
        candidate = repo_root / ".worktrees" / f"task-{tid_num}"
        if candidate.exists():
            worktree_dir = candidate
    else:
        cwd = Path.cwd().resolve()
        for p in [cwd, *cwd.parents]:
            if p.parent.name == ".worktrees" and re.match(r"^task-\d+", p.name, re.IGNORECASE):
                try:
                    if p.is_relative_to(repo_root):
                        worktree_dir = p
                        break
                except ValueError:
                    pass

    if not worktree_dir or not worktree_dir.exists():
        return False, "Not inside an active task worktree. Specify task ID or run from within .worktrees/task-XXXX."

    m = re.match(r"^task-(\d+)", worktree_dir.name, re.IGNORECASE)
    tid_num = m.group(1).zfill(4) if m else "0000"
    canonical_id = f"TASK-{tid_num}"

    queue = BacklogQueue(config.backlog_dir)
    target_task = next((t for t in queue.list_all_tasks() if t.canonical_id == canonical_id), None)
    if not target_task:
        return False, f"Task {canonical_id} not found in backlog."

    branch = get_worktree_branch(worktree_dir) or get_rescue_branch_name(canonical_id, worktree_dir)

    staged = get_staged_files(worktree_dir)
    ahead_chk = subprocess.run(["git", "log", "main..HEAD", "--oneline"], cwd=worktree_dir, capture_output=True, text=True)
    if not staged and not ahead_chk.stdout.strip():
        return False, f"No staged changes or rescue commits found in worktree {worktree_dir}."

    preflight_ok, preflight_log = run_curated_preflight(config, worktree_dir, task=target_task)
    if not preflight_ok:
        return False, f"Preflight verification failed on curated salvage staging area:\n{preflight_log}"

    commit_msg = format_salvage_commit_message(target_task, author=author, rescued_by=rescued_by)
    if staged:
        commit_res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=worktree_dir, capture_output=True, text=True)
        if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout:
            return False, f"Failed to commit curated salvage changes: {commit_res.stderr.strip()}"

    lock_mgr = MergeLockManager(repo_root)
    if lock_mgr.is_branch_behind_main(branch):
        rebase_ok, rebase_msg = rebase_with_inference_healing(worktree_dir, target_task, config)
        if not rebase_ok:
            return False, f"Rebase conflict against main during salvage completion: {rebase_msg}"

    try:
        with lock_mgr.acquire(timeout=120.0):
            if lock_mgr.is_branch_behind_main(branch):
                rebase_ok, rebase_msg = rebase_with_inference_healing(worktree_dir, target_task, config)
                if not rebase_ok:
                    return False, f"Rebase conflict against main under merge lock: {rebase_msg}"

            merge_ok, merge_msg = squash_merge_and_commit(
                repo_root,
                branch,
                commit_msg,
                on_staged=lambda: queue.complete_task(target_task),
            )
            if not merge_ok:
                return False, f"Squash-merge failed: {merge_msg}"

        try:
            os.chdir(repo_root)
        except OSError:
            pass

        cleanup_worktree(repo_root, worktree_dir, branch=branch, delete_branch=True)
        return True, f"✅ Task {canonical_id} successfully verified via salvage, merged to main, advanced to complete/, and worktree removed."
    except Exception as e:
        return False, f"Salvage finalization failed: {e}"
