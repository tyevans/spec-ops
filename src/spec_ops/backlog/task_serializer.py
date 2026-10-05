"""Task markdown file serialization preserving frontmatter and metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from ..core.models import Task
from .lock import atomic_write


def write_task_file(task: Task) -> Path:
    """Serializes a task to its file_path preserving frontmatter."""
    meta: dict[str, Any] = {
        "id": task.id,
        "title": task.title,
        "status": task.status,
    }
    if task.dependencies:
        meta["dependencies"] = task.dependencies
    if task.governing_adrs:
        meta["governing_adrs"] = task.governing_adrs
    if task.governing_prds:
        meta["governing_prds"] = task.governing_prds
    if task.governing_stories:
        meta["governing_stories"] = task.governing_stories
    simple_str_fields = [
        "target_bc", "target_release", "pr_url", "claimed_by", "branch",
        "hypothesis", "timebox", "signed_off_by", "signed_off_at",
        "commit_signature_status", "persona", "mutation_scope",
        "completed_at", "claimed_at", "timestamp", "heartbeat_at", "heartbeat", "external_ref",
    ]
    for key in simple_str_fields:
        val = getattr(task, key, "")
        if val:
            meta[key] = val

    if getattr(task, "allows_dependencies", False):
        meta["allows_dependencies"] = True
    if getattr(task, "has_signed_commits", None) is not None:
        meta["has_signed_commits"] = task.has_signed_commits
    if getattr(task, "slice_type", "") and getattr(task, "slice_type", "") != "feat":
        meta["slice_type"] = task.slice_type
    if getattr(task, "unblocked", False):
        meta["unblocked"] = True
    if getattr(task, "expected_lines", 0):
        meta["expected_lines"] = task.expected_lines
    if getattr(task, "pinned", False):
        meta["pinned"] = True
    if getattr(task, "priority_pin", None) is not None:
        meta["priority_pin"] = task.priority_pin
    if getattr(task, "failure_history", None):
        meta["failure_history"] = task.failure_history
    if getattr(task, "blocker", None):
        b = task.blocker
        b_dict = {
            k: v for k, v in [
                ("type", b.type), ("question", b.question), ("raised_by", b.raised_by),
                ("raised_at", b.raised_at), ("spike_id", b.spike_id),
                ("resolution", b.resolution), ("resolved_at", b.resolved_at), ("adr_id", b.adr_id),
            ] if v
        }
        meta["blocker"] = b_dict

    yaml_block = yaml.dump(meta, sort_keys=False).strip()
    clean_body = task.body.strip()
    full_content = f"---\n{yaml_block}\n---\n\n{clean_body}\n"

    atomic_write(task.file_path, full_content)
    return task.file_path
