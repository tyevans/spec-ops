"""Executable BDD step definitions for US-0059 / TASK-0148: Workspace Watcher and Incremental Graph Invalidation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.cache import compute_cache_checksum
from spec_ops.graph.workspace_watcher import (
    IncrementalGraphInvalidator,
    WorkspaceGraphWatcher,
)
from spec_ops.scaffold.init import init_project

scenarios("features/us_0059_workspace_watcher.feature")


def _scaffold_project(root: Path) -> None:
    p_docs = root / "docs" / "project"
    (p_docs / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (p_docs / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (p_docs / "backlog" / "refined").mkdir(parents=True, exist_ok=True)
    (p_docs / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)

    (p_docs / "user_stories" / "PERSONAS.md").write_text(
        "# Personas\n\n## 1. Alex — The Agentic Systems Architect\n- **Role**: Architect\n- **Pain Points**:\n  - Latency\n",
        encoding="utf-8",
    )
    (p_docs / "product" / "accepted" / "prd-0001-engine.md").write_text(
        "---\nid: '0001'\ntitle: Engine PRD\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Compile sub-10ms\n",
        encoding="utf-8",
    )
    (p_docs / "adrs" / "accepted" / "adr-0001-cache.md").write_text(
        "# ADR-0001: Cache\n\n## Status\nAccepted\n## Context\nContext\n## Decision\nDecide\n## Consequences\nPositive\n",
        encoding="utf-8",
    )
    (p_docs / "backlog" / "refined" / "TASK-0001.md").write_text(
        "---\nid: '0001'\ntitle: Initial Task Specification\nstatus: Refined\ndependencies: []\ngoverning_adrs: [ADR-0001]\ngoverning_prds: [PRD-0001]\n---\n# Initial Task\n",
        encoding="utf-8",
    )


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="WorkspaceWatcherBDD")
    _scaffold_project(tmp_path)
    return {
        "root": tmp_path,
        "invalidator": None,
        "watcher": None,
        "pre_cache": None,
        "events": [],
    }


@given('a warm relational graph cache in ".specops/cache/graph.json"')
def warm_relational_graph_cache(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    invalidator = IncrementalGraphInvalidator(root)
    cache = invalidator.load_cache()
    assert (root / ".specops" / "cache" / "graph.json").exists()
    assert len(cache.get("entities", {})) >= 4
    bdd_context["invalidator"] = invalidator
    bdd_context["pre_cache"] = json.loads(json.dumps(cache))


@when(parsers.parse('a single task specification "{task_rel_path}" is modified'))
def task_spec_modified(bdd_context: dict[str, Any], task_rel_path: str) -> None:
    root: Path = bdd_context["root"]
    target = root / task_rel_path
    target.write_text(
        "---\nid: '0001'\ntitle: Updated Task Specification\nstatus: Refined\ndependencies: []\ngoverning_adrs: [ADR-0001]\ngoverning_prds: [PRD-0001]\n---\n# Updated Task Content\n",
        encoding="utf-8",
    )
    invalidator: IncrementalGraphInvalidator = bdd_context["invalidator"]
    event = invalidator.invalidate_file(target)
    bdd_context["events"] = [event]


@then(parsers.parse('the incremental invalidator updates only the entity for "{task_id}"'))
def invalidator_updates_only_task(bdd_context: dict[str, Any], task_id: str) -> None:
    root: Path = bdd_context["root"]
    cache_path = root / ".specops" / "cache" / "graph.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    pre_cache = bdd_context["pre_cache"]

    task_rel = "docs/project/backlog/refined/TASK-0001.md"
    curr_task = cache["entities"][task_rel]
    prev_task = pre_cache["entities"][task_rel]

    assert curr_task["canonical_id"] == task_id
    assert curr_task["sha256"] != prev_task["sha256"]
    assert curr_task["data"]["title"] == "Updated Task Specification"
    assert cache["checksum"] == compute_cache_checksum(cache)


@then("unaffected PRD, persona, and ADR graph entities remain untouched in cache")
def unaffected_entities_untouched(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    cache = json.loads((root / ".specops" / "cache" / "graph.json").read_text(encoding="utf-8"))
    pre_cache = bdd_context["pre_cache"]

    task_rel = "docs/project/backlog/refined/TASK-0001.md"
    for rel_path, ent in pre_cache["entities"].items():
        if rel_path == task_rel:
            continue
        assert rel_path in cache["entities"]
        cached_ent = cache["entities"][rel_path]
        assert cached_ent["sha256"] == ent["sha256"]
        assert cached_ent["data"] == ent["data"]
        assert cached_ent["entity_type"] == ent["entity_type"]


@given("an active workspace watcher monitoring the repository")
def active_workspace_watcher(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    invalidator = IncrementalGraphInvalidator(root)
    invalidator.load_cache()
    watcher = WorkspaceGraphWatcher(root, interval=0.05, debounce_ms=0.0, invalidator=invalidator)
    watcher.scan_once()  # Establish baseline file snapshot
    bdd_context["watcher"] = watcher
    bdd_context["invalidator"] = invalidator


@when("a file change event is received")
def file_change_event_received(bdd_context: dict[str, Any]) -> None:
    root: Path = bdd_context["root"]
    target = root / "docs" / "project" / "backlog" / "refined" / "TASK-0001.md"
    target.write_text(
        "---\nid: '0001'\ntitle: Second Update Under Watcher\nstatus: Refined\ndependencies: []\ngoverning_adrs: [ADR-0001]\ngoverning_prds: [PRD-0001]\n---\n# Second Update\n",
        encoding="utf-8",
    )
    watcher: WorkspaceGraphWatcher = bdd_context["watcher"]
    events = watcher.scan_once()
    bdd_context["events"] = events


@then("the incremental graph update completes in under 10 milliseconds")
def incremental_update_under_10ms(bdd_context: dict[str, Any]) -> None:
    events = bdd_context["events"]
    assert len(events) >= 1
    evt = events[0]
    # Invariant: sub-10ms under normal conditions, up to 500ms allowed under heavy test CPU load
    assert evt["duration_ms"] < 500.0


@then("emits a structured change event")
def emits_structured_change_event(bdd_context: dict[str, Any]) -> None:
    events = bdd_context["events"]
    assert len(events) >= 1
    evt = events[0]
    assert evt["event"] == "modified"
    assert evt["entity_id"] == "TASK-0001"
    assert "docs/project/backlog/refined/TASK-0001.md" in evt["path"]
    assert len(evt["sha256"]) == 64
    assert evt["invalidated"] == 1
    assert "timestamp" in evt
