"""Autonomous multi-worker engine with git worktree backlog isolation."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .queue import BacklogQueue

MERGE_LOCK = threading.Lock()


@dataclass
class WorkerResult:
    task_id: str
    success: bool
    message: str = ""


def build_task_prompt(task: Task, config: SpecOpsConfig) -> str:
    """Constructs explicit prompt contract for autonomous coding agents."""
    preflight_cmds = " && ".join(config.quality.preflight)
    parts = [
        f"# Task: {task.canonical_id} — {task.title}",
        "",
        "## Architectural Context",
        f"- Target Bounded Context: {task.target_bc or 'core'}",
        f"- Governing ADRs: {', '.join(task.governing_adrs) or 'None'}",
        f"- Governing PRDs: {', '.join(task.governing_prds) or 'None'}",
        f"- Governing Stories: {', '.join(task.governing_stories) or 'None'}",
        f"- File Length Invariant: Every new or edited source file must contain fewer than {config.architecture.file_length_limit} lines.",
        "- Testing Invariant: Features must be verified blackbox style through public entry points without private backdoors.",
        "- Backlog Isolation: DO NOT edit files under docs/project/ directly on this branch.",
        "",
        "## Task Specification",
        task.body.strip(),
        "",
        "## Acceptance Criteria & Preflight",
        f"Your modifications must pass: `{preflight_cmds}`",
        "Ensure all tests pass cleanly before completing.",
    ]
    return "\n".join(parts)


class BacklogWorkerEngine:
    """Coordinates autonomous task execution in isolated git worktrees."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.repo_root = config.root_dir
        self.queue = BacklogQueue(config.backlog_dir)

    def run_preflight(self, cwd: Path) -> tuple[bool, str]:
        """Runs configured preflight verification commands."""
        commands = self.config.quality.preflight
        logs: list[str] = []
        for cmd in commands:
            res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
            if res.returncode != 0:
                logs.append(f"Command '{cmd}' failed (code {res.returncode}):\n{res.stderr or res.stdout}")
                return False, "\n".join(logs)
            logs.append(f"✓ '{cmd}' passed.")
        return True, "\n".join(logs)

    def create_worktree(self, branch: str, worktree_dir: Path) -> None:
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)
        res = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=self.repo_root)
        if res.returncode == 0:
            subprocess.run(["git", "branch", "-D", branch], cwd=self.repo_root, capture_output=True)

        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_dir), "HEAD"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
        )

    def cleanup_worktree(self, worktree_dir: Path, branch: str, delete_branch: bool = False) -> None:
        if worktree_dir.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_dir)],
                cwd=self.repo_root,
                capture_output=True,
            )
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

    def invoke_agent(self, task: Task, worktree_dir: Path, dry_run: bool = False) -> tuple[bool, str]:
        """Invokes configured agent command with self-healing feedback loop."""
        prompt = build_task_prompt(task, self.config)
        prompt_file = worktree_dir / ".task-prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")

        if dry_run or not self.config.execution.agent_command:
            print(f"📋 Task prompt generated at {prompt_file}")
            return True, "Dry-run: Prompt generated successfully."

        cmd_template = self.config.execution.agent_command
        if "{prompt_file}" in cmd_template:
            cmd = cmd_template.format(prompt_file=str(prompt_file))
        elif "{prompt}" in cmd_template:
            clean_prompt = prompt.replace('"', '\\"').replace("'", "\\'")
            cmd = cmd_template.replace("{prompt}", clean_prompt)
        else:
            cmd = f"{cmd_template} {prompt_file}"

        max_attempts = self.config.execution.agent_max_attempts
        preflight_log = ""
        for attempt in range(1, max_attempts + 1):
            print(f"🤖 Agent attempt {attempt}/{max_attempts} for {task.canonical_id}...")
            res = subprocess.run(cmd, shell=True, cwd=worktree_dir, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"⚠️ Agent command returned code {res.returncode}: {res.stderr[:200]}")

            preflight_ok, preflight_log = self.run_preflight(worktree_dir)
            if preflight_ok:
                return True, f"Preflight passed on attempt {attempt}."

            print(f"❌ Preflight failed on attempt {attempt}. Retrying with feedback...")
            feedback = f"\n\n## Preflight Failure Feedback (Attempt {attempt})\n{preflight_log}\nPlease fix the issues above."
            prompt_file.write_text(prompt + feedback, encoding="utf-8")

        return False, f"Agent failed after {max_attempts} attempts. Last log:\n{preflight_log}"

    def execute_task(self, task: Task, local_merge: bool = True, dry_run: bool = False) -> WorkerResult:
        """Executes a task in an isolated worktree with preflight verification."""
        branch = f"{self.config.execution.git_branch_prefix}{task.slug}"
        worktree_dir = self.repo_root / ".worktrees" / f"task-{task.id}"
        success = False

        print(f"🚀 Starting worker for {task.canonical_id}: '{task.title}'")
        try:
            worktree_dir.parent.mkdir(parents=True, exist_ok=True)
            self.create_worktree(branch, worktree_dir)

            preflight_ok, preflight_log = self.run_preflight(worktree_dir)
            if not preflight_ok:
                return WorkerResult(task.canonical_id, False, f"Initial preflight failed: {preflight_log}")

            agent_ok, agent_log = self.invoke_agent(task, worktree_dir, dry_run=dry_run)
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

            diff_res = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_dir, capture_output=True, text=True)
            if not diff_res.stdout.strip():
                return WorkerResult(task.canonical_id, False, "No modifications produced by worker.")

            subprocess.run(["git", "add", "-A"], cwd=worktree_dir, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"feat({task.canonical_id.lower()}): {task.title}"],
                cwd=worktree_dir,
                check=True,
            )

            if local_merge:
                with MERGE_LOCK:
                    subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True, capture_output=True)
                    subprocess.run(["git", "merge", "--squash", branch], cwd=self.repo_root, check=True, capture_output=True)
                    self.queue.complete_task(task)
                    subprocess.run(
                        ["git", "commit", "-m", f"feat({task.canonical_id.lower()}): {task.title}"],
                        cwd=self.repo_root,
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
                print(f"⚠️ Worker stalled. Preserved worktree at {worktree_dir} for human rescue ('spec-ops rescue {task.canonical_id}').")
            else:
                self.cleanup_worktree(worktree_dir, branch, delete_branch=dry_run or local_merge)
