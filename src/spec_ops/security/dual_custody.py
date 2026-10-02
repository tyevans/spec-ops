"""Dual-custody review sign-off gating and autonomous agent transition enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from .signing import verify_branch_commit_signatures, verify_reviewer_identity

_DEFAULT_TASK_FINDER: Any = None
_DEFAULT_TASK_WRITER: Any = None


def register_default_task_finder(finder: Any) -> None:
    """Registers an external task lookup callback for dependency inversion."""
    global _DEFAULT_TASK_FINDER
    _DEFAULT_TASK_FINDER = finder


def register_default_task_writer(writer: Any) -> None:
    """Registers an external task writer callback for dependency inversion."""
    global _DEFAULT_TASK_WRITER
    _DEFAULT_TASK_WRITER = writer


def is_autonomous_task(task: Task, config: SpecOpsConfig | None = None) -> bool:
    """Determines whether a backlog task was authored/executed by an autonomous agent."""
    if task.claimed_by:
        return True
    if config and config.security and config.security.compliance:
        if config.security.compliance.dual_custody or config.security.compliance.require_signed_commits:
            return True
    if "autonomous worker" in task.body.lower():
        return True
    return False


def evaluate_dual_custody_gate(task: Task, config: SpecOpsConfig | None = None) -> tuple[bool, str]:
    """Enforces dual-custody human sign-off on autonomous agent tasks before completion."""
    if is_autonomous_task(task, config) and not task.signed_off_by:
        return (
            False,
            f"Dual-Custody Gate: Autonomous agent task requires verified human review sign-off. Run 'spec-ops review sign {task.canonical_id} --identity <key-id>'",
        )
    return True, "Dual-custody verification passed."


def record_sign_off(
    task: Task,
    identity: str,
    timestamp: str | None = None,
    task_writer: Any = None,
) -> Task:
    """Records human reviewer sign-off identity and timestamp into task frontmatter."""
    task.signed_off_by = identity
    task.signed_off_at = timestamp or datetime.now(timezone.utc).isoformat()
    if task.file_path and task.file_path.is_file():
        writer = task_writer or _DEFAULT_TASK_WRITER
        if writer is None:
            try:
                import importlib
                bq_mod = importlib.import_module("spec_ops.backlog.queue")
                writer = getattr(bq_mod, "write_task_file", None)
            except Exception:
                writer = None
        if writer:
            writer(task)
    return task


def sign_task_review(
    task_id: str,
    identity: str,
    config: SpecOpsConfig,
    task_finder: Any = None,
    task_writer: Any = None,
) -> tuple[bool, str]:
    """Finds a task, verifies reviewer identity against keyring, and records sign-off."""
    clean_id = task_id.upper()
    if not clean_id.startswith("TASK-") and clean_id.isdigit():
        clean_id = f"TASK-{clean_id.zfill(4)}"

    finder = task_finder or _DEFAULT_TASK_FINDER
    target_task = None
    if finder is not None:
        target_task = finder(clean_id)
    else:
        try:
            import importlib
            bq_mod = importlib.import_module("spec_ops.backlog.queue")
            BacklogQueue = getattr(bq_mod, "BacklogQueue")
            queue = BacklogQueue(config.backlog_dir)
            for t in queue.list_all_tasks():
                if t.canonical_id == clean_id:
                    target_task = t
                    break
        except Exception:
            target_task = None

    if not target_task:
        return False, f"Task {task_id} not found in backlog."

    ok, msg = verify_reviewer_identity(identity, config=config, repo_dir=config.root_dir)
    if not ok:
        return False, msg

    record_sign_off(target_task, identity, task_writer=task_writer)
    return True, f"Task {target_task.canonical_id} review successfully signed by {identity}."


def verify_worker_integration_gates(
    repo_root: Path,
    branch: str,
    task: Task,
    config: SpecOpsConfig,
) -> tuple[bool, str]:
    """Enforces commit signature and dual-custody verification before worker merge."""
    if config.require_signed_commits:
        sig_ok, unsigned_sha, sig_msg = verify_branch_commit_signatures(
            repo_root,
            base_branch="main",
            target_branch=branch,
        )
        if not sig_ok:
            return False, sig_msg

    dc_ok, dc_msg = evaluate_dual_custody_gate(task, config=config)
    if not dc_ok:
        return False, dc_msg

    from ..rescue.handover import assert_handover_excluded_from_git

    handover_ok, handover_msg = assert_handover_excluded_from_git(repo_root, branch=branch)
    if not handover_ok:
        return False, handover_msg

    return True, "All integration gates passed."
