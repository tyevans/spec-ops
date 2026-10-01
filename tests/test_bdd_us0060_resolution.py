"""Executable BDD acceptance tests for US-0060: Deterministic Cycle Resolution and Choke Points.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009, ADR-0017; PRD-0005.
File length strictly under 400 lines.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0060_resolution.feature")

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
    repo = tmp_path / "resolution_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="ResolutionRepo")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "result": None}


@given("a backlog with cyclic tasks:")
def given_backlog_with_cyclic_tasks(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    for f in backlog_proposed.glob("*.md"):
        f.unlink()

    # Create cycle TASK-0010 -> TASK-0011 -> TASK-0012 -> TASK-0010
    tasks = [
        ("0010-task-10.md", "TASK-0010", ["TASK-0011"]),
        ("0011-task-11.md", "TASK-0011", ["TASK-0012"]),
        ("0012-task-12.md", "TASK-0012", ["TASK-0010"]),
    ]
    for filename, tid, deps in tasks:
        deps_yaml = "\n".join(f"  - {d}" for d in deps)
        deps_block = f"dependencies:\n{deps_yaml}" if deps else "dependencies: []"
        num = tid.split("-")[-1]
        content = f"---\nid: '{num}'\ntitle: Task {tid}\nstatus: Refined\n{deps_block}\ngoverning_stories: [US-0001]\n---\n# {tid}\n"
        (backlog_proposed / filename).write_text(content, encoding="utf-8")

    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@given("a backlog with high-fanout choke points:")
def given_backlog_with_choke_points(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    for f in backlog_proposed.glob("*.md"):
        f.unlink()

    tasks = [
        ("0001-task-1.md", "TASK-0001", []),
        ("0002-task-2.md", "TASK-0002", ["TASK-0001"]),
        ("0003-task-3.md", "TASK-0003", ["TASK-0001"]),
        ("0004-task-4.md", "TASK-0004", ["TASK-0002"]),
    ]
    for filename, tid, deps in tasks:
        deps_yaml = "\n".join(f"  - {d}" for d in deps)
        deps_block = f"dependencies:\n{deps_yaml}" if deps else "dependencies: []"
        num = tid.split("-")[-1]
        content = f"---\nid: '{num}'\ntitle: Task {tid}\nstatus: Refined\n{deps_block}\ngoverning_stories: [US-0001]\n---\n# {tid}\n"
        (backlog_proposed / filename).write_text(content, encoding="utf-8")

    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when('the lead runs "spec-ops graph cycles --resolve"')
def when_lead_runs_cycles_resolve(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    repo_context["result"] = run_spec_ops(repo, ["graph", "cycles", "--resolve"])


@when('the lead runs "spec-ops graph cycles --prune-chokepoints"')
def when_lead_runs_cycles_prune_chokepoints(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    repo_context["result"] = run_spec_ops(repo, ["graph", "cycles", "--prune-chokepoints"])


@when('the lead runs "spec-ops graph cycles --resolve --prune-chokepoints --json"')
def when_lead_runs_cycles_resolve_prune_json(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    repo_context["result"] = run_spec_ops(repo, ["graph", "cycles", "--resolve", "--prune-chokepoints", "--json"])


@then("the command exits with code 1")
def then_command_exits_1(repo_context: dict[str, Any]):
    assert repo_context["result"].returncode == 1


@then("the command exits with code 0")
def then_command_exits_0(repo_context: dict[str, Any]):
    assert repo_context["result"].returncode == 0, f"Error: {repo_context['result'].stderr}\nOutput: {repo_context['result'].stdout}"


@then(parsers.parse('reports "Cyclic Backlog Dependency Detected: Strongly Connected Component of size {size}"'))
def then_reports_scc_size(repo_context: dict[str, Any], size: str):
    out = repo_context["result"].stdout
    assert f"Strongly Connected Component of size {size}" in out


@then(parsers.parse('prints the directed cycle path: "{cycle_path}"'))
def then_prints_cycle_path(repo_context: dict[str, Any], cycle_path: str):
    out = repo_context["result"].stdout
    assert cycle_path in out


@then(parsers.parse('pinpoints minimal feedback edge: "{edge_str}"'))
def then_pinpoints_feedback_edge(repo_context: dict[str, Any], edge_str: str):
    out = repo_context["result"].stdout
    assert "Minimal feedback edge:" in out
    clean_edge = edge_str.strip('"')
    assert clean_edge in out


@then(parsers.parse('outputs actionable cycle remediation: "{remediation}"'))
def then_outputs_cycle_remediation(repo_context: dict[str, Any], remediation: str):
    out = repo_context["result"].stdout
    assert remediation in out


@then('reports "Traceability Invariant Met: Zero dependency cycles detected."')
def then_reports_acyclic(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "Traceability Invariant Met: Zero dependency cycles detected." in out


@then(parsers.parse('identifies choke point "{node_id}"'))
def then_identifies_choke_point(repo_context: dict[str, Any], node_id: str):
    out = repo_context["result"].stdout
    assert f"Choke Point: {node_id}" in out
    assert "downstream impact:" in out


@then(parsers.parse('suggests decoupling seams for "{node_id}"'))
def then_suggests_decoupling_seams(repo_context: dict[str, Any], node_id: str):
    out = repo_context["result"].stdout
    assert "Decoupling Seams:" in out
    assert "* " in out


@then("the JSON output contains cyclic status true")
def then_json_cyclic_true(repo_context: dict[str, Any]):
    out = json.loads(repo_context["result"].stdout)
    assert out["cyclic"] is True
    assert out["cycle_count"] >= 1


@then("the JSON output contains cycle resolution feedback edges")
def then_json_cycle_resolution(repo_context: dict[str, Any]):
    out = json.loads(repo_context["result"].stdout)
    assert "resolution" in out
    assert len(out["resolution"]["all_feedback_edges"]) >= 1
    assert len(out["resolution"]["all_remediations"]) >= 1


@then("the JSON output contains choke points")
def then_json_choke_points(repo_context: dict[str, Any]):
    out = json.loads(repo_context["result"].stdout)
    assert "choke_points" in out
