"""Unit tests for ArchitecturalReconciler, AutonomousTaskSlicer, and InferenceCurator."""

from __future__ import annotations

from pathlib import Path

from spec_ops.backlog.inference_curator import InferenceCurator
from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.backlog.reconciler import (
    ArchitecturalReconciler,
    ReconciliationChange,
    ReconciliationDiff,
)
from spec_ops.backlog.slicer import AutonomousTaskSlicer
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.prd.manager import PRDManager
from spec_ops.scaffold.init import init_project


def test_reconciler_diff_summary():
    diff_empty = ReconciliationDiff(task_id="TASK-0001")
    assert not diff_empty.has_changes
    assert "No architectural drift detected" in diff_empty.diff_summary

    diff_changes = ReconciliationDiff(
        task_id="TASK-0002",
        changes=[
            ReconciliationChange(
                change_type="superseded_adr",
                target="ADR-0001 -> ADR-0002",
                details="Replaced citation",
            )
        ],
    )
    assert diff_changes.has_changes
    assert "[SUPERSEDED_ADR]" in diff_changes.diff_summary


def test_reconciler_transitive_supersession(tmp_path: Path):
    init_project(tmp_path, name="TransitiveTest")
    adrs_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)

    # ADR-0001 superseded by ADR-0002
    (adrs_dir / "adr-0001.md").write_text(
        "---\nid: '0001'\nsuperseded_by: '0002'\n---\n# ADR-0001\n",
        encoding="utf-8",
    )
    # ADR-0002 superseded by ADR-0003
    (adrs_dir / "adr-0002.md").write_text(
        "---\nid: '0002'\nsuperseded_by: 'ADR-0003'\n---\n# ADR-0002\n",
        encoding="utf-8",
    )

    reconciler = ArchitecturalReconciler(tmp_path)
    mapping = reconciler.discover_superseded_adrs()
    assert mapping.get("ADR-0001") == "ADR-0003"
    assert mapping.get("ADR-0002") == "ADR-0003"


def test_reconciler_module_replacement_matching(tmp_path: Path):
    init_project(tmp_path, name="ModuleMatchTest")
    reconciler = ArchitecturalReconciler(tmp_path)

    codebase = {
        "src/spec_ops/backlog/active_queue.py": tmp_path
        / "src"
        / "spec_ops"
        / "backlog"
        / "active_queue.py",
        "src/spec_ops/core/service.py": tmp_path
        / "src"
        / "spec_ops"
        / "core"
        / "service.py",
    }

    # 1. Exact stem match across other directories
    match1 = reconciler.find_module_replacement(
        "src/spec_ops/legacy/service.py", codebase
    )
    assert match1 == "src/spec_ops/core/service.py"

    # 2. Fuzzy match
    match2 = reconciler.find_module_replacement(
        "src/spec_ops/backlog/actv_queue.py", codebase
    )
    assert match2 == "src/spec_ops/backlog/active_queue.py"

    # 3. Strip prefix (legacy_, old_, deprecated_)
    match3 = reconciler.find_module_replacement(
        "src/spec_ops/backlog/legacy_active_queue.py", codebase
    )
    assert match3 == "src/spec_ops/backlog/active_queue.py"

    # 4. Unknown returns None
    assert (
        reconciler.find_module_replacement("src/unknown/nonexistent.py", codebase)
        is None
    )


def test_slicer_estimation_and_needs_slicing(tmp_path: Path):
    init_project(tmp_path, name="SlicerEstimateTest")
    config = load_config(root_dir=tmp_path)
    slicer = AutonomousTaskSlicer(config)

    # Explicit marker
    t1 = Task(id="1", title="T1", body="estimated_lines: 480", target_bc="core")
    assert slicer.estimate_task_lines(t1) == 480
    assert slicer.needs_slicing(t1)

    # Explicit >500 lines mention
    t2 = Task(
        id="2",
        title="T2",
        body="This task will exceed 500 lines during implementation.",
        target_bc="core",
    )
    assert slicer.estimate_task_lines(t2) == 600
    assert slicer.needs_slicing(t2)

    # Multi-BC
    t3 = Task(
        id="3",
        title="T3",
        body="Short body",
        target_bc="backlog, worker",
    )
    assert slicer.touches_multiple_bounded_contexts(t3)
    assert slicer.needs_slicing(t3)

    # Small single-BC task
    t4 = Task(id="4", title="T4", body="Simple task", target_bc="core")
    assert slicer.estimate_task_lines(t4) == 250
    assert not slicer.needs_slicing(t4)


def test_slicer_write_and_priority_update(tmp_path: Path):
    init_project(tmp_path, name="SlicerWriteTest")
    config = load_config(root_dir=tmp_path)
    slicer = AutonomousTaskSlicer(config)

    proposed_dir = config.backlog_dir / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0099-oversized.md"

    body = """# Oversized Feature

## Checkable Outcomes
1. Outcome Alpha
2. Outcome Beta
3. Outcome Gamma
"""
    task = Task(
        id="0099",
        title="Oversized Feature",
        status="Proposed",
        target_bc="core",
        body=body,
        file_path=task_file,
    )
    write_task_file(task)

    # Setup PRIORITY.md with parent task
    priority_file = config.backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog\n\n- **TASK-0099 (Proposed)**: [`0099-oversized`](proposed/0099-oversized.md)\n",
        encoding="utf-8",
    )

    slice_res = slicer.slice_task(task, include_spike=True)
    paths = slicer.write_sliced_tasks(slice_res, task)

    assert len(paths) >= 2
    assert not task_file.exists()

    content = priority_file.read_text(encoding="utf-8")
    assert "TASK-0099" not in content
    assert slice_res.spike_task.canonical_id in content


def test_inference_curator_dry_run_non_mutating(tmp_path: Path):
    init_project(tmp_path, name="DryRunTest")
    config = load_config(root_dir=tmp_path)

    # Add a proposed task with stale ADR
    proposed_dir = config.backlog_dir / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0050-drifted.md"

    task = Task(
        id="0050",
        title="Drifted Task",
        status="Proposed",
        governing_adrs=["ADR-0003"],
        target_bc="core",
        body="Task body referencing ADR-0003.",
        file_path=task_file,
    )
    write_task_file(task)

    # Mark ADR-0003 superseded
    reg = tmp_path / "docs" / "project" / "adrs" / "REGISTRY.md"
    reg.write_text(
        "| ADR-0003 | Title | Superseded (by ADR-0010) | 2026-09-29 |\n",
        encoding="utf-8",
    )

    curator = InferenceCurator(config)
    res = curator.curate(dry_run=True)

    assert res.dry_run
    assert "DRY RUN" in res.diff_output
    assert "ADR-0003 -> ADR-0010" in res.diff_output

    # Verify task file on disk was NOT mutated
    disk_task = task_file.read_text(encoding="utf-8")
    assert "ADR-0003" in disk_task
    assert "ADR-0010" not in disk_task
    assert not any("0050" in p.name for p in config.backlog_dir.glob("refined/*.md"))
    assert task_file.exists()
