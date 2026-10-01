"""Autonomous task claim gate with dependency resolution, DoR validation, and contract hydration."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from ..backlog.queue import BacklogQueue, write_task_file
from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..core.parser import extract_frontmatter
from ..prd.lifecycle import PRDLifecycleManager
from .worktree import create_worktree


class DoRValidationError(Exception):
    """Raised when a task fails Definition of Ready (DoR) gate checks."""


def validate_definition_of_ready(task: Task, config: SpecOpsConfig) -> tuple[bool, list[str]]:
    """Verifies that a task meets all Definition of Ready (DoR) gate criteria."""
    errors: list[str] = []

    # 1. Governing PRD link verification
    if not task.governing_prds:
        errors.append("Task must link to at least one accepted PRD.")
    else:
        prd_mgr = PRDLifecycleManager(config)
        for prd_ref in task.governing_prds:
            prd_file = prd_mgr.find_prd_file(prd_ref)
            if config.prd_dir.exists() and not prd_file:
                errors.append(f"Governing PRD '{prd_ref}' could not be located under {config.prd_dir}.")
            elif prd_file:
                meta, _ = extract_frontmatter(prd_file.read_text(encoding="utf-8"))
                status = str(meta.get("status", "")).strip().lower()
                parent_stage = prd_file.parent.name.lower()
                if status not in ("accepted", "shipped") and parent_stage not in ("accepted", "shipped"):
                    errors.append(f"Governing PRD '{prd_ref}' is in '{parent_stage}' stage; must be accepted.")

    # 2. Governing ADRs link verification
    if not task.governing_adrs:
        errors.append("Task must cite governing ADRs.")
    else:
        adrs_dir = Path(config.project.docs_dir) / "adrs"
        if not adrs_dir.is_absolute():
            adrs_dir = config.root_dir / adrs_dir
        if adrs_dir.exists():
            for adr_ref in task.governing_adrs:
                clean_num = adr_ref.upper().replace("ADR-", "").lstrip("0")
                target_stem = clean_num.zfill(4)
                found = any(
                    target_stem in p.stem.upper() or adr_ref.upper() in p.name.upper()
                    for p in adrs_dir.rglob("*.md")
                )
                if not found:
                    errors.append(f"Governing ADR '{adr_ref}' could not be located under {adrs_dir}.")

    # 3. Executable Gherkin scenarios / acceptance criteria verification
    has_gherkin = False
    if task.governing_stories:
        stories_dir = Path(config.project.docs_dir) / "user_stories"
        if not stories_dir.is_absolute():
            stories_dir = config.root_dir / stories_dir
        if stories_dir.exists():
            for story_ref in task.governing_stories:
                clean_s = story_ref.upper().replace("US-", "").lstrip("0")
                target_stem = clean_s.zfill(4)
                matches = [
                    p for p in stories_dir.rglob("*.md")
                    if target_stem in p.name.upper() or story_ref.upper() in p.name.upper()
                ]
                for match in matches:
                    text = match.read_text(encoding="utf-8")
                    if "Scenario:" in text or ("Given " in text and "When " in text and "Then " in text):
                        has_gherkin = True
                        break
                if matches and not has_gherkin:
                    has_gherkin = True
        else:
            has_gherkin = True

    if not has_gherkin:
        # Check if task specification body contains Gherkin scenarios directly
        if "Scenario:" in task.body or ("Given " in task.body and "When " in task.body and "Then " in task.body):
            has_gherkin = True

    if not has_gherkin:
        errors.append("Task must link to executable Gherkin scenarios or specify acceptance criteria.")

    return len(errors) == 0, errors


def hydrate_task_prompt(task: Task, config: SpecOpsConfig) -> str:
    """Hydrates an unambiguous machine-readable task contract into .task-prompt.md."""
    preflight_chain = "uv lock --check && uv run pytest && uv run spec-ops health"
    limit = getattr(config.architecture, "file_length_limit", 500)
    bc = task.target_bc or "core"
    adrs = ", ".join(task.governing_adrs) or "None"
    prds = ", ".join(task.governing_prds) or "None"
    stories = ", ".join(task.governing_stories) or "None"

    lines = [
        f"# Task: {task.canonical_id} — {task.title}",
        "",
        "## Architectural Context",
        f"- Target Bounded Context: {bc}",
        f"- Governing ADRs: {adrs}",
        f"- Governing PRDs: {prds}",
        f"- Governing Stories: {stories}",
        f"- File Length Invariant: Every new or edited source file must contain fewer than {limit} lines (500-line file length limit invariant governed by ADR-0002).",
        "- Testing Invariant: Features must be verified blackbox style through public entry points without private backdoors (blackbox frontdoor verification rules with zero private mocks governed by ADR-0003).",
        "- Backlog Isolation: Files under docs/project/backlog/ must not be modified on feature branches. Accidental edits will be intercepted and discarded (ADR-0005).",
        "- Dependency Immutability Invariant: You must NOT edit `pyproject.toml` or `uv.lock` unless `allows_dependencies: true` is explicitly declared in task frontmatter (US-0111). Modifying `pyproject.toml` without authorization triggers an immediate security failure. Do not edit `pyproject.toml` for `[tool.mutmut]`; mutation coverage already scans `src/spec_ops/`.",
    ]

    from ..rescue.memory import format_failure_memory_prompt

    neg_block = format_failure_memory_prompt(task)
    if neg_block.strip():
        lines.append("")
        lines.append(neg_block.strip())

    lines.extend([
        "",
        "## Task Specification",
        task.body.strip(),
        "",
        "## Acceptance Criteria & Preflight",
        f"Your modifications must pass the exact preflight command chain: `{preflight_chain}`",
        "Ensure all tests pass cleanly before completing.",
    ])
    return "\n".join(lines) + "\n"


def initialize_worktree(
    repo_root: Path,
    task: Task,
    config: SpecOpsConfig,
    branch: str | None = None,
) -> Path:
    """Provisions isolated worktree and hydrates .task-prompt.md contract."""
    target_branch = branch or f"task/{task.canonical_id}"
    clean_id = task.canonical_id.lower().replace("task-", "")
    worktree_dir = repo_root / ".worktrees" / f"task-{clean_id}"

    create_worktree(repo_root, target_branch, worktree_dir)

    prompt_content = hydrate_task_prompt(task, config)
    prompt_file = worktree_dir / ".task-prompt.md"
    prompt_file.write_text(prompt_content, encoding="utf-8")

    return worktree_dir


class TaskClaimer:
    """Autonomous task claim gate with dependency resolution and DoR verification."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.repo_root = config.root_dir.resolve()
        self.backlog_dir = config.backlog_dir.resolve()
        self.queue = BacklogQueue(self.backlog_dir)

    def claim_auto(self, claimant: str = "") -> dict[str, Any] | None:
        """Evaluates PRIORITY.md in strict priority order and claims first ready unblocked task."""
        from ..backlog.lock import BacklogLock, recover_transactions

        with BacklogLock(self.repo_root).acquire():
            recover_transactions(self.repo_root)
            priority_file = self.backlog_dir / "PRIORITY.md"
            if not priority_file.exists():
                print("PRIORITY.md not found in backlog.", file=sys.stderr)
                return None

            all_tasks = {t.canonical_id: t for t in self.queue.list_all_tasks()}
            completed_ids = self.queue.get_completed_task_ids()

            priority_lines = priority_file.read_text(encoding="utf-8").splitlines()
            candidate_ids: list[str] = []
            for line in priority_lines:
                m = re.search(r"TASK-0*(\d+)", line, re.IGNORECASE)
                if m:
                    cid = f"TASK-{m.group(1).zfill(4)}"
                    if cid not in candidate_ids:
                        candidate_ids.append(cid)

            for cid in candidate_ids:
                task = all_tasks.get(cid)
                if not task:
                    continue
                if task.status != "Refined":
                    continue
                if task.claimed_by:
                    continue

                unsatisfied = []
                for dep in task.dependencies:
                    dep_num = dep.split("-")[-1]
                    dep_cid = f"TASK-{dep_num.zfill(4)}" if dep_num.isdigit() else dep
                    if dep_cid not in completed_ids:
                        unsatisfied.append(dep)

                if unsatisfied:
                    print(
                        f"Task {task.canonical_id} skipped: unsatisfied dependencies ({', '.join(unsatisfied)})",
                        file=sys.stderr,
                    )
                    continue

                dor_ok, dor_errors = validate_definition_of_ready(task, self.config)
                if not dor_ok:
                    print(
                        f"Task {task.canonical_id} skipped: failed Definition of Ready ({'; '.join(dor_errors)})",
                        file=sys.stderr,
                    )
                    continue

                # Selected task meets all gates
                branch = f"task/{task.canonical_id}"
                clean_id = task.canonical_id.lower().replace("task-", "")
                worktree_dir = self.repo_root / ".worktrees" / f"task-{clean_id}"

                initialize_worktree(self.repo_root, task, self.config, branch=branch)

                worker_name = claimant or os.environ.get("SPECOPS_WORKER_ID") or os.environ.get("SPECOPS_CLAIMANT") or "spec-ops-worker"
                task.claimed_by = worker_name
                task.branch = branch
                try:
                    write_task_file(task)
                except Exception:
                    pass

                metadata = {
                    "task_id": task.canonical_id,
                    "title": task.title,
                    "status": task.status,
                    "target_bc": task.target_bc or "core",
                    "branch": branch,
                    "worktree_dir": str(worktree_dir),
                    "dependencies": task.dependencies,
                    "governing_adrs": task.governing_adrs,
                    "governing_prds": task.governing_prds,
                    "governing_stories": task.governing_stories,
                }
                return metadata

            return None

    def claim_task(self, task_id: str, claimant: str = "") -> dict[str, Any] | None:
        """Claims a specific task by ID if dependencies and DoR are satisfied."""
        from ..backlog.lock import BacklogLock, recover_transactions

        with BacklogLock(self.repo_root).acquire():
            recover_transactions(self.repo_root)
            clean_num = task_id.upper().replace("TASK-", "").lstrip("0")
            cid = f"TASK-{clean_num.zfill(4)}" if clean_num.isdigit() else task_id.upper()

            all_tasks = {t.canonical_id: t for t in self.queue.list_all_tasks()}
            task = all_tasks.get(cid)
            if not task:
                print(f"Task {cid} not found in backlog.", file=sys.stderr)
                return None

            completed_ids = self.queue.get_completed_task_ids()
            unsatisfied = []
            for dep in task.dependencies:
                dep_num = dep.split("-")[-1]
                dep_cid = f"TASK-{dep_num.zfill(4)}" if dep_num.isdigit() else dep
                if dep_cid not in completed_ids:
                    unsatisfied.append(dep)

            if unsatisfied:
                print(
                    f"Task {task.canonical_id} skipped: unsatisfied dependencies ({', '.join(unsatisfied)})",
                    file=sys.stderr,
                )
                return None

            dor_ok, dor_errors = validate_definition_of_ready(task, self.config)
            if not dor_ok:
                print(
                    f"Task {task.canonical_id} skipped: failed Definition of Ready ({'; '.join(dor_errors)})",
                    file=sys.stderr,
                )
                return None

            branch = f"task/{task.canonical_id}"
            clean_id = task.canonical_id.lower().replace("task-", "")
            worktree_dir = self.repo_root / ".worktrees" / f"task-{clean_id}"

            initialize_worktree(self.repo_root, task, self.config, branch=branch)

            worker_name = claimant or os.environ.get("SPECOPS_WORKER_ID") or os.environ.get("SPECOPS_CLAIMANT") or "spec-ops-worker"
            task.claimed_by = worker_name
            task.branch = branch
            try:
                write_task_file(task)
            except Exception:
                pass

            return {
                "task_id": task.canonical_id,
                "title": task.title,
                "status": task.status,
                "target_bc": task.target_bc or "core",
                "branch": branch,
                "worktree_dir": str(worktree_dir),
                "dependencies": task.dependencies,
                "governing_adrs": task.governing_adrs,
                "governing_prds": task.governing_prds,
                "governing_stories": task.governing_stories,
            }
