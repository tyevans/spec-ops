"""Generative Hypothesis property tests for BacklogDoctor (ADR-0009).

Asserts that backlog doctor --fix idempotently restores a valid, zero-error state
without data loss across arbitrary corrupted backlog trees.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.doctor import BacklogDoctor
from spec_ops.core.parser import extract_frontmatter, parse_task

# Strategy for valid task IDs (1 to 50)
st_task_num = st.integers(min_value=1, max_value=50)

# Strategy for task stage folder
st_folder = st.sampled_from(["complete", "refined", "proposed"])


@st.composite
def backlog_tree_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generates an arbitrary backlog with a mixture of valid tasks and injected defects."""
    # 1. Distinct task numbers for valid tasks
    num_tasks = draw(st.integers(min_value=1, max_value=6))
    task_nums = draw(st.lists(st_task_num, min_size=num_tasks, max_size=num_tasks, unique=True))

    tasks_data = []
    all_valid_cids = [f"TASK-{n:04d}" for n in task_nums]

    for n in task_nums:
        cid = f"TASK-{n:04d}"
        folder = draw(st_folder)
        status = folder.capitalize()

        # Potential valid dependencies (pointing only to other valid tasks)
        other_cids = [c for c in all_valid_cids if c != cid]
        valid_deps = draw(st.lists(st.sampled_from(other_cids), max_size=2, unique=True)) if other_cids else []

        # Potential injected dangling dependencies (pointing to non-existent tasks)
        has_dangling = draw(st.booleans())
        dangling_deps = [f"TASK-{draw(st.integers(min_value=8000, max_value=9999)):04d}"] if has_dangling else []

        all_deps = valid_deps + dangling_deps
        title = f"Feature Task {n}"
        body = f"# {cid}: {title}\n\nTask implementation details for {cid}.\n"

        # Indexing in PRIORITY.md status
        in_priority = draw(st.booleans())
        # Potential folder drift in PRIORITY.md
        has_drift = draw(st.booleans())
        priority_folder = draw(st_folder) if has_drift else folder

        tasks_data.append(
            {
                "num": n,
                "cid": cid,
                "folder": folder,
                "status": status,
                "valid_deps": valid_deps,
                "all_deps": all_deps,
                "title": title,
                "body": body,
                "in_priority": in_priority,
                "priority_folder": priority_folder,
            }
        )

    # 2. Injected ghost entries in PRIORITY.md
    num_ghosts = draw(st.integers(min_value=0, max_value=2))
    ghost_nums = draw(st.lists(st.integers(min_value=60, max_value=90), min_size=num_ghosts, max_size=num_ghosts, unique=True))
    ghosts = [f"TASK-{g:04d}" for g in ghost_nums]

    return {
        "tasks": tasks_data,
        "valid_cids": set(all_valid_cids),
        "ghosts": ghosts,
    }


def populate_backlog_dir(backlog_dir: Path, data: dict[str, Any]) -> None:
    """Populates the filesystem according to generated backlog data."""
    for f in ("complete", "refined", "proposed"):
        (backlog_dir / f).mkdir(parents=True, exist_ok=True)

    priority_lines = [
        "# Backlog Priority Index",
        "",
        "Strict sequential order of execution for engineering tasks.",
        "",
    ]

    for t in data["tasks"]:
        target_f = backlog_dir / t["folder"]
        task_p = target_f / f"{t['num']:04d}-task-{t['num']}.md"
        deps_yaml = ""
        if t["all_deps"]:
            deps_yaml = "dependencies:\n" + "".join(f"  - {d}\n" for d in t["all_deps"])

        content = (
            "---\n"
            f"id: '{t['num']:04d}'\n"
            f"title: {t['title']}\n"
            f"status: {t['status']}\n"
            f"{deps_yaml}"
            "---\n\n"
            f"{t['body']}"
        )
        task_p.write_text(content, encoding="utf-8")

        if t["in_priority"]:
            pf = t["priority_folder"]
            st_name = pf.capitalize()
            priority_lines.append(f"- **{t['cid']} ({st_name})**: [`{task_p.stem}`]({pf}/{task_p.name})")

    # Add ghost entries to PRIORITY.md
    for g in data["ghosts"]:
        num_str = g.split("-")[-1]
        priority_lines.append(f"- **{g} (Proposed)**: [`{num_str}-ghost`](proposed/{num_str}-ghost.md)")

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text("\n".join(priority_lines) + "\n", encoding="utf-8")


@settings(max_examples=35, deadline=None)
@given(backlog_data=backlog_tree_strategy())
def test_backlog_doctor_idempotent_self_healing_without_data_loss(backlog_data: dict[str, Any]):
    """Hypothesis generative invariant: queue doctor --fix idempotently restores a valid, zero-error state without data loss."""
    with tempfile.TemporaryDirectory() as tmp_str:
        backlog_dir = Path(tmp_str)
        populate_backlog_dir(backlog_dir, backlog_data)

        doctor = BacklogDoctor(backlog_dir)

        # 1. Execute automated self-healing repair
        first_repair_report = doctor.fix()

        # Invariant A: Post-condition zero-error state
        assert first_repair_report.is_healthy, f"Expected clean health after first fix(), got defects: {first_repair_report.defects}"
        assert len(first_repair_report.defects) == 0

        # Invariant B: Re-auditing confirms zero defects
        post_audit = doctor.audit()
        assert post_audit.is_healthy, f"Re-audit failed: {post_audit.defects}"
        assert len(post_audit.defects) == 0

        # Invariant C: Idempotence — second fix() produces 0 remediations and does not alter state
        second_repair_report = doctor.fix()
        assert second_repair_report.is_healthy
        assert second_repair_report.remediated_count == 0
        assert len(second_repair_report.remediations) == 0

        # Invariant D: Zero data loss
        # Every valid task that existed before still exists on disk
        disk_tasks = doctor.discover_disk_tasks()
        assert set(disk_tasks.keys()) == backlog_data["valid_cids"]

        priority_text = doctor.priority_file.read_text(encoding="utf-8")

        for t in backlog_data["tasks"]:
            cid = t["cid"]
            assert cid in disk_tasks
            task_obj, file_path, folder = disk_tasks[cid]

            # Task title and body preserved
            assert task_obj.title == t["title"]
            assert t["body"].strip() in file_path.read_text(encoding="utf-8")

            # Non-dangling dependencies preserved
            assert set(task_obj.dependencies) == set(t["valid_deps"])

            # Task is indexed in PRIORITY.md under its actual folder on disk
            assert f"**{cid}" in priority_text
            assert f"({folder.capitalize()})" in priority_text
            assert f"{folder}/{file_path.name}" in priority_text

        # All ghost entries were eradicated
        for g in backlog_data["ghosts"]:
            assert g not in priority_text
