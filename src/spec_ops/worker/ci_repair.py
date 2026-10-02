"""Empty-diff guardrails and remote CI failure repair loop coordinator."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from ..config.models import SpecOpsConfig
    from ..core.models import Task


EXCLUDED_DIFF_FILES = (
    ".task-prompt.md",
    ".task-review-prompt.md",
    ".failure.log",
    ".specops",
)


def verify_worktree_diff(worktree_dir: Path | str) -> tuple[bool, str]:
    """Guards against empty, cosmetic, or whitespace-only agent modifications.

    Returns:
        (True, "") if meaningful code modifications were detected.
        (False, "No Modifications Produced") if the diff is empty or whitespace-only.
    """
    wt = Path(worktree_dir).resolve()

    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=wt,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return False, "No Modifications Produced"

    candidate_lines: list[tuple[str, str]] = []
    for line in res.stdout.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        status_prefix = line[:2]
        path_str = line[3:].strip().strip('"')
        if " -> " in path_str:
            path_str = path_str.split(" -> ")[-1].strip().strip('"')

        # Ignore prompt and review artifacts
        if any(path_str.endswith(exc) or exc in path_str for exc in EXCLUDED_DIFF_FILES):
            continue
        candidate_lines.append((status_prefix, path_str))

    if not candidate_lines:
        return False, "No Modifications Produced"

    # Separate untracked files from modified tracked files
    untracked_paths: list[str] = []
    has_tracked_changes = False

    for status_prefix, path_str in candidate_lines:
        if "??" in status_prefix:
            untracked_paths.append(path_str)
        else:
            has_tracked_changes = True

    # Check untracked files for non-whitespace content
    has_substantive_untracked = False
    for rel_path in untracked_paths:
        file_path = wt / rel_path
        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    has_substantive_untracked = True
                    break
            except Exception:
                has_substantive_untracked = True
                break
        elif file_path.is_dir():
            has_substantive_untracked = True
            break

    if has_substantive_untracked:
        return True, ""

    if not has_tracked_changes:
        return False, "No Modifications Produced"

    # Check tracked modifications excluding whitespace-only changes
    pathspec_args = ["--", "."] + [f":!{exc}" for exc in EXCLUDED_DIFF_FILES]
    unstaged_diff = subprocess.run(
        ["git", "diff", "-w", "--ignore-blank-lines"] + pathspec_args,
        cwd=wt,
        capture_output=True,
        text=True,
    )
    staged_diff = subprocess.run(
        ["git", "diff", "--cached", "-w", "--ignore-blank-lines"] + pathspec_args,
        cwd=wt,
        capture_output=True,
        text=True,
    )

    if unstaged_diff.stdout.strip() or staged_diff.stdout.strip():
        return True, ""

    return False, "No Modifications Produced"


def fetch_failed_ci_logs(
    cwd: Path | str,
    custom_cmd: Sequence[str] | None = None,
) -> tuple[bool, str]:
    """Queries GitHub CLI to extract failed step logs from remote CI."""
    cmd = list(custom_cmd) if custom_cmd else ["gh", "run", "view", "--log-failed"]
    try:
        res = subprocess.run(
            cmd,
            cwd=Path(cwd).resolve(),
            capture_output=True,
            text=True,
        )
        logs = res.stdout.strip() or res.stderr.strip()
        ok = res.returncode == 0 and bool(logs)
        return ok, logs or "No failed remote CI logs found."
    except Exception as exc:
        return False, f"Failed to execute '{' '.join(cmd)}': {exc}"


def extract_failure_trace(raw_log: str) -> str:
    """Extracts relevant failure trace lines from raw CI logs."""
    if not raw_log or not raw_log.strip():
        return "No failure trace provided."

    lines = raw_log.splitlines()
    error_markers = ("error", "fail", "exception", "traceback", "fatal", "assert", "err:")
    extracted: list[str] = []

    for line in lines:
        if any(marker in line.lower() for marker in error_markers):
            extracted.append(line)

    if extracted and len(extracted) < len(lines):
        return "\n".join(extracted)
    return raw_log.strip()


def inject_ci_failure_prompt(
    task_id: str,
    worktree_dir: Path,
    failure_trace: str,
) -> Path:
    """Extracts failure trace into worktree .task-prompt.md."""
    prompt_file = worktree_dir / ".task-prompt.md"
    existing_prompt = ""
    if prompt_file.exists():
        try:
            existing_prompt = prompt_file.read_text(encoding="utf-8")
        except Exception:
            existing_prompt = ""

    header = f"# Task {task_id}: Autonomous Remote CI Repair Loop"
    section = (
        f"\n\n## Remote CI Failure Diagnostics\n"
        f"Remote GitHub Actions checks failed for this pull request:\n"
        f"```\n{failure_trace}\n```\n"
        f"Please apply targeted repairs to fix the failing tests/checks."
    )

    if existing_prompt:
        updated = existing_prompt.rstrip() + section
    else:
        updated = f"{header}\n{section}\n"

    prompt_file.write_text(updated, encoding="utf-8")
    return prompt_file


def ci_heal_task(
    config: SpecOpsConfig,
    task_id: str,
    gh_cmd: Sequence[str] | None = None,
    dry_run: bool = False,
    no_push: bool = False,
) -> tuple[bool, str]:
    """Executes the end-to-end remote CI healing workflow for target task.

    1. Executes 'gh run view --log-failed' to extract failed step logs.
    2. Extracts failure trace into .task-prompt.md.
    3. Opens/prepares worktree (.worktrees/<task-id>).
    4. Invokes the agent with the failure context.
    5. Runs local preflight verification.
    6. When preflight passes, pushes updated branch and re-triggers remote CI.
    """
    from ..backlog.queue import BacklogQueue
    from .engine import BacklogWorkerEngine
    from .worktree import create_worktree

    queue = BacklogQueue(config.backlog_dir)
    clean_id = task_id.upper().strip()
    if not clean_id.startswith("TASK-") and clean_id.isdigit():
        clean_id = f"TASK-{clean_id.zfill(4)}"

    target_task: Task | None = None
    for t in queue.list_all_tasks():
        if t.canonical_id == clean_id:
            target_task = t
            break

    wt_slug = clean_id.lower().replace("task-", "")
    wt_dir = config.root_dir / ".worktrees" / f"task-{wt_slug}"
    branch = f"task/{clean_id}"

    # Open existing worktree or checkout existing branch into worktree
    if not wt_dir.exists():
        chk_branch = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=config.root_dir,
        )
        if chk_branch.returncode == 0:
            subprocess.run(
                ["git", "worktree", "add", str(wt_dir), branch],
                cwd=config.root_dir,
                capture_output=True,
                check=True,
            )
        else:
            create_worktree(config.root_dir, branch, wt_dir)

    # 1. Fetch remote CI failed logs
    ok_log, raw_logs = fetch_failed_ci_logs(wt_dir, custom_cmd=gh_cmd)
    failure_trace = extract_failure_trace(raw_logs)

    # 2. Extract failure trace into .task-prompt.md
    prompt_file = inject_ci_failure_prompt(clean_id, wt_dir, failure_trace)

    if dry_run:
        return True, f"Dry-run: CI failure trace injected into {prompt_file}"

    # 3. Invoke agent with failure context
    engine = BacklogWorkerEngine(config)
    if target_task is None:
        from ..core.models import Task
        target_task = Task(
            id=wt_slug,
            title=f"Task {clean_id}",
            status="Refined",
            target_bc="worker",
        )
    agent_ok, agent_msg = engine.invoke_agent(target_task, wt_dir)
    if not agent_ok:
        return False, f"Agent repair failed: {agent_msg}"

    # 4. Verify local preflight
    preflight_ok, preflight_log = engine.run_preflight(wt_dir, task=target_task)
    if not preflight_ok:
        return False, f"Preflight failed after repair: {preflight_log}"

    # 5. Commit, push updated branch, and re-trigger remote CI
    commit_ok, commit_msg = engine.prepare_commit(
        wt_dir,
        task=target_task,
        commit_msg=f"fix({clean_id.lower()}): repair remote CI failures",
    )
    if not commit_ok and "nothing to commit" not in commit_msg.lower():
        return False, f"Commit preparation failed: {commit_msg}"

    if not no_push:
        push_res = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=wt_dir,
            capture_output=True,
            text=True,
        )
        # Attempt to re-trigger remote CI via gh CLI if available
        if shutil.which("gh"):
            subprocess.run(["gh", "run", "rerun"], cwd=wt_dir, capture_output=True)

    return True, f"Successfully healed CI for {clean_id} and re-triggered remote CI."
