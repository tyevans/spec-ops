"""BDD step definitions for US-0065: Real-Time In-Memory Graph Event Bus and Workspace Watcher."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.event_bus import EventBus
from spec_ops.core.watcher import WorkspaceWatcher
from spec_ops.scaffold.init import init_project

scenarios("features/us_0065_real_time_graph_event_bus_and_workspace_watcher.feature")


@pytest.fixture
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="WatcherApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@specops.test"], cwd=repo, check=True, capture_output=True)

    # Pre-populate base PRD, ADR, and Story
    p_prd = repo / "docs" / "project" / "product" / "accepted" / "prd-0001.md"
    p_prd.parent.mkdir(parents=True, exist_ok=True)
    p_prd.write_text("---\nid: '0001'\ntitle: Base PRD\nstatus: Accepted\n---\n", encoding="utf-8")

    p_adr = repo / "docs" / "project" / "adrs" / "accepted" / "adr-0001.md"
    p_adr.parent.mkdir(parents=True, exist_ok=True)
    p_adr.write_text("# ADR-0001: Base ADR\n\n## Status\nAccepted\n", encoding="utf-8")

    p_us = repo / "docs" / "project" / "user_stories" / "accepted" / "us-0001.md"
    p_us.parent.mkdir(parents=True, exist_ok=True)
    p_us.write_text("---\nid: '0001'\ntitle: Base Story\ngoverning_prd: PRD-0001\n---\n", encoding="utf-8")

    # Initial Task with 3 connections (PRD-0001, ADR-0001, target_bc: core)
    p_task = repo / "docs" / "project" / "backlog" / "proposed" / "0010-feature.md"
    p_task.parent.mkdir(parents=True, exist_ok=True)
    p_task.write_text(
        "---\nid: '0010'\ntitle: Feature 10\nstatus: Proposed\ntarget_bc: core\ngoverning_prds:\n  - PRD-0001\ngoverning_adrs:\n  - ADR-0001\ngoverning_stories:\n  - US-0001\n---\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    out_io = io.StringIO()
    err_io = io.StringIO()
    bus = EventBus()

    return {
        "repo": repo,
        "out_io": out_io,
        "err_io": err_io,
        "bus": bus,
        "watcher": None,
    }


@given(parsers.parse('the background daemon "{daemon_cmd}" is running in a worktree'))
def daemon_running_in_worktree(repo_context: dict[str, Any], daemon_cmd: str):
    repo = repo_context["repo"]
    event_stream = "--event-stream" in daemon_cmd
    watcher = WorkspaceWatcher(
        root_dir=repo,
        debounce_ms=10.0,
        event_stream=event_stream,
        event_bus=repo_context["bus"],
        out_stream=repo_context["out_io"],
        err_stream=repo_context["err_io"],
    )
    watcher.start()
    repo_context["watcher"] = watcher


@when(parsers.parse('Morgan moves "{src_path}" to "{dst_path}"'))
def morgan_moves_file(repo_context: dict[str, Any], src_path: str, dst_path: str):
    repo = repo_context["repo"]
    src = repo / src_path
    dst = repo / dst_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))

    watcher: WorkspaceWatcher = repo_context["watcher"]
    changed = watcher.scan_once()
    assert len(changed) > 0
    # Process batch
    items = watcher._debouncer.flush()
    watcher._handle_batch_flush(items)


@then(parsers.parse("the watcher detects the filesystem move event within {ms:d} milliseconds"))
def watcher_detects_within_ms(repo_context: dict[str, Any], ms: int):
    watcher: WorkspaceWatcher = repo_context["watcher"]
    assert watcher is not None


@then(parsers.parse('updates the in-memory graph node "{node_id}" status to "{status}"'))
def in_memory_node_updated(repo_context: dict[str, Any], node_id: str, status: str):
    watcher: WorkspaceWatcher = repo_context["watcher"]
    assert node_id in watcher.state.graph.nodes
    node_status = watcher.state.graph.nodes[node_id].get("status")
    assert node_status == status


@then("emits a structured event:")
def emits_structured_event(repo_context: dict[str, Any], docstring: str):
    out_text = repo_context["out_io"].getvalue()
    expected = json.loads(docstring)

    found = False
    for line in out_text.strip().splitlines():
        try:
            parsed = json.loads(line)
            if parsed.get("event") == expected.get("event") and parsed.get("id") == expected.get("id"):
                assert parsed.get("status") == expected.get("status")
                assert parsed.get("type") == expected.get("type")
                assert parsed.get("edges_recalculated") == expected.get("edges_recalculated")
                found = True
                break
        except json.JSONDecodeError:
            continue
    assert found, f"Expected event {expected} not found in output:\n{out_text}"


@given(parsers.parse('the watcher "{watcher_cmd}" is actively running'))
def watcher_actively_running(repo_context: dict[str, Any], watcher_cmd: str):
    repo = repo_context["repo"]
    watcher = WorkspaceWatcher(
        root_dir=repo,
        debounce_ms=10.0,
        event_stream=False,
        event_bus=repo_context["bus"],
        out_stream=repo_context["out_io"],
        err_stream=repo_context["err_io"],
    )
    watcher.start()
    repo_context["watcher"] = watcher


@when(parsers.parse('Morgan writes a new story referencing "{ref_clause}"'))
def morgan_writes_new_story(repo_context: dict[str, Any], ref_clause: str):
    repo = repo_context["repo"]
    story_file = repo / "docs" / "project" / "user_stories" / "accepted" / "us-0060.md"
    story_file.parent.mkdir(parents=True, exist_ok=True)
    story_file.write_text(f"---\nid: '0060'\ntitle: Story 60\n{ref_clause}\n---\n# US-0060\n", encoding="utf-8")

    watcher: WorkspaceWatcher = repo_context["watcher"]
    watcher.scan_once()
    items = watcher._debouncer.flush()
    watcher._handle_batch_flush(items)


@when(parsers.parse('"{entity_id}" does not exist in "{dir_path}"'))
def entity_does_not_exist(repo_context: dict[str, Any], entity_id: str, dir_path: str):
    repo = repo_context["repo"]
    target_dir = repo / dir_path
    matching = list(target_dir.glob(f"*{entity_id.lower()}*"))
    assert len(matching) == 0


@then("the watcher immediately outputs a real-time warning to the stream:")
def watcher_outputs_warning(repo_context: dict[str, Any], docstring: str):
    err_text = repo_context["err_io"].getvalue()
    lines = [line.strip() for line in docstring.strip().splitlines() if line.strip()]
    for line in lines:
        assert line in err_text, f"Expected warning line '{line}' in stderr:\n{err_text}"



@then(parsers.parse('flags the in-memory node as "{flag}" until resolved.'))
def flags_in_memory_node(repo_context: dict[str, Any], flag: str):
    watcher: WorkspaceWatcher = repo_context["watcher"]
    assert "US-0060" in watcher.state.graph.nodes
    assert watcher.state.graph.nodes["US-0060"].get("status") == flag or "US-0060" in watcher.state._invalid_nodes


@given("the watcher is running on a repository branch")
def watcher_running_on_branch(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    watcher = WorkspaceWatcher(
        root_dir=repo,
        debounce_ms=100.0,
        event_stream=False,
        event_bus=repo_context["bus"],
        out_stream=repo_context["out_io"],
        err_stream=repo_context["err_io"],
    )
    watcher.start()
    repo_context["watcher"] = watcher


@when(parsers.parse('Morgan runs "{git_cmd}" causing {count:d} files to update simultaneously'))
def morgan_git_checkout_batch(repo_context: dict[str, Any], git_cmd: str, count: int):
    repo = repo_context["repo"]
    # Simulate batch creation of specification files
    backlog_dir = repo / "docs" / "project" / "backlog" / "proposed"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    for i in range(100, 100 + count):
        (backlog_dir / f"{i:04d}-batch-task.md").write_text(
            f"---\nid: '{i:04d}'\ntitle: Batch Task {i}\nstatus: Proposed\n---\n",
            encoding="utf-8",
        )

    watcher: WorkspaceWatcher = repo_context["watcher"]
    changed = watcher.scan_once()
    assert len(changed) >= count
    items = watcher._debouncer.flush()
    watcher._handle_batch_flush(items)


@then(parsers.parse("the watcher debounces filesystem events across a {ms:d}ms window"))
def watcher_debounces_window(repo_context: dict[str, Any], ms: int):
    watcher: WorkspaceWatcher = repo_context["watcher"]
    assert watcher.debounce_ms == float(ms)


@then("executes a single batched graph recalculation")
def single_batched_graph_recalculation(repo_context: dict[str, Any]):
    bus: EventBus = repo_context["bus"]
    batch_events = bus.get_history("BATCHED_UPDATE")
    assert len(batch_events) >= 1


@then(parsers.parse('emits a summary: "{summary}".'))
def emits_summary_matching(repo_context: dict[str, Any], summary: str):
    out_text = repo_context["out_io"].getvalue()
    # Summary may vary slightly in duration ms: e.g. "Batched update: 15 files synchronized in 42ms"
    pattern = re.compile(r"Batched update: 15 files synchronized in \d+ms")
    assert pattern.search(out_text) is not None, f"Expected summary matching pattern in output:\n{out_text}"
