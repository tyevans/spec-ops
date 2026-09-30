"""Integration and rebase coordination with inference-driven self-healing."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from ..config.models import SpecOpsConfig
from ..core.models import Task


def rebase_with_inference_healing(
    worktree_dir: Path,
    task: Task,
    config: SpecOpsConfig,
    main_branch: str = "main",
) -> tuple[bool, str]:
    """Attempts to rebase task branch onto main.

    If conflicts are encountered, extracts conflict hunks, invokes an
    inference agent to resolve them cleanly, verifies no conflict markers remain,
    and continues rebase. Aborts cleanly if healing fails.
    """
    rebase_cmd = subprocess.run(
        ["git", "rebase", main_branch],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if rebase_cmd.returncode == 0:
        return True, "Rebased successfully onto latest main."

    raw_conflict = rebase_cmd.stderr.strip() or rebase_cmd.stdout.strip()

    enable_healing = getattr(config.execution, "enable_conflict_healing", True)
    agent_cmd = (
        config.execution.agent_command.strip()
        if config.execution.agent_command
        else ""
    )

    if not enable_healing or not agent_cmd:
        subprocess.run(["git", "rebase", "--abort"], cwd=worktree_dir, capture_output=True)
        return False, raw_conflict

    # Identify unmerged/conflicted files
    status_res = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    conflicted_files = [f.strip() for f in status_res.stdout.splitlines() if f.strip()]
    if not conflicted_files:
        porc_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        conflicted_files = [
            line[3:].strip()
            for line in porc_res.stdout.splitlines()
            if line.startswith("UU ") or line.startswith("AA ")
        ]

    if not conflicted_files:
        subprocess.run(["git", "rebase", "--abort"], cwd=worktree_dir, capture_output=True)
        return False, raw_conflict

    print(
        f"🔧 Rebase conflict detected on {task.canonical_id} in: "
        f"{', '.join(conflicted_files)}. Attempting inference self-healing..."
    )

    conflict_contexts: list[str] = []
    for f in conflicted_files:
        fp = worktree_dir / f
        if fp.is_file():
            text = fp.read_text(encoding="utf-8", errors="replace")
            if "<<<<<<<" in text:
                conflict_contexts.append(f"### {f}\n```\n{text[:4000]}\n```")

    prompt = (
        f"# Rebase Conflict Resolution: {task.canonical_id} — {task.title}\n\n"
        f"A git merge conflict occurred while rebasing branch onto latest '{main_branch}'.\n\n"
        f"## Conflicted Files\n"
        + "\n".join(f"- {f}" for f in conflicted_files)
        + "\n\n"
        f"## Conflicted File Contents\n"
        + "\n\n".join(conflict_contexts)
        + "\n\n"
        "## CRITICAL INSTRUCTIONS\n"
        "1. Open and edit the conflicted files in the worktree directly.\n"
        "2. Resolve all conflicts cleanly: preserve incoming changes from main AND your task additions.\n"
        "3. Remove ALL git conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).\n"
        "4. Ensure Python syntax is valid and no syntax errors are introduced.\n"
        "5. Do NOT run `git rebase --abort` or `git rebase --continue`. Simply edit and save the files.\n"
    )

    prompt_file = worktree_dir / ".task-conflict-prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    from ..backlog.prompts import build_agent_cmd

    cmd = build_agent_cmd(agent_cmd, prompt, prompt_file, continue_session=False)

    env = os.environ.copy()
    env["SPEC_OPS_WORKTREE"] = str(worktree_dir.resolve())
    env["PWD"] = str(worktree_dir.resolve())

    agent_res = subprocess.run(
        cmd,
        shell=False,
        cwd=worktree_dir,
        env=env,
        capture_output=True,
        text=True,
    )

    markers_remain = False
    for f in conflicted_files:
        fp = worktree_dir / f
        if fp.is_file():
            text = fp.read_text(encoding="utf-8", errors="replace")
            if "<<<<<<<" in text or ">>>>>>>" in text:
                markers_remain = True
                break

    if agent_res.returncode == 0 and not markers_remain:
        subprocess.run(["git", "add", "-A"], cwd=worktree_dir, capture_output=True)
        cont_res = subprocess.run(
            ["git", "-c", "core.editor=true", "rebase", "--continue"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if cont_res.returncode == 0:
            print(f"✨ Successfully healed rebase conflict for {task.canonical_id} via inference.")
            return True, "Rebase conflict successfully healed via inference."

    subprocess.run(["git", "rebase", "--abort"], cwd=worktree_dir, capture_output=True)
    return (
        False,
        f"Rebase conflict on {task.canonical_id} (inference healing failed): {raw_conflict}",
    )


def squash_merge_and_commit(
    repo_root: Path,
    branch: str,
    commit_msg: str,
    on_staged: Callable[[], None] | None = None,
    main_branch: str = "main",
) -> tuple[bool, str]:
    """Squash-merges branch into main and commits under MERGE_LOCK with safety checks."""
    porc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if porc.returncode != 0:
        return False, f"Failed to check git status in {repo_root}: {porc.stderr}"

    for line in porc.stdout.splitlines():
        if line.startswith("UU ") or line.startswith("AA ") or line.startswith("DD "):
            return (
                False,
                f"Root repository at {repo_root} has unresolved merge conflicts ({line}). "
                "Resolve them before integrating.",
            )

    branch_check = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    current_branch = branch_check.stdout.strip()
    if current_branch != main_branch:
        co_res = subprocess.run(
            ["git", "checkout", main_branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if co_res.returncode != 0:
            err = co_res.stderr.strip() or co_res.stdout.strip()
            return False, f"Failed to checkout {main_branch} in {repo_root}: {err}"

    merge_res = subprocess.run(
        ["git", "merge", "--squash", branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if merge_res.returncode != 0:
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_root, capture_output=True)
        err = merge_res.stderr.strip() or merge_res.stdout.strip()
        return False, f"Squash merge of {branch} failed: {err}"

    if on_staged:
        try:
            on_staged()
        except Exception as exc:
            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_root, capture_output=True)
            return False, f"Failed during post-merge queue transition: {exc}"

    add_res = subprocess.run(["git", "add", "-A"], cwd=repo_root, capture_output=True, text=True)
    if add_res.returncode != 0:
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_root, capture_output=True)
        return False, f"git add failed: {add_res.stderr}"

    import time
    commit_res = None
    for _ in range(3):
        commit_res = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if commit_res.returncode == 0:
            break
        err = commit_res.stderr.strip() or commit_res.stdout.strip()
        if "index.lock" in err:
            time.sleep(0.5)
            continue
        break

    if commit_res is None or commit_res.returncode != 0:
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_root, capture_output=True)
        err = commit_res.stderr.strip() or commit_res.stdout.strip() if commit_res else "unknown error"
        return False, f"git commit failed: {err}"

    return True, "Merged and committed cleanly."
