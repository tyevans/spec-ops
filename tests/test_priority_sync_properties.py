"""Hypothesis property-based tests for Backlog Health and Priority Sync (ADR-0009, TASK-0182)."""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.health import HealthChecker
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project


@st.composite
def task_sync_scenario_strategy(draw: st.DrawFn):
    """Generates random tasks across backlog folders with presence/absence in PRIORITY.md."""
    num_tasks = draw(st.integers(min_value=1, max_value=8))
    task_ids = draw(st.lists(st.integers(min_value=100, max_value=999), min_size=num_tasks, max_size=num_tasks, unique=True))
    folders = ["complete", "refined", "proposed"]
    folder_choices = draw(st.lists(st.sampled_from(folders), min_size=num_tasks, max_size=num_tasks))
    indexed_flags = draw(st.lists(st.booleans(), min_size=num_tasks, max_size=num_tasks))

    tasks = []
    for tid, folder, indexed in zip(task_ids, folder_choices, indexed_flags):
        tasks.append({"id": tid, "folder": folder, "indexed": indexed})
    return tasks


@given(tasks=task_sync_scenario_strategy())
@settings(max_examples=15, deadline=None)
def test_property_unindexed_tasks_strictly_flagged(tmp_path_factory, tasks: list[dict]):
    """Invariant: Every task file on disk must be indexed in PRIORITY.md or priority_sync_ok is False."""
    tmp_path = tmp_path_factory.mktemp("priority_sync_prop")
    init_project(tmp_path, name="PropApp")
    config = load_config(root_dir=tmp_path)
    checker = HealthChecker(config)

    backlog_dir = tmp_path / "docs" / "project" / "backlog"
    priority_file = backlog_dir / "PRIORITY.md"
    priority_content = priority_file.read_text(encoding="utf-8")

    unindexed_expected: list[str] = []

    for t in tasks:
        cid = f"TASK-{t['id']:04d}"
        folder_dir = backlog_dir / t["folder"]
        folder_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{t['id']:04d}-task-{t['id']}.md"
        task_file = folder_dir / file_name
        task_file.write_text(
            f"---\nid: {cid}\ntitle: Task {t['id']}\nstatus: {t['folder'].capitalize()}\n---\n",
            encoding="utf-8",
        )

        if t["indexed"]:
            status_tag = t["folder"].capitalize()
            priority_content += f"\n- **{cid} ({status_tag})**: [`{file_name[:-3]}`]({t['folder']}/{file_name})\n"
        else:
            unindexed_expected.append(cid)

    priority_file.write_text(priority_content, encoding="utf-8")

    ok, errors = checker.check_priority_sync()

    if unindexed_expected:
        assert not ok
        for unindexed_cid in unindexed_expected:
            assert any(unindexed_cid in err and "unindexed in PRIORITY.md" in err for err in errors)
    else:
        assert ok
        assert len(errors) == 0
