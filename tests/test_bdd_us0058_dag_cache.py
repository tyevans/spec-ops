"""Executable BDD acceptance tests for US-0058: Incremental DAG Cache and Cycle Pre-Check.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009, ADR-0017; PRD-0005.
File length strictly under 400 lines.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import BacklogQueue
from spec_ops.core.dag_cache import DAGCacheEngine, can_add_dependency
from spec_ops.scaffold.init import init_project

scenarios("features/us_0058_dag_cache.feature")

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
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "dag_cache_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="DagCacheRepo")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "result": None, "api_duration_ms": 0.0, "tiers": None}


@given(parsers.parse('a cached task dependency DAG where "{task_b}" depends on "{task_a}"'))
def given_cached_dag(repo_context: dict[str, Any], task_b: str, task_a: str):
    repo = repo_context["repo"]
    backlog_refined = repo / "docs" / "project" / "backlog" / "refined"
    backlog_refined.mkdir(parents=True, exist_ok=True)

    t1_content = (
        "---\n"
        "id: '0001'\n"
        f"title: {task_a}\n"
        "status: Refined\n"
        "dependencies: []\n"
        "---\n"
        f"# {task_a}\n"
    )
    (backlog_refined / "0001-task-1.md").write_text(t1_content, encoding="utf-8")

    t2_content = (
        "---\n"
        "id: '0002'\n"
        f"title: {task_b}\n"
        "status: Refined\n"
        f"dependencies:\n  - {task_a}\n"
        "---\n"
        f"# {task_b}\n"
    )
    (backlog_refined / "0002-task-2.md").write_text(t2_content, encoding="utf-8")

    engine = DAGCacheEngine(repo)
    engine.build_cache(force=True)
    assert engine.cache_file.exists()


@when(parsers.parse('a command attempts to add "{target}" as a dependency of "{source}"'))
def when_attempt_add_dependency(repo_context: dict[str, Any], target: str, source: str):
    repo = repo_context["repo"]
    engine = DAGCacheEngine(repo)

    t0 = time.perf_counter()
    api_res = engine.can_add_dependency(target, source)
    api_dur = (time.perf_counter() - t0) * 1000

    repo_context["api_res"] = api_res
    repo_context["api_duration_ms"] = api_dur

    proc = run_spec_ops(repo, ["graph", "cycles", "--check-edge", target, source])
    repo_context["result"] = proc


@then("the cycle pre-check rejects the dependency in under 5 milliseconds")
def then_rejects_in_under_5ms(repo_context: dict[str, Any]):
    proc = repo_context["result"]
    assert proc.returncode == 1, f"Expected non-zero exit code: {proc.stdout}\n{proc.stderr}"
    api_res = repo_context["api_res"]
    assert api_res.allowed is False
    assert repo_context["api_duration_ms"] < 5.0, f"Cycle check took {repo_context['api_duration_ms']}ms >= 5ms"


@then(parsers.parse('reports the exact cyclic path "{expected_path}"'))
def then_reports_exact_path(repo_context: dict[str, Any], expected_path: str):
    proc = repo_context["result"]
    assert expected_path in proc.stdout
    api_res = repo_context["api_res"]
    assert api_res.path_str == expected_path


@given("an unmodified repository with valid topological cache")
def given_unmodified_repo_with_valid_cache(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    backlog_refined = repo / "docs" / "project" / "backlog" / "refined"
    backlog_refined.mkdir(parents=True, exist_ok=True)

    for i in range(1, 4):
        deps = [f"TASK-{i-1:04d}"] if i > 1 else []
        deps_block = f"dependencies:\n  - {deps[0]}" if deps else "dependencies: []"
        content = (
            f"---\nid: '{i:04d}'\ntitle: Task {i}\nstatus: Refined\n{deps_block}\n---\n# Task {i}\n"
        )
        (backlog_refined / f"{i:04d}-task-{i}.md").write_text(content, encoding="utf-8")

    engine = DAGCacheEngine(repo)
    engine.build_cache(force=True)
    assert engine.cache_file.exists()
    assert engine.is_cache_valid()


@when("the queue engine requests execution tiers")
def when_queue_requests_tiers(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    queue = BacklogQueue(repo / "docs" / "project" / "backlog")
    engine = DAGCacheEngine(repo)
    tiers = queue.get_execution_tiers(use_cache=True)
    repo_context["tiers"] = tiers
    repo_context["cache_engine"] = engine


@then("tiers are retrieved directly from cache without full repository graph parsing")
def then_tiers_retrieved_from_cache(repo_context: dict[str, Any]):
    tiers = repo_context["tiers"]
    assert tiers is not None
    assert len(tiers) >= 1
    engine: DAGCacheEngine = repo_context["cache_engine"]
    assert engine.is_cache_valid()
    loaded = engine.load_cache()
    assert loaded is not None
    assert loaded.execution_tiers == tiers
