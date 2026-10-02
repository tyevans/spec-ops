"""Blackbox frontdoor verification for TASK-0232: Decouple Core from Backlog.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path
import pytest

from spec_ops.backlog import (
    ProposeTask,
    RefineTask,
    TaskDecider,
    TaskProposed,
    TaskRefined,
    TaskState,
    task_id_to_uuid,
)
from spec_ops.config.loader import load_config
from spec_ops.core.event_store import (
    SQLiteEventLedger,
    append_events,
    get_stream,
    project_task_event_to_filesystem,
    replay_task_state,
)
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_core_event_store_has_no_backlog_imports():
    """Verify that src/spec_ops/core/event_store.py contains zero imports of spec_ops.backlog."""
    event_store_file = Path("src/spec_ops/core/event_store.py")
    assert event_store_file.is_file(), "event_store.py must exist"

    code = event_store_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    backlog_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "backlog" in alias.name:
                    backlog_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "backlog" in mod:
                backlog_imports.append(mod)

    assert not backlog_imports, f"Found illegal backlog imports in core/event_store.py: {backlog_imports}"


def test_core_to_backlog_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from core -> backlog."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    core_backlog_violations = [
        v for v in violations
        if v.get("source") == "core" and v.get("target") == "backlog"
    ]
    assert not core_backlog_violations, f"Active core -> backlog violations detected: {core_backlog_violations}"


def test_event_store_lifecycle_and_projection_via_dependency_inversion(tmp_path: Path):
    """Verify event store persistence and synchronous filesystem projection without direct coupling."""
    db_file = tmp_path / "events.db"
    backlog_dir = tmp_path / "docs" / "project" / "backlog"
    backlog_dir.mkdir(parents=True)

    ledger = SQLiteEventLedger(db_path=db_file, project_root=tmp_path, sync_projection=True)

    task_id = "TASK-0999"
    uid = task_id_to_uuid(task_id)
    evt1 = TaskProposed(
        aggregate_id=uid,
        task_id=task_id,
        title="Decoupled Core Event Store Test",
        target_bc="core",
    )
    evt2 = TaskRefined(aggregate_id=uid, task_id=task_id)

    persisted = ledger.append_events(task_id, [evt1, evt2])
    assert len(persisted) == 2

    # Verify filesystem projection into backlog markdown
    proposed_dir = backlog_dir / "proposed"
    refined_dir = backlog_dir / "refined"
    assert refined_dir.is_dir(), "Refined directory should be created by projection"
    projected_files = list(refined_dir.glob("*.md"))
    assert len(projected_files) == 1, "Projected task markdown should exist in refined/"
    assert "0999" in projected_files[0].name

    # Verify stream retrieval
    stream = ledger.get_stream(task_id)
    assert len(stream) == 2
    assert stream[0].title == "Decoupled Core Event Store Test"

    # Verify state replaying via dependency inversion
    state = ledger.replay_task_state(task_id)
    assert state.status == "Refined"
    assert state.task_id == task_id
