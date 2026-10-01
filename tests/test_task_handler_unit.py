"""Unit tests for ergonomic task authoring, ID normalization, and Definition of Ready validation."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spec_ops.backlog.dor import validate_task_dor
from spec_ops.cli.parser import build_parser
from spec_ops.cli.queue_handler import handle_queue_command
from spec_ops.cli.task_handler import (
    append_task_to_priority,
    get_next_task_number,
    handle_task_command,
    normalize_id_list,
    scaffold_task_file,
    slugify_task_title,
)
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task


def test_get_next_task_number_empty(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    assert get_next_task_number(backlog_dir) == 1


def test_get_next_task_number_disk_and_priority(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    proposed = backlog_dir / "proposed"
    proposed.mkdir(parents=True, exist_ok=True)
    (proposed / "0042-some-task.md").write_text("# Task\n", encoding="utf-8")

    assert get_next_task_number(backlog_dir) == 43

    priority = backlog_dir / "PRIORITY.md"
    priority.write_text("- **TASK-0050 (Proposed)**: [`0050-x`](proposed/0050-x.md)\n", encoding="utf-8")
    assert get_next_task_number(backlog_dir) == 51


def test_slugify_task_title():
    assert slugify_task_title("Extract Visualizer Drawer Script") == "extract-visualizer-drawer-script"
    assert slugify_task_title("Fix: Special & Weird / Characters!") == "fix-special-weird-characters"
    assert slugify_task_title("   ---Spaces and Dashes---   ") == "spaces-and-dashes"
    assert slugify_task_title("") == "task"


def test_normalize_id_list():
    assert normalize_id_list(None, "PRD") == []
    assert normalize_id_list([], "PRD") == []
    assert normalize_id_list(["PRD-0001", "PRD-0002"], "PRD") == ["PRD-0001", "PRD-0002"]
    assert normalize_id_list(["1", "2"], "PRD") == ["PRD-0001", "PRD-0002"]
    assert normalize_id_list(["PRD-0001, 2"], "PRD") == ["PRD-0001", "PRD-0002"]
    assert normalize_id_list(["us-3", "US-0004"], "US") == ["US-0003", "US-0004"]
    assert normalize_id_list(["adr-10"], "ADR") == ["ADR-0010"]


def test_append_task_to_priority(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    priority = backlog_dir / "PRIORITY.md"
    priority.write_text("# Backlog Priority\n\n", encoding="utf-8")

    append_task_to_priority(backlog_dir, "TASK-0073", "proposed", "0073-test.md")
    content = priority.read_text(encoding="utf-8")
    assert "- **TASK-0073 (Proposed)**: [`0073-test`](proposed/0073-test.md)" in content

    # Should not duplicate if already present
    append_task_to_priority(backlog_dir, "TASK-0073", "proposed", "0073-test.md")
    assert content.count("TASK-0073") == 1


def test_scaffold_task_file(tmp_path: Path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "PRIORITY.md").write_text("# Priority\n\n", encoding="utf-8")

    cid, path = scaffold_task_file(
        backlog_dir=backlog_dir,
        title="Extract Visualizer Drawer Script",
        target_bc="visualizer",
        governing_prds=["PRD-0001"],
        governing_stories=["US-0002"],
        governing_adrs=["ADR-0001"],
        dependencies=["TASK-0010"],
        stage="proposed",
    )

    assert cid == "TASK-0001"
    assert path.is_file()
    task = parse_task(path)
    assert task.title == "Extract Visualizer Drawer Script"
    assert task.target_bc == "visualizer"
    assert task.governing_prds == ["PRD-0001"]
    assert task.governing_stories == ["US-0002"]
    assert task.governing_adrs == ["ADR-0001"]
    assert task.dependencies == ["TASK-0010"]
    assert task.status == "Proposed"


def test_validate_task_dor(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "project"
    docs_dir.mkdir(parents=True, exist_ok=True)
    cfg = SpecOpsConfig(root_dir=tmp_path)

    # Missing everything
    task_empty = Task(id="0001", title="Empty", status="Proposed")
    ok, errors = validate_task_dor(task_empty, cfg)
    assert ok is False
    assert any("governing ADRs" in e for e in errors)
    assert any("governing story" in e for e in errors)
    assert any("governing PRD" in e for e in errors)
    assert any("target bounded context" in e for e in errors)

    # Scaffold accepted artifacts
    adrs_dir = docs_dir / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "0001-adr.md").write_text("---\nid: '0001'\nstatus: Accepted\n---\n", encoding="utf-8")

    stories_dir = docs_dir / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0002-story.md").write_text("---\nid: '0002'\nstatus: Accepted\n---\n", encoding="utf-8")

    prd_dir = docs_dir / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-prd.md").write_text("---\nid: '0001'\nstatus: Accepted\n---\n", encoding="utf-8")

    # Complete task
    task_valid = Task(
        id="0001",
        title="Valid Task",
        status="Proposed",
        target_bc="core",
        governing_adrs=["ADR-0001"],
        governing_stories=["US-0002"],
        governing_prds=["PRD-0001"],
    )
    ok_valid, errors_valid = validate_task_dor(task_valid, cfg)
    assert ok_valid is True
    assert len(errors_valid) == 0


def test_handle_task_command_dispatcher(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    parser = build_parser()
    cfg = SpecOpsConfig(root_dir=tmp_path)
    (tmp_path / "docs" / "project" / "backlog").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "project" / "backlog" / "PRIORITY.md").write_text("# Priority\n\n", encoding="utf-8")

    # 1. No action
    args_none = argparse.Namespace(task_action=None)
    ret_none = handle_task_command(args_none, cfg, parser)
    assert ret_none == 0

    # 2. Create missing title
    args_no_title = argparse.Namespace(
        task_action="create",
        title=None,
        target_bc=None,
        prd=None,
        story=None,
        adr=None,
        dependencies=None,
        stage="proposed",
        non_interactive=True,
    )
    ret_no_title = handle_task_command(args_no_title, cfg, parser)
    assert ret_no_title == 1

    # 3. Create proposed successfully
    args_create = argparse.Namespace(
        task_action="create",
        title="Extract Visualizer Drawer Script",
        target_bc="visualizer",
        prd=["PRD-0001"],
        story=["US-0002"],
        adr=["ADR-0001"],
        dependencies=["TASK-0005"],
        stage="proposed",
        non_interactive=True,
    )
    ret_create = handle_task_command(args_create, cfg, parser)
    assert ret_create == 0
    out = capsys.readouterr().out
    assert "Created task TASK-0001" in out

    # 4. Create refined failing DoR
    args_refined_fail = argparse.Namespace(
        task_action="create",
        title="Refined Task Missing ADRs",
        target_bc="visualizer",
        prd=["PRD-0001"],
        story=[],
        adr=[],
        dependencies=[],
        stage="refined",
        non_interactive=True,
    )
    ret_fail = handle_task_command(args_refined_fail, cfg, parser)
    assert ret_fail == 1


def test_handle_queue_refine_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    parser = build_parser()
    cfg = SpecOpsConfig(root_dir=tmp_path)
    backlog_dir = tmp_path / "docs" / "project" / "backlog"
    proposed_dir = backlog_dir / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text("# Priority\n\n", encoding="utf-8")

    # 1. Non-existent task
    args_missing = argparse.Namespace(queue_action="refine", task_id="TASK-9999")
    ret_missing = handle_queue_command(args_missing, cfg, parser)
    assert ret_missing == 1

    # 2. Existing task failing DoR
    t_file = proposed_dir / "0025-legacy.md"
    t_file.write_text(
        "---\nid: '0025'\ntitle: Legacy\nstatus: Proposed\n---\n# TASK-0025\n",
        encoding="utf-8",
    )
    priority_file.write_text("- **TASK-0025 (Proposed)**: [`0025-legacy`](proposed/0025-legacy.md)\n", encoding="utf-8")

    args_fail = argparse.Namespace(queue_action="refine", task_id="TASK-0025")
    ret_fail = handle_queue_command(args_fail, cfg, parser)
    assert ret_fail == 1
    out_fail = capsys.readouterr().out
    assert "Definition of Ready (DoR) validation failed" in out_fail

    # 3. Existing task satisfying DoR
    adrs_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "0001-adr.md").write_text("---\nid: '0001'\nstatus: Accepted\n---\n", encoding="utf-8")

    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0002-story.md").write_text(
        "---\nid: '0002'\nstatus: Accepted\npersona: Jordan\n---\nGiven a legacy system\nWhen migrated\nThen success\n",
        encoding="utf-8",
    )

    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-prd.md").write_text("---\nid: '0001'\nstatus: Accepted\ntarget_persona: Jordan\n---\n", encoding="utf-8")

    t_file.write_text(
        """---
id: '0025'
title: Legacy
status: Proposed
target_bc: worker
governing_adrs:
- ADR-0001
governing_stories:
- US-0002
governing_prds:
- PRD-0001
mutation_scope: src/spec_ops/worker
---
# TASK-0025
""",
        encoding="utf-8",
    )

    args_ok = argparse.Namespace(queue_action="refine", task_id="TASK-0025")
    ret_ok = handle_queue_command(args_ok, cfg, parser)
    assert ret_ok == 0
    out_ok = capsys.readouterr().out
    assert "Promoted task TASK-0025 to refined/" in out_ok
    assert not t_file.exists()
    assert (backlog_dir / "refined" / "0025-legacy.md").exists()
