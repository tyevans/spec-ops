"""Comprehensive unit tests for Incremental DAG Cache and Cycle Pre-Check.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0017; PRD-0005; US-0058.
File length strictly under 400 lines.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from spec_ops.backlog.queue import BacklogQueue
from spec_ops.core.dag_cache import (
    CyclePreCheckResult,
    CyclicDependencyError,
    DAGCacheEngine,
    DAGCachePayload,
    can_add_dependency,
    compute_content_sha256,
    format_cycle_path,
    normalize_task_id,
)
from spec_ops.scaffold.init import init_project

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test_project"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="TestProject")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    backlog = repo / "docs" / "project" / "backlog" / "refined"
    backlog.mkdir(parents=True, exist_ok=True)

    # 3-task chain: TASK-0003 depends on TASK-0002, which depends on TASK-0001
    tasks = [
        ("0001-task-1.md", "0001", []),
        ("0002-task-2.md", "0002", ["TASK-0001"]),
        ("0003-task-3.md", "0003", ["TASK-0002"]),
    ]
    for fn, tid, deps in tasks:
        d_yaml = "\n".join(f"  - {d}" for d in deps)
        d_block = f"dependencies:\n{d_yaml}" if deps else "dependencies: []"
        content = f"---\nid: '{tid}'\ntitle: Task {tid}\nstatus: Refined\n{d_block}\n---\n# Task {tid}\n"
        (backlog / fn).write_text(content, encoding="utf-8")

    return repo


def test_normalize_task_id():
    assert normalize_task_id("task-1") == "TASK-0001"
    assert normalize_task_id("TASK-0042") == "TASK-0042"
    assert normalize_task_id("123") == "TASK-0123"
    assert normalize_task_id("  task-0005  ") == "TASK-0005"


def test_format_cycle_path():
    assert format_cycle_path(["TASK-0002", "TASK-0001", "TASK-0002"]) == [
        "TASK-0001",
        "TASK-0002",
        "TASK-0001",
    ]
    assert format_cycle_path(["TASK-0003", "TASK-0001", "TASK-0002", "TASK-0003"]) == [
        "TASK-0001",
        "TASK-0002",
        "TASK-0003",
        "TASK-0001",
    ]
    assert format_cycle_path(["TASK-0001", "TASK-0001"]) == ["TASK-0001", "TASK-0001"]


def test_can_add_dependency_self_loop():
    cache = DAGCachePayload(adj={"TASK-0001": []}, reachability={"TASK-0001": []})
    res = can_add_dependency(cache, "TASK-0001", "TASK-0001")
    assert not res
    assert res.allowed is False
    assert res.cycle_path == ["TASK-0001", "TASK-0001"]
    assert res.path_str == "TASK-0001 -> TASK-0001"

    with pytest.raises(CyclicDependencyError) as exc_info:
        can_add_dependency(cache, "TASK-0001", "TASK-0001", raise_on_cycle=True)
    assert exc_info.value.path_str == "TASK-0001 -> TASK-0001"


def test_can_add_dependency_chain_cycle_and_allowed(test_repo: Path):
    engine = DAGCacheEngine(test_repo)
    payload = engine.build_cache(force=True)

    # Allowed: independent or forward edge
    res_ok = can_add_dependency(payload, "TASK-0003", "TASK-0001")
    assert res_ok.allowed is True
    assert res_ok.cycle_path == []
    assert bool(res_ok) is True

    # Iteration unpacking support
    allowed, path_str = can_add_dependency(payload, "TASK-0001", "TASK-0003")
    assert allowed is False
    assert path_str == "TASK-0001 -> TASK-0003 -> TASK-0002 -> TASK-0001"

    # Cycle: TASK-0001 cannot depend on TASK-0003
    res_cycle = can_add_dependency(payload, "TASK-0001", "TASK-0003")
    assert res_cycle.allowed is False
    assert res_cycle.cycle_path == ["TASK-0001", "TASK-0003", "TASK-0002", "TASK-0001"]
    assert res_cycle.path_str == "TASK-0001 -> TASK-0003 -> TASK-0002 -> TASK-0001"


def test_dag_cache_engine_persistence_and_warm_hit(test_repo: Path):
    engine = DAGCacheEngine(test_repo)
    assert not engine.cache_file.exists()

    payload1 = engine.build_cache()
    assert engine.cache_file.exists()
    assert engine.last_hit is False
    assert payload1.critical_path_depth == 2

    # Second call should be a warm hit
    payload2 = engine.build_cache()
    assert engine.last_hit is True
    assert payload1.fingerprint == payload2.fingerprint
    assert payload1.execution_tiers == payload2.execution_tiers


def test_dag_cache_invalidation_on_file_modification(test_repo: Path):
    engine = DAGCacheEngine(test_repo)
    payload1 = engine.build_cache()
    assert engine.is_cache_valid()

    # Modify task 1
    t1_path = test_repo / "docs" / "project" / "backlog" / "refined" / "0001-task-1.md"
    time.sleep(0.01)
    t1_path.write_text(t1_path.read_text(encoding="utf-8") + "\n# Extra Line\n", encoding="utf-8")

    assert not engine.is_cache_valid()
    payload2 = engine.build_cache()
    assert engine.last_hit is False
    assert payload1.fingerprint != payload2.fingerprint


def test_dag_cache_invalidation_on_file_addition_and_deletion(test_repo: Path):
    engine = DAGCacheEngine(test_repo)
    engine.build_cache()
    assert engine.is_cache_valid()

    # Add task 4
    new_task = test_repo / "docs" / "project" / "backlog" / "refined" / "0004-task-4.md"
    new_task.write_text(
        "---\nid: '0004'\ntitle: Task 4\nstatus: Refined\ndependencies:\n  - TASK-0003\n---\n# Task 4\n",
        encoding="utf-8",
    )
    assert not engine.is_cache_valid()

    engine.build_cache()
    assert engine.is_cache_valid()

    # Delete task 4
    new_task.unlink()
    assert not engine.is_cache_valid()


def test_dag_cache_corrupted_file_recovery(test_repo: Path):
    engine = DAGCacheEngine(test_repo)
    engine.build_cache()
    assert engine.cache_file.exists()

    # Corrupt cache file
    engine.cache_file.write_text("NOT_VALID_JSON", encoding="utf-8")
    assert engine.load_cache() is None
    assert not engine.is_cache_valid()

    # Should gracefully rebuild
    payload = engine.build_cache()
    assert payload is not None
    assert engine.is_cache_valid()


def test_backlog_queue_get_execution_tiers_integration(test_repo: Path):
    queue = BacklogQueue(test_repo / "docs" / "project" / "backlog")
    tiers = queue.get_execution_tiers(use_cache=True)
    assert len(tiers) == 3
    assert tiers[0] == ["TASK-0001"]
    assert tiers[1] == ["TASK-0002"]
    assert tiers[2] == ["TASK-0003"]


def test_cli_graph_cycles_check_edge_frontdoor(test_repo: Path):
    # Valid edge
    res_ok = run_spec_ops(test_repo, ["graph", "cycles", "--check-edge", "TASK-0003", "TASK-0001"])
    assert res_ok.returncode == 0
    assert "Zero dependency cycles detected" in res_ok.stdout

    # Valid edge with JSON
    res_ok_json = run_spec_ops(test_repo, ["graph", "cycles", "--check-edge", "TASK-0003", "TASK-0001", "--json"])
    assert res_ok_json.returncode == 0
    data_ok = json.loads(res_ok_json.stdout)
    assert data_ok["allowed"] is True

    # Cyclic edge
    res_err = run_spec_ops(test_repo, ["graph", "cycles", "--check-edge", "TASK-0001", "TASK-0003"])
    assert res_err.returncode == 1
    assert "Cyclic dependency detected: TASK-0001 -> TASK-0003 -> TASK-0002 -> TASK-0001" in res_err.stdout
    assert "Actionable suggestion: Break cycle by removing dependency from TASK-0001 to TASK-0003" in res_err.stdout

    # Cyclic edge with JSON
    res_err_json = run_spec_ops(test_repo, ["graph", "cycles", "--check-edge", "TASK-0001", "TASK-0003", "--json"])
    assert res_err_json.returncode == 1
    data_err = json.loads(res_err_json.stdout)
    assert data_err["allowed"] is False
    assert data_err["path_str"] == "TASK-0001 -> TASK-0003 -> TASK-0002 -> TASK-0001"
    assert data_err["cycle_path"] == ["TASK-0001", "TASK-0003", "TASK-0002", "TASK-0001"]


def test_performance_sub_5ms_requirement(test_repo: Path):
    engine = DAGCacheEngine(test_repo)
    engine.build_cache()

    durations = []
    for _ in range(50):
        t0 = time.perf_counter()
        res = engine.can_add_dependency("TASK-0001", "TASK-0003")
        dur = (time.perf_counter() - t0) * 1000
        durations.append(dur)
        assert res.allowed is False

    avg_dur = sum(durations) / len(durations)
    max_dur = max(durations)
    assert avg_dur < 1.0, f"Average check duration {avg_dur}ms >= 1.0ms"
    assert max_dur < 5.0, f"Max check duration {max_dur}ms >= 5.0ms"
