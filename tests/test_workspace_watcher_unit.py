"""Unit tests for workspace file watcher and incremental graph invalidator.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0011, ADR-0015; PRD-0005; US-0059, US-0060.
Target Bounded Context: graph. High mutation coverage (>80%).
"""

from __future__ import annotations

import io
import json
import signal
from pathlib import Path

import pytest

from spec_ops.core.cache import compute_cache_checksum
from spec_ops.graph.workspace_watcher import (
    GraphChangeEvent,
    IncrementalGraphInvalidator,
    WorkspaceGraphWatcher,
)
from spec_ops.scaffold.init import init_project


def _setup_repo(tmp_path: Path) -> Path:
    init_project(tmp_path, name="WatcherUnitTestRepo")
    docs = tmp_path / "docs" / "project"
    (docs / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (docs / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (docs / "backlog" / "refined").mkdir(parents=True, exist_ok=True)
    (docs / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)

    (docs / "user_stories" / "PERSONAS.md").write_text(
        "# Personas\n\n## 1. Alex — Architect\n- **Role**: Architect\n- **Pain Points**: Drift\n",
        encoding="utf-8",
    )
    (docs / "product" / "accepted" / "prd-0001-engine.md").write_text(
        "---\nid: '0001'\ntitle: Engine PRD\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Compile sub-10ms\n",
        encoding="utf-8",
    )
    (docs / "adrs" / "accepted" / "adr-0001-cache.md").write_text(
        "# ADR-0001: Cache\n\n## Status\nAccepted\n## Context\nContext\n## Decision\nDecide\n## Consequences\nGood\n",
        encoding="utf-8",
    )
    (docs / "user_stories" / "accepted" / "us-0001-speed.md").write_text(
        "---\nid: '0001'\ntitle: Speed Story\nstatus: Accepted\npersona: Alex\ngoverning_prd: PRD-0001\n---\n# Story\n",
        encoding="utf-8",
    )
    (docs / "backlog" / "refined" / "TASK-0001.md").write_text(
        "---\nid: '0001'\ntitle: Task 1 Title\nstatus: Refined\ndependencies: []\ngoverning_adrs: [ADR-0001]\ngoverning_prds: [PRD-0001]\ngoverning_stories: [US-0001]\n---\n# Task 1\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "sample.py").write_text("# initial python code\n", encoding="utf-8")
    return tmp_path


def test_graph_change_event_post_init_and_to_dict() -> None:
    evt = GraphChangeEvent("modified", "docs/test.md", "TASK-0001", "sha123", 4.5, 1)
    d = evt.to_dict()
    assert d["event"] == "modified"
    assert d["path"] == "docs/test.md"
    assert d["entity_id"] == "TASK-0001"
    assert d["sha256"] == "sha123"
    assert d["duration_ms"] == 4.5
    assert d["invalidated"] == 1
    assert "timestamp" in d and len(d["timestamp"]) > 0


def test_load_cache_missing_builds_cold_cache(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    cache_path = tmp_path / ".specops" / "cache" / "graph.json"
    if cache_path.exists():
        cache_path.unlink()

    inv = IncrementalGraphInvalidator(tmp_path)
    payload = inv.load_cache()
    assert cache_path.exists()
    assert payload.get("version") == 1
    assert len(payload.get("entities", {})) >= 4
    assert payload.get("checksum") == compute_cache_checksum(payload)


def test_load_cache_corrupt_falls_back(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    cache_path = tmp_path / ".specops" / "cache" / "graph.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{corrupt-json", encoding="utf-8")

    inv = IncrementalGraphInvalidator(tmp_path)
    payload = inv.load_cache()
    assert payload.get("version") == 1
    assert len(payload.get("entities", {})) >= 4


def test_invalidate_file_unchanged_returns_unchanged(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    inv = IncrementalGraphInvalidator(tmp_path)
    inv.load_cache()

    task_file = tmp_path / "docs" / "project" / "backlog" / "refined" / "TASK-0001.md"
    evt = inv.invalidate_file(task_file)
    assert evt["event"] == "unchanged"
    assert evt["invalidated"] == 0
    assert evt["entity_id"] == "TASK-0001"


def test_invalidate_file_modified_task(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    inv = IncrementalGraphInvalidator(tmp_path)
    inv.load_cache()

    task_file = tmp_path / "docs" / "project" / "backlog" / "refined" / "TASK-0001.md"
    task_file.write_text(
        "---\nid: '0001'\ntitle: Brand New Title\nstatus: Ready\ndependencies: []\n---\n# New Content\n",
        encoding="utf-8",
    )
    evt = inv.invalidate_file(task_file)
    assert evt["event"] == "modified"
    assert evt["invalidated"] == 1
    assert evt["entity_id"] == "TASK-0001"

    cache = inv.load_cache()
    rel = "docs/project/backlog/refined/TASK-0001.md"
    assert cache["entities"][rel]["data"]["title"] == "Brand New Title"
    assert cache["entities"][rel]["data"]["status"] == "Ready"


def test_invalidate_file_deleted_task(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    inv = IncrementalGraphInvalidator(tmp_path)
    inv.load_cache()

    task_file = tmp_path / "docs" / "project" / "backlog" / "refined" / "TASK-0001.md"
    task_file.unlink()
    evt = inv.invalidate_file(task_file)
    assert evt["event"] == "deleted"
    assert evt["invalidated"] == 1
    assert evt["entity_id"] == "TASK-0001"

    cache = inv.load_cache()
    rel = "docs/project/backlog/refined/TASK-0001.md"
    assert rel not in cache["entities"]


def test_invalidate_file_non_existent_and_not_in_cache(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    inv = IncrementalGraphInvalidator(tmp_path)
    inv.load_cache()

    dummy = tmp_path / "docs" / "project" / "backlog" / "refined" / "nonexistent.md"
    evt = inv.invalidate_file(dummy)
    assert evt["event"] == "ignored"
    assert evt["invalidated"] == 0


def test_invalidate_code_file_under_src(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    inv = IncrementalGraphInvalidator(tmp_path)
    inv.load_cache()

    py_file = tmp_path / "src" / "sample.py"
    py_file.write_text("# modified python code line\n", encoding="utf-8")
    evt = inv.invalidate_file(py_file)
    assert evt["event"] == "modified"
    assert evt["invalidated"] == 1
    assert evt["entity_id"] == "code:src/sample.py"

    cache = inv.load_cache()
    assert "src/sample.py" in cache.get("file_hashes", {})


def test_invalidate_unknown_doc_file_ignored(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    inv = IncrementalGraphInvalidator(tmp_path)
    inv.load_cache()

    doc_file = tmp_path / "docs" / "project" / "REGISTRY.md"
    doc_file.write_text("# Registry\n", encoding="utf-8")
    evt = inv.invalidate_file(doc_file)
    assert evt["event"] == "ignored"
    assert evt["invalidated"] == 0


def test_invalidate_story_and_prd_and_adr(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    inv = IncrementalGraphInvalidator(tmp_path)
    inv.load_cache()

    prd_file = tmp_path / "docs" / "project" / "product" / "accepted" / "prd-0001-engine.md"
    prd_file.write_text("---\nid: '0001'\ntitle: New PRD Title\nstatus: Accepted\n---\n# Content\n", encoding="utf-8")
    evt_prd = inv.invalidate_file(prd_file)
    assert evt_prd["event"] == "modified"
    assert evt_prd["entity_id"] == "PRD-0001"

    story_file = tmp_path / "docs" / "project" / "user_stories" / "accepted" / "us-0001-speed.md"
    story_file.write_text("---\nid: '0001'\ntitle: New Story Title\nstatus: Accepted\npersona: Alex\n---\n# Story\n", encoding="utf-8")
    evt_story = inv.invalidate_file(story_file)
    assert evt_story["event"] == "modified"
    assert evt_story["entity_id"] == "US-0001"

    adr_file = tmp_path / "docs" / "project" / "adrs" / "accepted" / "adr-0001-cache.md"
    adr_file.write_text("# ADR-0001: New Cache ADR\n\n## Status\nAccepted\n## Context\nContext\n## Decision\nDecide\n## Consequences\nConsequences\n", encoding="utf-8")
    evt_adr = inv.invalidate_file(adr_file)
    assert evt_adr["event"] == "modified"
    assert evt_adr["entity_id"] == "ADR-0001"


def test_workspace_graph_watcher_scan_once(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    captured_events: list[dict[str, Any]] = []
    out = io.StringIO()

    watcher = WorkspaceGraphWatcher(
        tmp_path,
        interval=0.01,
        debounce_ms=0.0,
        json_output=True,
        out_stream=out,
        on_event=lambda e: captured_events.append(e),
    )

    # Initial scan baseline
    init_evts = watcher.scan_once()
    assert len(init_evts) >= 1

    # Modify a file
    task_file = tmp_path / "docs" / "project" / "backlog" / "refined" / "TASK-0001.md"
    task_file.write_text(
        "---\nid: '0001'\ntitle: Modified In Watcher\nstatus: Refined\ndependencies: []\n---\n# Task\n",
        encoding="utf-8",
    )

    evts = watcher.scan_once()
    assert len(evts) == 1
    assert evts[0]["entity_id"] == "TASK-0001"
    assert len(captured_events) >= 2
    assert "TASK-0001" in out.getvalue()


def test_workspace_graph_watcher_run_max_iterations(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    out = io.StringIO()
    watcher = WorkspaceGraphWatcher(
        tmp_path,
        interval=0.01,
        debounce_ms=0.0,
        json_output=False,
        out_stream=out,
    )
    watcher.start()
    # Modify a file after start
    task_file = tmp_path / "docs" / "project" / "backlog" / "refined" / "TASK-0001.md"
    task_file.write_text(
        "---\nid: '0001'\ntitle: Run Max Iterations Test\nstatus: Refined\ndependencies: []\n---\n# Content\n",
        encoding="utf-8",
    )
    code = watcher.run(max_iterations=1)
    assert code == 0
    assert "[GRAPH_SYNC]" in out.getvalue()


def test_workspace_graph_watcher_signal_stop(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    watcher = WorkspaceGraphWatcher(tmp_path, interval=0.05)
    watcher.start()
    assert not watcher._stop_event.is_set()
    watcher.stop()
    assert watcher._stop_event.is_set()


def test_cli_graph_watch_command_handler(tmp_path: Path) -> None:
    _setup_repo(tmp_path)
    import argparse
    from spec_ops.cli.graph_handler import handle_graph_command
    from spec_ops.config.models import SpecOpsConfig

    config = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(
        graph_action="watch",
        dir=str(tmp_path),
        interval=0.01,
        debounce_ms=0.0,
        json=True,
        event_stream=False,
        once=True,
        max_iterations=1,
    )
    code = handle_graph_command(args, config)
    assert code == 0
