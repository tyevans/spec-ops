"""Human developer worktree sandboxing commands."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ..backlog.queue import BacklogQueue
from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..worker.integration import rebase_with_inference_healing, squash_merge_and_commit
from ..worker.merge_lock import MergeLockManager
from ..worker.preflight import run_worktree_preflight
from .lifecycle import cleanup_worktree, create_worktree, get_worktree_branch, init_worktree_environment


def _normalize_id(raw_id: str) -> tuple[str, str]:
    """Returns (canonical_id, tid_num) e.g. ('TASK-0021', '0021')."""
    clean = raw_id.upper().replace("TASK-", "").lstrip("0")
    tid_num = clean.zfill(4) if clean else "0000"
    return f"TASK-{tid_num}", tid_num


def start_human_worktree(
    config: SpecOpsConfig,
    task_id_input: str,
) -> tuple[bool, str, Path | None]:
    """Provisions an isolated development worktree for human engineers."""
    canonical_id, tid_num = _normalize_id(task_id_input)
    repo_root = config.root_dir

    queue = BacklogQueue(config.backlog_dir)
    target_task: Task | None = None
    for t in queue.list_all_tasks():
        if t.canonical_id == canonical_id:
            target_task = t
            break

    if not target_task:
        return False, f"Task {canonical_id} not found in backlog ({config.backlog_dir}).", None

    worktree_dir = repo_root / ".worktrees" / f"task-{tid_num}"
    branch = f"feat/{canonical_id}"

    try:
        create_worktree(repo_root, branch=branch, worktree_dir=worktree_dir, check_dirty=True)
    except Exception as e:
        return False, f"Failed to provision worktree: {e}", None

    init_worktree_environment(repo_root, worktree_dir)

    msg = (
        f"✨ Worktree initialized for {canonical_id} at .worktrees/task-{tid_num} on branch {branch}\n"
        f"👉 To enter the workspace: cd .worktrees/task-{tid_num}"
    )
    return True, msg, worktree_dir


def finish_human_worktree(
    config: SpecOpsConfig,
    task_id_input: str | None = None,
) -> tuple[bool, str]:
    """Runs preflight verification, merges into main under MERGE_LOCK, and tears down worktree."""
    repo_root = config.root_dir
    worktree_dir: Path | None = None

    if task_id_input:
        canonical_id, tid_num = _normalize_id(task_id_input)
        candidate = repo_root / ".worktrees" / f"task-{tid_num}"
        if candidate.exists():
            worktree_dir = candidate
    else:
        # Auto-detect from current working directory
        cwd = Path.cwd().resolve()
        for p in [cwd, *cwd.parents]:
            if p.parent.name == ".worktrees" and re.match(r"^task-\d+", p.name, re.IGNORECASE):
                try:
                    if p.is_relative_to(repo_root):
                        worktree_dir = p
                        break
                except ValueError:
                    pass
            if (p / ".git").exists():
                break

    if not worktree_dir or not worktree_dir.exists():
        return False, "Not inside an active task worktree. Specify task ID or run from within .worktrees/task-XXXX."

    # Identify task
    m = re.match(r"^task-(\d+)", worktree_dir.name, re.IGNORECASE)
    tid_num = m.group(1).zfill(4) if m else "0000"
    canonical_id = f"TASK-{tid_num}"

    queue = BacklogQueue(config.backlog_dir)
    target_task = None
    for t in queue.list_all_tasks():
        if t.canonical_id == canonical_id:
            target_task = t
            break

    if not target_task:
        return False, f"Task {canonical_id} not found in backlog."

    branch = get_worktree_branch(worktree_dir) or f"feat/{canonical_id}"

    # 1. Backlog isolation guard: discard accidental edits to backlog inside worktree
    if config.execution.backlog_isolation:
        docs_dir = str(config.project.docs_dir)
        chk = subprocess.run(
            ["git", "status", "--porcelain", docs_dir],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if chk.stdout.strip():
            subprocess.run(["git", "checkout", "HEAD", "--", docs_dir], cwd=worktree_dir)

    # 2. Stage and commit uncommitted changes in worktree
    diff_chk = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if diff_chk.stdout.strip():
        subprocess.run(["git", "add", "-A"], cwd=worktree_dir, capture_output=True)
        commit_res = subprocess.run(
            ["git", "commit", "-m", f"feat({canonical_id.lower()}): {target_task.title}"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout:
            return False, f"Failed to commit modifications in worktree: {commit_res.stderr.strip()}"

    # 3. Local preflight verification
    all_tasks = queue.list_all_tasks()
    preflight_ok, preflight_log = run_worktree_preflight(config, worktree_dir, all_tasks=all_tasks, task=target_task)
    if not preflight_ok:
        return False, f"Preflight verification failed in worktree:\n{preflight_log}"

    # 4. Auto-rebase onto main if behind
    lock_mgr = MergeLockManager(repo_root)
    if lock_mgr.is_branch_behind_main(branch):
        rebase_ok, rebase_msg = rebase_with_inference_healing(worktree_dir, target_task, config)
        if not rebase_ok:
            return False, f"Rebase conflict against main during worktree completion: {rebase_msg}"

    # 5. Squash-merge under MERGE_LOCK
    try:
        with lock_mgr.acquire(timeout=120.0):
            if lock_mgr.is_branch_behind_main(branch):
                rebase_ok, rebase_msg = rebase_with_inference_healing(worktree_dir, target_task, config)
                if not rebase_ok:
                    return False, f"Rebase conflict against main under merge lock: {rebase_msg}"

            merge_ok, merge_msg = squash_merge_and_commit(
                repo_root,
                branch,
                f"feat({canonical_id.lower()}): {target_task.title}",
                on_staged=lambda: queue.complete_task(target_task),
            )
            if not merge_ok:
                return False, f"Squash-merge failed: {merge_msg}"

        # 6. Safely return working directory to repo root
        try:
            os.chdir(repo_root)
        except OSError:
            pass

        # 7. Atomic teardown
        cleanup_worktree(repo_root, worktree_dir, branch=branch, delete_branch=True)
        return True, f"✅ Task {canonical_id} successfully verified, merged to main, advanced to complete/, and worktree removed."
    except Exception as e:
        return False, f"Worktree finalization failed: {e}"
