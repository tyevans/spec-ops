"""Executable BDD acceptance tests for US-0016 and US-0021: Bidirectional Traceability Audit and Backlog Bottlenecks.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007; PRD-0005.
File length strictly under 400 lines.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0016_graph_traceability.feature")
scenarios("features/us_0021_backlog_bottlenecks.feature")

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
    repo = tmp_path / "audit_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="AuditRepo")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "result": None}


# --- US-0016 Scenario 1 ---
@given("a repository where all tasks cite accepted stories, all stories cite accepted PRDs, and all PRDs cite valid personas")
def given_clean_repository(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    # Create PRD-0001 accepted PRD citing persona Alex
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-prd-0001.md").write_text(
        "---\nid: '0001'\ntitle: Core PRD\nstatus: Accepted\ntarget_persona: Alex\nlinked_stories:\n  - US-0001\n---\n# PRD-0001\n",
        encoding="utf-8",
    )

    # Create US-0001 accepted story citing PRD-0001 and persona Alex
    us_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    us_dir.mkdir(parents=True, exist_ok=True)
    (us_dir / "0001-story-0001.md").write_text(
        "---\nid: '0001'\ntitle: Core Story\nstatus: Accepted\npersona: Alex\ngoverning_prd: PRD-0001\n---\n# US-0001\n",
        encoding="utf-8",
    )

    # Ensure all tasks across complete, refined, and proposed cite US-0001
    for folder in ["complete", "refined", "proposed"]:
        for f in (repo / "docs" / "project" / "backlog" / folder).glob("*.md"):
            txt = f.read_text(encoding="utf-8")
            if "governing_stories" not in txt:
                f.write_text(txt.replace("target_bc:", "governing_stories:\n  - US-0001\ntarget_bc:"), encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when('the architect runs "spec-ops trace --verify"')
def when_architect_runs_trace_verify(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["trace", "--verify"])
    repo_context["result"] = res


@then("the command exits with code 0")
def then_exit_0(repo_context: dict[str, Any]):
    assert repo_context["result"].returncode == 0, f"Stderr: {repo_context['result'].stderr}\nStdout: {repo_context['result'].stdout}"


@then('reports "Traceability Invariant Met: 100% graph connectivity with 0 orphan entities".')
def then_reports_traceability_met(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "Traceability Invariant Met: 100% graph connectivity with 0 orphan entities" in out


# --- US-0016 Scenario 2 ---
@given(parsers.parse('a task file in "{task_rel_path}" citing "story: {story_id}"'))
def given_task_file_citing_missing_story(repo_context: dict[str, Any], task_rel_path: str, story_id: str):
    repo = repo_context["repo"]
    target = repo / task_rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    num = target.stem.split("-")[0]
    content = f"---\nid: '{num}'\ntitle: Orphan Feature\nstatus: Proposed\nstory: {story_id}\ntarget_bc: core\n---\n# Orphan Feature\n"
    target.write_text(content, encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@given(parsers.parse('"{story_id}" does not exist in "docs/project/user_stories/"'))
def given_story_does_not_exist(repo_context: dict[str, Any], story_id: str):
    repo = repo_context["repo"]
    matches = list((repo / "docs" / "project" / "user_stories").rglob(f"*{story_id.lower()}*"))
    for m in matches:
        m.unlink()


@then("the command exits with code 1")
def then_exit_1(repo_context: dict[str, Any]):
    assert repo_context["result"].returncode == 1, f"Stderr: {repo_context['result'].stderr}\nStdout: {repo_context['result'].stdout}"


@then(parsers.parse('reports "Graph Error: Task {task_filename} references missing story \'{story_id}\'".'))
def then_reports_graph_error_missing_story(repo_context: dict[str, Any], task_filename: str, story_id: str):
    out = repo_context["result"].stdout
    assert f"Task {task_filename} references missing story '{story_id}'" in out


# --- US-0016 Scenario 3 ---
@given(parsers.parse('task "{task_a}" has "dependencies: [{task_b}]"'))
def given_task_has_dependency(repo_context: dict[str, Any], task_a: str, task_b: str):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    num = task_a.split("-")[-1]
    fpath = backlog_proposed / f"{num}-{task_a.lower()}.md"
    content = f"---\nid: '{num}'\ntitle: Task {task_a}\nstatus: Refined\ndependencies:\n  - {task_b}\ngoverning_stories: [US-0001]\n---\n# {task_a}\n"
    fpath.write_text(content, encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@then(parsers.parse('reports "Cyclic Backlog Dependency Detected: {task_a} <-> {task_b}"'))
def then_reports_cyclic_dependency(repo_context: dict[str, Any], task_a: str, task_b: str):
    out = repo_context["result"].stdout
    assert f"Cyclic Backlog Dependency Detected: {task_a} <-> {task_b}" in out or f"Cyclic Backlog Dependency Detected: {task_b} <-> {task_a}" in out


@then("outputs the cycle path.")
def then_outputs_cycle_path(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "Cycle Path:" in out or "->" in out


# --- US-0021 Scenario 1 ---
@given(parsers.parse('a backlog where multiple proposed tasks in different bounded contexts depend on a single unrefined task "{choke_task}"'))
def given_backlog_with_choke_point(repo_context: dict[str, Any], choke_task: str):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    for f in backlog_proposed.glob("*.md"):
        f.unlink()

    # Create choke task TASK-0013 as Proposed (unrefined)
    num = choke_task.split("-")[-1]
    choke_file = backlog_proposed / f"{num}-{choke_task.lower()}.md"
    choke_file.write_text(f"---\nid: '{num}'\ntitle: Choke Task\nstatus: Proposed\ngoverning_stories: [US-0001]\n---\n# {choke_task}\n", encoding="utf-8")

    # Create 6 proposed tasks in different BCs depending on TASK-0013 across 3 delivery horizons
    # Horizon 1: T20, T21 depend on TASK-0013
    # Horizon 2: T30, T31 depend on T20
    # Horizon 3: T40, T41 depend on T30
    bcs = ["core", "invariants", "visualizer", "backlog", "security", "prd"]
    task_specs = [
        ("0020", "TASK-0020", [choke_task], bcs[0]),
        ("0021", "TASK-0021", [choke_task], bcs[1]),
        ("0030", "TASK-0030", ["TASK-0020"], bcs[2]),
        ("0031", "TASK-0031", ["TASK-0020"], bcs[3]),
        ("0040", "TASK-0040", ["TASK-0030"], bcs[4]),
        ("0041", "TASK-0041", ["TASK-0030"], bcs[5]),
    ]
    for tid_num, tid, deps, bc in task_specs:
        deps_yaml = "\n".join(f"  - {d}" for d in deps)
        content = f"---\nid: '{tid_num}'\ntitle: Task {tid}\nstatus: Proposed\ntarget_bc: {bc}\ndependencies:\n{deps_yaml}\ngoverning_stories: [US-0001]\n---\n# {tid}\n"
        (backlog_proposed / f"{tid_num}-{tid.lower()}.md").write_text(content, encoding="utf-8")

    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when('the lead runs "spec-ops backlog bottlenecks"')
def when_lead_runs_backlog_bottlenecks(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["backlog", "bottlenecks"])
    repo_context["result"] = res


@then("the command outputs a prioritized bottleneck analysis:")
def then_outputs_prioritized_bottleneck_analysis(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "Prioritized Bottleneck Analysis:" in out
    assert "TASK-0013" in out
    assert "6 tasks" in out
    assert "3 delivery horizons" in out
    assert "Prioritize Refinement" in out


@then(parsers.parse('highlights {choke_task} as a primary choke point in the visualizer graph with a pulsing alert aura.'))
def then_highlights_choke_point(repo_context: dict[str, Any], choke_task: str):
    out = repo_context["result"].stdout
    assert f"Highlights {choke_task} as a primary choke point in the visualizer graph with a pulsing alert aura." in out


# --- US-0021 Scenario 2 ---
@given(parsers.parse('task "{task_a}" lists "{task_b}" in its dependencies'))
def given_task_lists_dependency(repo_context: dict[str, Any], task_a: str, task_b: str):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    num = task_a.split("-")[-1]
    content = f"---\nid: '{num}'\ntitle: Task {task_a}\nstatus: Refined\ndependencies:\n  - {task_b}\ngoverning_stories: [US-0001]\n---\n# {task_a}\n"
    (backlog_proposed / f"{num}-{task_a.lower()}.md").write_text(content, encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@given(parsers.parse('task "{task_b}" directly or transitively depends on "{task_a}"'))
def given_task_transitively_depends(repo_context: dict[str, Any], task_b: str, task_a: str):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    num = task_b.split("-")[-1]
    content = f"---\nid: '{num}'\ntitle: Task {task_b}\nstatus: Refined\ndependencies:\n  - {task_a}\ngoverning_stories: [US-0001]\n---\n# {task_b}\n"
    (backlog_proposed / f"{num}-{task_b.lower()}.md").write_text(content, encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@then(parsers.parse('displays the exact circular cycle: "{cycle_path}"'))
def then_displays_exact_circular_cycle(repo_context: dict[str, Any], cycle_path: str):
    out = repo_context["result"].stdout
    assert cycle_path in out


@then("provides actionable CLI suggestions to break the dependency cycle.")
def then_provides_actionable_suggestions(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "suggestion:" in out.lower() or "break cycle" in out.lower()


# --- US-0021 Scenario 3 ---
@given("a refined queue containing only 1 unassigned task")
def given_refined_queue_single_unassigned(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    backlog_refined = repo / "docs" / "project" / "backlog" / "refined"
    backlog_refined.mkdir(parents=True, exist_ok=True)

    for f in backlog_proposed.glob("*.md"):
        f.unlink()
    for f in backlog_refined.glob("*.md"):
        f.unlink()

    # Single refined task
    (backlog_refined / "0001-task-0001.md").write_text(
        "---\nid: '0001'\ntitle: Task 1\nstatus: Refined\ngoverning_stories: [US-0001]\n---\n# TASK-0001\n",
        encoding="utf-8",
    )


@given("all remaining proposed tasks are blocked by pending in-flight tasks")
def given_proposed_tasks_blocked_by_in_flight(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    (backlog_proposed / "0002-task-0002.md").write_text(
        "---\nid: '0002'\ntitle: Task 2\nstatus: Proposed\ndependencies:\n  - TASK-0001\ngoverning_stories: [US-0001]\n---\n# TASK-0002\n",
        encoding="utf-8",
    )
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when('the lead executes "spec-ops backlog bottlenecks --forecast"')
def when_lead_executes_backlog_bottlenecks_forecast(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["backlog", "bottlenecks", "--forecast"])
    repo_context["result"] = res


@then(parsers.parse('the command warns: "{warning_msg}"'))
def then_command_warns_buffer_starvation(repo_context: dict[str, Any], warning_msg: str):
    out = repo_context["result"].stdout
    clean_warn = warning_msg.strip('"').strip(".")
    assert clean_warn.lower() in out.lower()


@then("suggests which in-flight tasks require immediate unblocking or rescue to replenish the ready buffer.")
def then_suggests_inflight_tasks_unblock(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "suggested action:" in out.lower()
    assert "TASK-0001" in out
