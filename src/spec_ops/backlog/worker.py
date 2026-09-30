from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..worker.integration import rebase_with_inference_healing, squash_merge_and_commit
from ..worker.merge_lock import MergeLockManager, _THREAD_LOCK as MERGE_LOCK
from ..worker.preflight import run_worktree_preflight
from ..worker.worktree import cleanup_worktree as _cleanup_worktree, create_worktree as _create_worktree
from .queue import BacklogQueue
from .reviewer import TaskReviewEngine


_GLOBAL_SHUTDOWN: bool = False


def request_global_shutdown() -> None:
    """Signals all worker retry loops to halt gracefully."""
    global _GLOBAL_SHUTDOWN
    _GLOBAL_SHUTDOWN = True


def is_shutdown_requested() -> bool:
    """Returns True if a shutdown has been requested via signal."""
    return _GLOBAL_SHUTDOWN


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

    def run_preflight(
        self, cwd: Path, task: Task | None = None, initial: bool = False
    ) -> tuple[bool, str]:
        """Runs configured preflight verification commands with supply-chain lockfile checks."""
        return run_worktree_preflight(
            self.config, cwd, all_tasks=self.queue.list_all_tasks(), task=task, initial=initial
        )

    def create_worktree(self, branch: str, worktree_dir: Path) -> None:
        """Robustly creates or resets an isolated git worktree branch."""
        _create_worktree(self.repo_root, branch, worktree_dir)

    def cleanup_worktree(self, worktree_dir: Path, branch: str, delete_branch: bool = False) -> None:
        """Removes a worktree and optionally deletes its associated branch."""
        _cleanup_worktree(self.repo_root, worktree_dir, branch, delete_branch=delete_branch)

    def prepare_commit(
        self,
        worktree_dir: Path,
        task: Task | None = None,
        commit_msg: str = "",
    ) -> tuple[bool, str]:
        """Initiates commit preparation with backlog guardrails and staging."""
        from ..worker.commits import format_task_commit_message
        from ..worker.guardrails import prepare_guardrailed_commit
        msg = commit_msg or (
            format_task_commit_message(task)
            if task else "feat: worker commit"
        )
        allows_dep = getattr(task, "allows_dependencies", False) if task else False
        return prepare_guardrailed_commit(worktree_dir, msg, allows_dependencies=allows_dep)

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
        if prompt_file.exists():
            existing = prompt_file.read_text(encoding="utf-8", errors="ignore")
            if "## Remote CI Failure Diagnostics" in existing and "## Remote CI Failure Diagnostics" not in prompt:
                diag_idx = existing.find("## Remote CI Failure Diagnostics")
                prompt += "\n\n" + existing[diag_idx:]
        prompt_file.write_text(prompt, encoding="utf-8")

        run_review_enabled = not skip_review and getattr(self.config.execution, "enable_review", True)

        if dry_run or not self.config.execution.agent_command:
            print(f"📋 Task prompt generated at {prompt_file}")
            wt_res = str(worktree_dir.resolve())
            print(f"🔧 Environment configured: SPEC_OPS_WORKTREE={wt_res}, PWD={wt_res}")
            sim_cmd = build_agent_cmd(
                self.config.execution.agent_command or "echo {prompt_file}",
                prompt,
                prompt_file,
                worktree_dir=worktree_dir,
            )
            print(f"🔎 Simulated Agent Command: {sim_cmd}")
            if run_review_enabled:
                self.reviewer.run_review(task, worktree_dir, dry_run=True, attempt=1)
            return True, "Dry-run: Prompt generated successfully."

        cmd_template = self.config.execution.agent_command
        max_attempts = self.config.execution.agent_max_attempts
        last_failure_log = ""
        current_prompt = prompt
        self.last_attempt_history: list[tuple[int, int]] = []

        for attempt in range(1, max_attempts + 1):
            if is_shutdown_requested():
                print(f"⚠️ Shutdown requested. Halting worker attempts for {task.canonical_id}.")
                return False, "Interrupted by shutdown signal."

            print(f"🤖 Agent attempt {attempt}/{max_attempts} for {task.canonical_id}...")
            env = os.environ.copy()
            env["SPEC_OPS_WORKTREE"] = str(worktree_dir.resolve())
            env["PWD"] = str(worktree_dir.resolve())

            continue_session = attempt > 1
            cmd = build_agent_cmd(cmd_template, current_prompt, prompt_file, continue_session=continue_session)
            sandbox_config = getattr(self.config.execution, "sandbox", None)
            if sandbox_config and getattr(sandbox_config, "enabled", True):
                from ..security.sandbox import ExecutionSandbox
                sandbox = ExecutionSandbox(
                    worktree_dir=worktree_dir,
                    allowed_commands=sandbox_config.allowed_commands,
                    isolate_network=sandbox_config.isolate_network,
                )
                res = sandbox.run(cmd, shell=False, cwd=worktree_dir, env=env, capture_output=True, text=True)
            else:
                res = subprocess.run(cmd, shell=False, cwd=worktree_dir, env=env, capture_output=True, text=True)

            # If continuing session failed, retry attempt without -c
            if res.returncode != 0 and continue_session and "-c" in cmd and res.returncode != 126:
                fallback_cmd = build_agent_cmd(cmd_template, current_prompt, prompt_file, continue_session=False)
                if sandbox_config and getattr(sandbox_config, "enabled", True):
                    res = sandbox.run(fallback_cmd, shell=False, cwd=worktree_dir, env=env, capture_output=True, text=True)
                else:
                    res = subprocess.run(fallback_cmd, shell=False, cwd=worktree_dir, env=env, capture_output=True, text=True)

            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip() or f"process returned code {res.returncode}"
                if res.returncode == 126:
                    print(f"❌ Security violation: {err_msg[:300]}")
                    return False, f"Command Prohibited (exit code 126): {err_msg}"
                if (
                    res.returncode in (130, -2, -15)
                    or "interrupted" in err_msg.lower()
                    or "context canceled" in err_msg.lower()
                    or is_shutdown_requested()
                ):
                    print(f"⚠️ Agent execution interrupted by signal. Aborting attempts for {task.canonical_id}.")
                    return False, f"Interrupted by signal: {err_msg}"
                print(f"❌ Agent command returned code {res.returncode}: {err_msg[:300]}")
                feedback = f"\n\n## Agent Execution Failure (Attempt {attempt})\n{err_msg}\nPlease resolve this failure."
                current_prompt = prompt + feedback
                prompt_file.write_text(current_prompt, encoding="utf-8")
                self.last_attempt_history.append((attempt, res.returncode if res.returncode else 1))
                last_failure_log = err_msg
                continue

            # Verify that real code modifications were produced (excluding prompt files)
            from ..worker.ci_repair import verify_worktree_diff
            diff_ok, diff_reason = verify_worktree_diff(worktree_dir)
            if not diff_ok:
                print(f"⚠️ Agent attempt {attempt} flagged as '{diff_reason}'. Retrying...")
                feedback = (
                    f"\n\n## Failure Feedback (Attempt {attempt})\n"
                    f"{diff_reason}: Implementation code is required. "
                    f"You must deliver real modifications to the codebase."
                )
                current_prompt = prompt + feedback
                prompt_file.write_text(current_prompt, encoding="utf-8")
                self.last_attempt_history.append((attempt, 1))
                last_failure_log = diff_reason
                continue

            if run_review_enabled:
                print(f"🔍 Running CI preflight and architectural review concurrently (Attempt {attempt})...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    ci_future = executor.submit(self.run_preflight, worktree_dir, task)
                    review_future = executor.submit(
                        self.reviewer.run_review,
                        task,
                        worktree_dir,
                        dry_run=dry_run,
                        attempt=attempt,
                    )
                    preflight_ok, preflight_log = ci_future.result()
                    review_res = review_future.result()

                if "Unauthorized Dependency Modification" in preflight_log:
                    print(f"❌ Security violation: {preflight_log}")
                    return False, f"Unauthorized Dependency Modification violation: {preflight_log}"

                if preflight_ok and review_res.approved:
                    print(f"✅ Preflight passed and architectural review approved on attempt {attempt}.")
                    return True, f"Preflight and architectural review passed on attempt {attempt}."

                feedback_sections: list[str] = []
                if not preflight_ok:
                    print(f"❌ CI preflight failed on attempt {attempt}.")
                    from ..worker.ast_analyzer import format_preflight_ast_feedback
                    feedback_sections.append(
                        format_preflight_ast_feedback(preflight_log, attempt, worktree_dir)
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
                self.last_attempt_history.append((attempt, 1))
                last_failure_log = feedback
            else:
                preflight_ok, preflight_log = self.run_preflight(worktree_dir, task)
                if "Unauthorized Dependency Modification" in preflight_log:
                    print(f"❌ Security violation: {preflight_log}")
                    return False, f"Unauthorized Dependency Modification violation: {preflight_log}"

                if preflight_ok:
                    return True, f"Preflight passed on attempt {attempt}."

                print(f"❌ Preflight failed on attempt {attempt}. Retrying with feedback...")
                from ..worker.ast_analyzer import format_preflight_ast_feedback
                feedback = "\n\n" + format_preflight_ast_feedback(preflight_log, attempt, worktree_dir)
                current_prompt = prompt + feedback
                prompt_file.write_text(current_prompt, encoding="utf-8")
                self.last_attempt_history.append((attempt, 1))
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
        clean_id = task.canonical_id.lower().replace("task-", "").replace("spike-", "")
        branch = task.branch or f"{self.config.execution.git_branch_prefix}task-{clean_id}"
        worktree_dir = self.repo_root / ".worktrees" / f"task-{clean_id}"
        success = False
        worktree_created = False
        agent_log = ""

        print(f"🚀 Starting worker for {task.canonical_id}: '{task.title}'")
        try:
            worktree_dir.parent.mkdir(parents=True, exist_ok=True)
            self.create_worktree(branch, worktree_dir)
            worktree_created = True
            print(f"✨ Created isolated worktree at .worktrees/task-{clean_id} on branch {branch}")

            # Ensure active repository profiles (e.g. security) are synchronized in worktree
            if (
                self.config.security is not None
                or (self.repo_root / "docs" / "project" / "SECURITY.md").exists()
            ):
                from ..profiles.security import sync_security_profile, validate_security_policy

                sec_ok, _ = validate_security_policy(worktree_dir)
                if not sec_ok:
                    sync_security_profile(worktree_dir, sync_worktrees=False)

            preflight_ok, preflight_log = self.run_preflight(worktree_dir, task=task, initial=True)
            if not preflight_ok:
                return WorkerResult(task.canonical_id, False, f"Initial preflight failed: {preflight_log}")

            agent_ok, agent_log = self.invoke_agent(task, worktree_dir, dry_run=dry_run, skip_review=skip_review)
            if not agent_ok:
                return WorkerResult(task.canonical_id, False, f"Agent execution failed: {agent_log}")

            if dry_run:
                success = True
                return WorkerResult(task.canonical_id, True, "Zero-cost dry-run simulation completed cleanly.")

            for p in (worktree_dir / ".task-prompt.md", worktree_dir / ".task-review-prompt.md", worktree_dir / "HANDOVER.md"):
                if p.exists():
                    p.unlink()

            from ..worker.commits import format_task_commit_message
            commit_msg = format_task_commit_message(task)
            commit_ok, commit_log = self.prepare_commit(worktree_dir, task=task, commit_msg=commit_msg)
            if not commit_ok:
                return WorkerResult(task.canonical_id, False, f"Commit preparation failed: {commit_log}")

            if local_merge:
                lock_mgr = MergeLockManager(self.repo_root)
                # 1. Rebase and preflight in isolated worktree WITHOUT holding MERGE_LOCK
                if lock_mgr.is_branch_behind_main(branch):
                    print(f"🔄 Task branch '{branch}' is behind main. Auto-rebasing onto latest main...")
                    rebase_ok, rebase_msg = rebase_with_inference_healing(worktree_dir, task, self.config)
                    if not rebase_ok:
                        print(f"⚠️ Rebase conflict on {task.canonical_id}. Aborting rebase and preserving worktree with status 'Conflict'.")
                        print(f"Actionable rescue: spec-ops rescue {task.canonical_id}")
                        return WorkerResult(task.canonical_id, False, f"Rebase conflict against main: {rebase_msg}")
                    print("✓ Rebase succeeded. Running preflight verification on rebased code...")
                    post_rebase_ok, post_rebase_log = self.run_preflight(worktree_dir, task=task)
                    if not post_rebase_ok:
                        print(f"❌ Post-rebase preflight failed on {task.canonical_id}.")
                        return WorkerResult(
                            task.canonical_id,
                            False,
                            f"Post-rebase preflight failed: {post_rebase_log}",
                        )

                # 2. Acquire MERGE_LOCK strictly for the atomic integration step (<1s)
                with lock_mgr.acquire(timeout=120.0):
                    from ..security.dual_custody import verify_worker_integration_gates
                    gate_ok, gate_msg = verify_worker_integration_gates(self.repo_root, branch, task, self.config)
                    if not gate_ok:
                        print(f"❌ {gate_msg}")
                        return WorkerResult(task.canonical_id, False, gate_msg)

                    if lock_mgr.is_branch_behind_main(branch):
                        rebase_ok, rebase_msg = rebase_with_inference_healing(
                            worktree_dir,
                            task,
                            self.config,
                        )
                        if not rebase_ok:
                            return WorkerResult(
                                task.canonical_id,
                                False,
                                f"Rebase conflict against main: {rebase_msg}",
                            )

                    merge_ok, merge_msg = squash_merge_and_commit(
                        self.repo_root, branch, commit_msg, on_staged=lambda: self.queue.complete_task(task)
                    )
                    if not merge_ok:
                        return WorkerResult(task.canonical_id, False, f"Integration failed: {merge_msg}")
                success = True
                return WorkerResult(task.canonical_id, True, "Completed and integrated cleanly.")
            success = True
            return WorkerResult(task.canonical_id, True, "Task verified in worktree.")

        except Exception as e:
            return WorkerResult(task.canonical_id, False, f"Worker error: {e}")
        finally:
            if not success and not dry_run:
                if worktree_created and worktree_dir.exists() and any(worktree_dir.iterdir()):
                    diag_file = worktree_dir / ".failure.log"
                    diag_file.write_text(
                        f"Autonomous Worker Execution Failure Report\nTask: {task.canonical_id}\n\nLast Failure Log:\n{agent_log or 'Preflight verification failed'}\n",
                        encoding="utf-8",
                    )
                    from ..rescue.handover import generate_handover_brief
                    generate_handover_brief(worktree_dir, task, agent_log or "Preflight verification failed", getattr(self, "last_attempt_history", None), self.config)
                    print(f"⚠️ Worker stalled. Preserved worktree at {worktree_dir} for human rescue ('spec-ops rescue {task.canonical_id}').")
                    print(f"spec-ops rescue {task.canonical_id}")
            else:
                self.cleanup_worktree(worktree_dir, branch, delete_branch=dry_run or local_merge)
                if dry_run:
                    print(f"🧹 Cleaned up dry-run worktree at .worktrees/task-{clean_id}.")
