"""Architectural and specification review engine for autonomous tasks."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task


@dataclass
class ReviewResult:
    """Outcome of an architectural and specification review pass."""

    approved: bool
    feedback: str = ""
    raw_output: str = ""


def build_review_prompt(
    task: Task,
    config: SpecOpsConfig,
    worktree_dir: Path,
    diff_text: str = "",
) -> str:
    """Constructs explicit prompt contract for autonomous architectural reviewer."""
    parts = [
        f"# Architectural & Specification Review: {task.canonical_id} — {task.title}",
        "",
        "## Reviewer Role & Non-Interference Invariants",
        "You are acting as an Autonomous Architectural & Specification Reviewer for SpecOps.",
        "Your mission is to evaluate the code modifications produced in this worktree against the task specification, acceptance criteria, project documentation, and governing ADRs.",
        "",
        "### CRITICAL INVARIANT: CI PREFLIGHT CONCURRENCY",
        "- Automated CI preflight checks (pytest, linters, lockfile checks) are executing concurrently in an independent process.",
        "- Do NOT run test suites, linters, or typecheckers.",
        "- Do NOT report on failing tests, syntax errors, or lint issues that CI preflight covers.",
        "- Focus strictly on: completeness against the task specification, architectural integrity, ADR compliance, and code quality.",
        "- Do NOT modify any source files in the worktree.",
        "",
        "## Task Specification",
        f"- Canonical ID: {task.canonical_id}",
        f"- Title: {task.title}",
        f"- Target Bounded Context: {task.target_bc or 'core'}",
        f"- Governing ADRs: {', '.join(task.governing_adrs) or 'None'}",
        f"- Governing PRDs: {', '.join(task.governing_prds) or 'None'}",
        f"- Governing Stories: {', '.join(task.governing_stories) or 'None'}",
        "",
        "### Task Body & Acceptance Requirements",
        task.body.strip(),
        "",
        "## Architectural Constraints & Invariants",
        f"- File Length Invariant: Every new or edited source file must contain fewer than {config.architecture.file_length_limit} lines (ADR-0002).",
        "- Testing Invariant: Features must be verified blackbox style through public frontdoor entry points without private mock backdoors (ADR-0003).",
        "- Bounded Contexts: Respect domain boundaries and isolate domain logic from infrastructure (ADR-0007).",
        "- Backlog Isolation: Working branches must not modify files under docs/project/ directly (ADR-0005).",
        "",
        "## Changes Under Review",
    ]
    if diff_text.strip():
        parts.extend([
            "```diff",
            diff_text.strip(),
            "```",
        ])
    else:
        parts.append("Inspect the modified files in the worktree directly.")

    parts.extend([
        "",
        "## Evaluation Criteria",
        "1. Completeness: Does the change deliver the entire ask and satisfy all requirements in the task specification?",
        "2. Architectural Alignment: Does the implementation adhere to governing ADRs and project architectural standards?",
        "3. Quality & Maintainability: Are public interfaces clean, idiomatic, well-typed, robust, and avoiding leaky abstractions?",
        "",
        "## Decision Output Format",
        "Conclude your response with a clear status decision:",
        "",
        "If all criteria are met and no changes are needed:",
        "```",
        "STATUS: APPROVED",
        "```",
        "(Optionally followed by a brief summary of architectural strengths)",
        "",
        "If changes, additions, or fixes are needed to satisfy the task or architecture:",
        "```",
        "STATUS: CHANGES_REQUESTED",
        "",
        "## Review Feedback",
        "- [Item 1]: Clear description of what is missing or misaligned and actionable fix instructions.",
        "- [Item 2]: ...",
        "```",
    ])
    return "\n".join(parts)


def parse_review_output(output: str) -> ReviewResult:
    """Parses reviewer response to determine approval or extract actionable feedback."""
    cleaned = output.strip()
    if not cleaned:
        return ReviewResult(
            approved=False,
            feedback="Empty response received from reviewer.",
            raw_output=output,
        )

    # Check for STATUS: APPROVED / CHANGES_REQUESTED
    has_approved = bool(re.search(r"STATUS:\s*APPROVED", cleaned, re.IGNORECASE))
    has_changes_requested = bool(
        re.search(r"STATUS:\s*(CHANGES_REQUESTED|REJECTED)", cleaned, re.IGNORECASE)
    )

    if has_approved and not has_changes_requested:
        return ReviewResult(approved=True, feedback="", raw_output=cleaned)

    if has_changes_requested:
        feedback = ""
        m = re.search(
            r"(?:##\s*Review\s*Feedback|STATUS:\s*(?:CHANGES_REQUESTED|REJECTED))\s*([\s\S]*)",
            cleaned,
            re.IGNORECASE,
        )
        if m:
            feedback = m.group(1).strip()
        if not feedback:
            feedback = cleaned
        return ReviewResult(approved=False, feedback=feedback, raw_output=cleaned)

    # Heuristic fallback: if output explicitly starts or contains approval
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    first_lines = " ".join(lines[:3]).upper()
    if "APPROVED" in first_lines and "CHANGES" not in first_lines:
        return ReviewResult(approved=True, feedback="", raw_output=cleaned)

    feedback_match = re.search(r"##\s*Review\s*Feedback\s*([\s\S]*)", cleaned, re.IGNORECASE)
    feedback = feedback_match.group(1).strip() if feedback_match else cleaned
    return ReviewResult(approved=False, feedback=feedback, raw_output=cleaned)


class TaskReviewEngine:
    """Coordinates autonomous architectural and specification reviews."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config

    def get_git_diff(self, worktree_dir: Path) -> str:
        """Captures working tree diff including tracked modifications and untracked files."""
        tracked_diff = ""
        try:
            diff_res = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=worktree_dir,
                capture_output=True,
                text=True,
            )
            tracked_diff = diff_res.stdout.strip()
        except Exception:
            pass

        untracked: list[str] = []
        try:
            status_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=worktree_dir,
                capture_output=True,
                text=True,
            )
            untracked = [
                line[3:].strip()
                for line in status_res.stdout.splitlines()
                if line.startswith("?? ")
                and not any(
                    line.strip().endswith(p)
                    for p in [".task-prompt.md", ".task-review-prompt.md"]
                )
            ]
        except Exception:
            pass

        parts: list[str] = []
        if tracked_diff:
            if len(tracked_diff) > 50000:
                tracked_diff = (
                    tracked_diff[:50000]
                    + "\n\n... [Diff truncated at 50KB; inspect full worktree directly]"
                )
            parts.append(tracked_diff)
        if untracked:
            parts.append("# Untracked new files:\n" + "\n".join(f"+ {f}" for f in untracked))

        return "\n\n".join(parts)

    def build_prompt(self, task: Task, worktree_dir: Path) -> str:
        """Constructs review prompt for the specified task and worktree."""
        diff_text = self.get_git_diff(worktree_dir)
        return build_review_prompt(task, self.config, worktree_dir, diff_text=diff_text)

    def run_review(
        self,
        task: Task,
        worktree_dir: Path,
        dry_run: bool = False,
        attempt: int = 1,
    ) -> ReviewResult:
        """Executes the reviewer agent and returns a structured ReviewResult."""
        from ..core.agent_cmd import build_agent_cmd

        prompt = self.build_prompt(task, worktree_dir)
        prompt_file = worktree_dir / ".task-review-prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")

        cmd_template = (
            self.config.execution.reviewer_command.strip()
            if getattr(self.config.execution, "reviewer_command", "")
            else self.config.execution.agent_command.strip()
        )

        if dry_run or not cmd_template:
            print(f"📋 Task review prompt generated at {prompt_file}")
            return ReviewResult(
                approved=True,
                feedback="",
                raw_output="Dry-run: Review prompt generated.",
            )

        print(f"🧐 Running task architectural review (Attempt {attempt}) for {task.canonical_id}...")
        env = os.environ.copy()
        env["SPEC_OPS_WORKTREE"] = str(worktree_dir.resolve())
        env["PWD"] = str(worktree_dir.resolve())

        cmd = build_agent_cmd(cmd_template, prompt, prompt_file, continue_session=False)
        res = subprocess.run(
            cmd,
            shell=False,
            cwd=worktree_dir,
            env=env,
            capture_output=True,
            text=True,
        )

        output = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
        if res.returncode != 0 and not output.strip():
            return ReviewResult(
                approved=False,
                feedback=f"Reviewer process failed with exit code {res.returncode}.",
                raw_output=output,
            )

        return parse_review_output(output)
