from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..worker.merge_lock import MergeLockManager, _THREAD_LOCK as MERGE_LOCK
from .queue import BacklogQueue
from .reviewer import TaskReviewEngine


@dataclass
class WorkerResult:
    task_id: str
    success: bool
    message: str = ""


from .prompts import build_task_prompt, build_agent_cmd


class BacklogWorkerEngine:
    """Coordinates autonomous task execution in isolated git worktrees."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.repo_root = config.root_dir
        self.queue = BacklogQueue(config.backlog_dir)
        self.reviewer = TaskReviewEngine(config)

    def run_preflight(self, cwd: Path) -> tuple[bool, str]:
        """Runs configured preflight verification commands with supply-chain lockfile checks."""
        commands = list(self.config.quality.preflight)

        if getattr(self.config.quality, "enforce_lockfile", True):
            if (cwd / "uv.lock").exists() and "uv lock --check" not in commands:
                commands.insert(0, "uv lock --check")

        logs: list[str] = []
        for cmd in commands:
            res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
            if res.returncode != 0:
                logs.append(f"Command '{cmd}' failed (code {res.returncode}):\n{res.stderr or res.stdout}")
                return False, "\n".join(logs)
            logs.append(f"✓ '{cmd}' passed.")
        return True, "\n".join(logs)

    def create_worktree(self, branch: str, worktree_dir: Path) -> None:
        """Robustly creates or resets an isolated git worktree branch."""
        # 1. Force remove worktree from git tracking if already registered
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=self.repo_root,
            capture_output=True,
        )
        # 2. Prune any stale administrative records in .git/worktrees/
        subprocess.run(["git", "worktree", "prune"], cwd=self.repo_root, capture_output=True)

        # 3. Clean up leftover directory if git worktree remove left anything behind
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)

        # 4. Prune again to ensure git recognizes the directory is gone
        subprocess.run(["git", "worktree", "prune"], cwd=self.repo_root, capture_output=True)

        # 5. Delete existing branch if it exists so we can start clean from HEAD
        chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=self.repo_root)
        if chk.returncode == 0:
            subprocess.run(["git", "branch", "-D", branch], cwd=self.repo_root, capture_output=True)

        # 6. Add worktree with -B to create or reset branch cleanly from HEAD
        add_res = subprocess.run(
            ["git", "worktree", "add", "-B", branch, str(worktree_dir), "HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if add_res.returncode != 0:
            # Fallback retry with prune in case of transient record lock
            subprocess.run(["git", "worktree", "prune"], cwd=self.repo_root, capture_output=True)
            retry_res = subprocess.run(
                ["git", "worktree", "add", "-B", branch, str(worktree_dir), "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
            if retry_res.returncode != 0:
                raise RuntimeError(
                    f"Failed to create worktree: {retry_res.stderr.strip() or add_res.stderr.strip()}"
                )

    def cleanup_worktree(self, worktree_dir: Path, branch: str, delete_branch: bool = False) -> None:
        """Removes a worktree and optionally deletes its associated branch."""
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=self.repo_root,
            capture_output=True,
        )
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=self.repo_root,
            capture_output=True,
        )
        if delete_branch:
            subprocess.run(
                ["git", "branch", "-D", branch],
                cwd=self.repo_root,
                capture_output=True,
            )

    def invoke_agent(
        self,
        task: Task,
        worktree_dir: Path,
        dry_run: bool = False,
        skip_review: bool = False,
    ) -> tuple[bool, str]:
        """Invokes configured agent command with self-healing feedback loop and concurrent review."""
        prompt = build_task_prompt(task, self.config)
        prompt_file = worktree_dir / ".task-prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")

        run_review_enabled = not skip_review and getattr(self.config.execution, "enable_review", True)

        if dry_run or not self.config.execution.agent_command:
            print(f"📋 Task prompt generated at {prompt_file}")
            if run_review_enabled:
                self.reviewer.run_review(task, worktree_dir, dry_run=True, attempt=1)
            return True, "Dry-run: Prompt generated successfully."

        cmd_template = self.config.execution.agent_command
        max_attempts = self.config.execution.agent_max_attempts
        last_failure_log = ""
        current_prompt = prompt

        for attempt in range(1, max_attempts + 1):
            print(f"🤖 Agent attempt {attempt}/{max_attempts} for {task.canonical_id}...")
            env = os.environ.copy()
            env["SPEC_OPS_WORKTREE"] = str(worktree_dir.resolve())
            env["PWD"] = str(worktree_dir.resolve())

            continue_session = attempt > 1
            cmd = build_agent_cmd(cmd_template, current_prompt, prompt_file, continue_session=continue_session)
            res = subprocess.run(cmd, shell=False, cwd=worktree_dir, env=env, capture_output=True, text=True)

            # If continuing session failed, retry attempt without -c
            if res.returncode != 0 and continue_session and "-c" in cmd:
                fallback_cmd = build_agent_cmd(cmd_template, current_prompt, prompt_file, continue_session=False)
                res = subprocess.run(fallback_cmd, shell=False, cwd=worktree_dir, env=env, capture_output=True, text=True)

            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip() or f"process returned code {res.returncode}"
                print(f"❌ Agent command returned code {res.returncode}: {err_msg[:300]}")
                feedback = f"\n\n## Agent Execution Failure (Attempt {attempt})\n{err_msg}\nPlease resolve this failure."
                current_prompt = prompt + feedback
                prompt_file.write_text(current_prompt, encoding="utf-8")
                last_failure_log = err_msg
                continue

            # Verify that real code modifications were produced (excluding prompt files)
            diff_check = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_dir, capture_output=True, text=True)
            modified_lines = [
                line for line in diff_check.stdout.splitlines()
                if not any(line.strip().endswith(p) for p in [".task-prompt.md", ".task-review-prompt.md"])
            ]
            if not modified_lines:
                print(f"⚠️ Agent attempt {attempt} succeeded without producing code modifications. Retrying...")
                feedback = f"\n\n## Failure Feedback (Attempt {attempt})\nNo code modifications were produced in the worktree. You must implement the requested feature."
                current_prompt = prompt + feedback
                prompt_file.write_text(current_prompt, encoding="utf-8")
                last_failure_log = "No modifications produced."
                continue

            if run_review_enabled:
                print(f"🔍 Running CI preflight and architectural review concurrently (Attempt {attempt})...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    ci_future = executor.submit(self.run_preflight, worktree_dir)
                    review_future = executor.submit(
                        self.reviewer.run_review,
                        task,
                        worktree_dir,
                        dry_run=dry_run,
                        attempt=attempt,
                    )
                    preflight_ok, preflight_log = ci_future.result()
                    review_res = review_future.result()

                if preflight_ok and review_res.approved:
                    print(f"✅ Preflight passed and architectural review approved on attempt {attempt}.")
                    return True, f"Preflight and architectural review passed on attempt {attempt}."

                feedback_sections: list[str] = []
                if not preflight_ok:
                    print(f"❌ CI preflight failed on attempt {attempt}.")
                    feedback_sections.append(
                        f"## Preflight Failure Feedback (Attempt {attempt})\n{preflight_log}\nPlease fix the preflight issues above."
                    )
                else:
                    print(f"✓ CI preflight passed on attempt {attempt}.")

                if not review_res.approved:
                    print(f"⚠️ Architectural review requested changes on attempt {attempt}.")
                    feedback_sections.append(
                        f"## Architectural Review Feedback (Attempt {attempt})\n{review_res.feedback}\nPlease address all architectural review feedback above."
                    )
                else:
                    print(f"✓ Architectural review approved on attempt {attempt}.")

                feedback = "\n\n".join(feedback_sections)
                current_prompt = prompt + "\n\n" + feedback
                prompt_file.write_text(current_prompt, encoding="utf-8")
                last_failure_log = feedback
            else:
                preflight_ok, preflight_log = self.run_preflight(worktree_dir)
                if preflight_ok:
                    return True, f"Preflight passed on attempt {attempt}."

                print(f"❌ Preflight failed on attempt {attempt}. Retrying with feedback...")
                feedback = f"\n\n## Preflight Failure Feedback (Attempt {attempt})\n{preflight_log}\nPlease fix the issues above."
                current_prompt = prompt + feedback
                prompt_file.write_text(current_prompt, encoding="utf-8")
                last_failure_log = preflight_log

        return False, f"Agent failed after {max_attempts} attempts. Last feedback:\n{last_failure_log}"

    def execute_task(
        self,
        task: Task,
        local_merge: bool = True,
        dry_run: bool = False,
        skip_review: bool = False,
    ) -> WorkerResult:
        """Executes a task in an isolated worktree with preflight verification."""
        branch = f"{self.config.execution.git_branch_prefix}{task.slug}"
        worktree_dir = self.repo_root / ".worktrees" / f"task-{task.id}"
        success = False
        worktree_created = False

        print(f"🚀 Starting worker for {task.canonical_id}: '{task.title}'")
        try:
            worktree_dir.parent.mkdir(parents=True, exist_ok=True)
            self.create_worktree(branch, worktree_dir)
            worktree_created = True

            preflight_ok, preflight_log = self.run_preflight(worktree_dir)
            if not preflight_ok:
                return WorkerResult(task.canonical_id, False, f"Initial preflight failed: {preflight_log}")

            agent_ok, agent_log = self.invoke_agent(task, worktree_dir, dry_run=dry_run, skip_review=skip_review)
            if not agent_ok:
                return WorkerResult(task.canonical_id, False, f"Agent execution failed: {agent_log}")

            if dry_run:
                success = True
                return WorkerResult(task.canonical_id, True, "Dry-run successful.")

            if self.config.execution.backlog_isolation:
                status = subprocess.run(
                    ["git", "status", "--porcelain", str(self.config.project.docs_dir)],
                    cwd=worktree_dir,
                    capture_output=True,
                    text=True,
                )
                if status.stdout.strip():
                    subprocess.run(
                        ["git", "checkout", "HEAD", "--", str(self.config.project.docs_dir)],
                        cwd=worktree_dir,
                    )

            # Clean up task prompt files before checking status and committing
            prompt_file = worktree_dir / ".task-prompt.md"
            if prompt_file.exists():
                prompt_file.unlink()
            review_prompt_file = worktree_dir / ".task-review-prompt.md"
            if review_prompt_file.exists():
                review_prompt_file.unlink()

            diff_res = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_dir, capture_output=True, text=True)
            if not diff_res.stdout.strip():
                return WorkerResult(task.canonical_id, False, "No modifications produced by worker.")


            commit_msg = (
                f"feat({task.canonical_id.lower()}): {task.title}\n\n"
                f"Task-ID: {task.canonical_id}\n"
                f"Governing-ADRs: {', '.join(task.governing_adrs) or 'None'}\n"
                f"Provenance: spec-ops autonomous worker"
            )
            subprocess.run(["git", "add", "-A"], cwd=worktree_dir, check=True)
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=worktree_dir,
                check=True,
            )

            if local_merge:
                lock_mgr = MergeLockManager(self.repo_root)
                with lock_mgr.acquire():
                    if lock_mgr.is_branch_behind_main(branch):
                        print(f"🔄 Task branch '{branch}' is behind main. Auto-rebasing onto latest main...")
                        rebase_ok, rebase_msg = lock_mgr.rebase_branch(worktree_dir)
                        if not rebase_ok:
                            print(
                                f"⚠️ Rebase conflict on {task.canonical_id}. Aborting rebase and preserving worktree with status 'Conflict'."
                            )
                            print(f"Actionable rescue: spec-ops rescue {task.canonical_id}")
                            return WorkerResult(
                                task.canonical_id,
                                False,
                                f"Rebase conflict against main: {rebase_msg}",
                            )
                        print("✓ Rebase succeeded. Running preflight verification on rebased code...")
                        post_rebase_ok, post_rebase_log = self.run_preflight(worktree_dir)
                        if not post_rebase_ok:
                            print(f"❌ Post-rebase preflight failed on {task.canonical_id}.")
                            return WorkerResult(
                                task.canonical_id,
                                False,
                                f"Post-rebase preflight failed: {post_rebase_log}",
                            )

                    subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True, capture_output=True)
                    subprocess.run(["git", "merge", "--squash", branch], cwd=self.repo_root, check=True, capture_output=True)
                    self.queue.complete_task(task)
                    subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True, capture_output=True)
                    subprocess.run(
                        ["git", "commit", "-m", commit_msg],
                        cwd=self.repo_root,
                        check=True,
                        capture_output=True,
                    )
                success = True
                return WorkerResult(task.canonical_id, True, "Completed and integrated cleanly.")
            success = True
            return WorkerResult(task.canonical_id, True, "Task verified in worktree.")

        except Exception as e:
            return WorkerResult(task.canonical_id, False, f"Worker error: {e}")
        finally:
            if not success and not dry_run:
                if worktree_created and worktree_dir.exists() and any(worktree_dir.iterdir()):
                    print(f"⚠️ Worker stalled. Preserved worktree at {worktree_dir} for human rescue ('spec-ops rescue {task.canonical_id}').")
            else:
                self.cleanup_worktree(worktree_dir, branch, delete_branch=dry_run or local_merge)
