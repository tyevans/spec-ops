"""Integration and rebase coordination with inference-driven self-healing."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from ..config.models import SpecOpsConfig
from ..core.git_worktree import resolve_repo_root
from ..core.models import Task


def is_rebase_in_progress(worktree_dir: Path) -> bool:
    """Checks if a git rebase is currently active in the worktree."""
    git_dir_res = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if git_dir_res.returncode != 0:
        return False
    git_dir = Path(git_dir_res.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (worktree_dir / git_dir).resolve()
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


def determine_rebase_command(
    worktree_dir: Path,
    task: Task,
    main_branch: str = "main",
) -> list[str]:
    """Determines the optimal git rebase command to avoid replaying squashed commits.

    If intermediate commits from other tasks were squash-merged upstream into main,
    a standard `git rebase main` attempts to replay those already-integrated commits,
    leading to false merge conflicts.

    We first check `git merge-base --fork-point`. If a valid fork point exists in the
    upstream reflog that is newer than merge-base, we rebase using `--onto <main> <fork_point>`.
    Alternatively, we inspect the commit history between merge-base and HEAD to isolate
    the target task's commits.
    """
    merge_res = subprocess.run(
        ["git", "merge-base", main_branch, "HEAD"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    merge_base = merge_res.stdout.strip() if merge_res.returncode == 0 else ""

    fork_res = subprocess.run(
        ["git", "merge-base", "--fork-point", main_branch, "HEAD"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    fork_point = fork_res.stdout.strip() if fork_res.returncode == 0 else ""

    if fork_point and merge_base and fork_point != merge_base:
        return ["git", "rebase", "--onto", main_branch, fork_point]

    if merge_base:
        rev_res = subprocess.run(
            ["git", "rev-list", "--reverse", f"{merge_base}..HEAD"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        commit_shas = [c.strip() for c in rev_res.stdout.splitlines() if c.strip()]
        if len(commit_shas) > 1:
            clean_cid = task.canonical_id.lower()
            clean_num = task.id.lower().lstrip("0")
            first_task_sha = None
            for sha in commit_shas:
                show_res = subprocess.run(
                    ["git", "show", "-s", "--format=%s%n%b", sha],
                    cwd=worktree_dir,
                    capture_output=True,
                    text=True,
                )
                msg = show_res.stdout.lower()
                if (
                    clean_cid in msg
                    or f"task-{clean_num}" in msg
                    or (task.title and task.title.lower() in msg)
                ):
                    first_task_sha = sha
                    break

            if first_task_sha and first_task_sha != commit_shas[0]:
                parent_res = subprocess.run(
                    ["git", "rev-parse", f"{first_task_sha}^"],
                    cwd=worktree_dir,
                    capture_output=True,
                    text=True,
                )
                if parent_res.returncode == 0:
                    base_sha = parent_res.stdout.strip()
                    return ["git", "rebase", "--onto", main_branch, base_sha]

    return ["git", "rebase", main_branch]


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
    rebase_cmd = determine_rebase_command(worktree_dir, task, main_branch=main_branch)
    rebase_res = subprocess.run(
        rebase_cmd,
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if rebase_res.returncode == 0 and not is_rebase_in_progress(worktree_dir):
        return True, "Rebased successfully onto latest main."

    raw_conflict = rebase_res.stderr.strip() or rebase_res.stdout.strip()

    enable_healing = getattr(config.execution, "enable_conflict_healing", True)
    agent_cmd = (
        config.execution.agent_command.strip()
        if config.execution.agent_command
        else ""
    )

    if not enable_healing or not agent_cmd:
        subprocess.run(["git", "rebase", "--abort"], cwd=worktree_dir, capture_output=True)
        return False, raw_conflict

    from .runners import build_agent_cmd

    max_steps = 10
    step = 0
    while is_rebase_in_progress(worktree_dir) and step < max_steps:
        step += 1
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
            diff_staged = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=worktree_dir,
            )
            if diff_staged.returncode == 0:
                skip_res = subprocess.run(
                    ["git", "rebase", "--skip"],
                    cwd=worktree_dir,
                    capture_output=True,
                    text=True,
                )
                if skip_res.returncode == 0 and not is_rebase_in_progress(worktree_dir):
                    return True, "Rebased successfully onto latest main."
                continue
            else:
                cont_res = subprocess.run(
                    ["git", "-c", "core.editor=true", "rebase", "--continue"],
                    cwd=worktree_dir,
                    capture_output=True,
                    text=True,
                )
                if cont_res.returncode == 0 and not is_rebase_in_progress(worktree_dir):
                    return True, "Rebased successfully onto latest main."
                continue

        print(
            f"🔧 Rebase conflict detected on {task.canonical_id} in: "
            f"{', '.join(conflicted_files)}. Attempting inference self-healing (step {step})..."
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

        if prompt_file.exists():
            prompt_file.unlink()

        if agent_res.returncode != 0 or markers_remain:
            subprocess.run(["git", "rebase", "--abort"], cwd=worktree_dir, capture_output=True)
            return (
                False,
                f"Rebase conflict on {task.canonical_id} (inference healing failed): {raw_conflict}",
            )

        subprocess.run(["git", "add", "-A"], cwd=worktree_dir, capture_output=True)
        cont_res = subprocess.run(
            ["git", "-c", "core.editor=true", "rebase", "--continue"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if cont_res.returncode == 0 and not is_rebase_in_progress(worktree_dir):
            print(f"✨ Successfully healed rebase conflict for {task.canonical_id} via inference.")
            return True, "Rebase conflict successfully healed via inference."

    if not is_rebase_in_progress(worktree_dir):
        return True, "Rebase conflict successfully healed via inference."

    subprocess.run(["git", "rebase", "--abort"], cwd=worktree_dir, capture_output=True)
    return (
        False,
        f"Rebase conflict on {task.canonical_id} (inference healing failed after {step} steps): {raw_conflict}",
    )


def squash_merge_and_commit(
    repo_root: Path,
    branch: str,
    commit_msg: str,
    on_staged: Callable[[], None] | None = None,
    main_branch: str = "main",
) -> tuple[bool, str]:
    """Squash-merges branch into main and commits under MERGE_LOCK with safety checks."""
    repo_root = resolve_repo_root(repo_root)
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
