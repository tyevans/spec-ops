"""Executable BDD acceptance tests for US-0060 and US-0063: Graph Topology, Cycle Detection, Pathfinding, and Blast-Radius.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009; PRD-0005.
File length strictly under 400 lines.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0060_graph_topology.feature")
scenarios("features/us_0063_graph_inspection.feature")

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
    repo = tmp_path / "graph_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="GraphRepo")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "result": None}


# --- US-0060 Scenario 1 ---
@given("a backlog with tasks:")
def given_backlog_with_tasks(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    for f in backlog_proposed.glob("*.md"):
        f.unlink()

    tasks_spec = [
        ("0001-task-1.md", "TASK-0001", []),
        ("0002-task-2.md", "TASK-0002", ["TASK-0001"]),
        ("0003-task-3.md", "TASK-0003", ["TASK-0001"]),
        ("0004-task-4.md", "TASK-0004", ["TASK-0002", "TASK-0003"]),
    ]
    for filename, tid, deps in tasks_spec:
        deps_yaml = "\n".join(f"  - {d}" for d in deps)
        deps_block = f"dependencies:\n{deps_yaml}" if deps else "dependencies: []"
        content = f"---\nid: '{tid.split('-')[-1]}'\ntitle: Task {tid}\nstatus: Refined\n{deps_block}\ngoverning_stories: [US-0001]\n---\n# {tid}\n"
        (backlog_proposed / filename).write_text(content, encoding="utf-8")

    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when('the lead runs "spec-ops graph order --type task"')
def when_lead_runs_graph_order(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["graph", "order", "--type", "task"])
    repo_context["result"] = res


@then("the command exits with code 0")
def then_command_exits_0(repo_context: dict[str, Any]):
    assert repo_context["result"].returncode == 0, f"Stderr: {repo_context['result'].stderr}\nStdout: {repo_context['result'].stdout}"


@then("outputs the deterministic topological sequence:")
def then_outputs_deterministic_topological_sequence(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "1. TASK-0001 (depth: 0)" in out
    assert "2. TASK-0002 (depth: 1)" in out
    assert "3. TASK-0003 (depth: 1)" in out
    assert "4. TASK-0004 (depth: 2)" in out


@then("identifies the critical path depth as 2.")
def then_identifies_critical_path_depth(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "critical path depth as 2" in out.lower()


# --- US-0060 Scenario 2 ---
@given(parsers.parse('task "{task_a}" depends on "{task_b}"'))
def given_task_depends_on(repo_context: dict[str, Any], task_a: str, task_b: str):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    num = task_a.split("-")[-1]
    fpath = backlog_proposed / f"{num}-{task_a.lower()}.md"
    content = f"---\nid: '{num}'\ntitle: Task {task_a}\nstatus: Refined\ndependencies:\n  - {task_b}\ngoverning_stories: [US-0001]\n---\n# {task_a}\n"
    fpath.write_text(content, encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@then("the command exits with code 1")
def then_command_exits_1(repo_context: dict[str, Any]):
    assert repo_context["result"].returncode == 1


@then(parsers.parse('reports "Cyclic Backlog Dependency Detected: Strongly Connected Component of size {size}"'))
def then_reports_scc_size(repo_context: dict[str, Any], size: str):
    out = repo_context["result"].stdout
    assert f"Strongly Connected Component of size {size}" in out


@then(parsers.parse('prints the directed cycle path: "{cycle_path}"'))
def then_prints_cycle_path(repo_context: dict[str, Any], cycle_path: str):
    out = repo_context["result"].stdout
    assert cycle_path in out


@then(parsers.parse('recommends: "{recommendation}".'))
def then_recommends_break_cycle(repo_context: dict[str, Any], recommendation: str):
    out = repo_context["result"].stdout
    clean_rec = recommendation.strip('"').strip(".")
    assert clean_rec.lower() in out.lower()


# --- US-0060 Scenario 3 ---
@given(parsers.parse('PRD "{prd_id}" claims implementing stories "{stories_str}"'))
def given_prd_claims_stories(repo_context: dict[str, Any], prd_id: str, stories_str: str):
    repo = repo_context["repo"]
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    num = prd_id.split("-")[-1]
    fpath = prd_dir / f"{num}-{prd_id.lower()}.md"
    stories = [s.strip().strip("'").strip('"') for s in stories_str.strip("[]").split(",") if s.strip()]
    yaml_stories = "\n".join(f"  - {s}" for s in stories)
    content = f"---\nid: '{num}'\ntitle: PRD {prd_id}\nstatus: Accepted\ntarget_persona: Alex\nlinked_stories:\n{yaml_stories}\n---\n# {prd_id}\n"
    fpath.write_text(content, encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@given(parsers.parse('User Story "{story_id}" specifies governing PRD "{prd_id}"'))
def given_story_specifies_prd(repo_context: dict[str, Any], story_id: str, prd_id: str):
    repo = repo_context["repo"]
    story_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    num = story_id.split("-")[-1]
    fpath = story_dir / f"{num}-{story_id.lower()}.md"
    content = f"---\nid: '{num}'\ntitle: Story {story_id}\nstatus: Accepted\npersona: Alex\ngoverning_prd: {prd_id}\n---\n# {story_id}\n"
    fpath.write_text(content, encoding="utf-8")
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when('the lead runs "spec-ops trace --verify"')
def when_lead_runs_trace_verify(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["trace", "--verify"])
    repo_context["result"] = res


@then(parsers.parse('reports "{message}".'))
def then_reports_message(repo_context: dict[str, Any], message: str):
    out = repo_context["result"].stdout
    clean_msg = message.strip('"').strip(".")
    assert clean_msg.lower() in out.lower()


# --- US-0063 Scenario 1 ---
@given(parsers.parse('a repository where task "{task_id}" is governed by "{adr_id}", implements "{story_id}", and targets bounded context "{bc}"'))
def given_task_governed_and_implements(repo_context: dict[str, Any], task_id: str, adr_id: str, story_id: str, bc: str):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    num = task_id.split("-")[-1]
    content = f"---\nid: '{num}'\ntitle: Task {task_id}\nstatus: Refined\ntarget_bc: {bc}\ngoverning_adrs:\n  - {adr_id}\ngoverning_stories:\n  - {story_id}\n---\n# {task_id}\n"
    (backlog_proposed / f"{num}-{task_id.lower()}.md").write_text(content, encoding="utf-8")

    # Author story with persona Jordan
    story_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    s_num = story_id.split("-")[-1]
    s_content = f"---\nid: '{s_num}'\ntitle: Story {story_id}\nstatus: Accepted\npersona: Jordan\ngoverning_prd: PRD-0001\n---\n# {story_id}\n"
    (story_dir / f"{s_num}-{story_id.lower()}.md").write_text(s_content, encoding="utf-8")

    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when(parsers.parse('the developer runs "spec-ops graph inspect {task_id}"'))
def when_developer_runs_graph_inspect(repo_context: dict[str, Any], task_id: str):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["graph", "inspect", task_id])
    repo_context["result"] = res


@then("the command outputs an ASCII entity card displaying:")
def then_outputs_ascii_entity_card(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "Entity ID" in out
    assert "TASK-0042" in out
    assert "invariants" in out
    assert "ADR-0003" in out
    assert "US-0020" in out
    assert "Jordan" in out


@then("lists all 1st-degree upstream dependencies and downstream dependents.")
def then_lists_1st_degree_neighbors(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "Upstream Dependencies (1st-degree):" in out
    assert "Downstream Dependents (1st-degree):" in out


# --- US-0063 Scenario 2 ---
@given(parsers.parse('persona "{persona_name}" desires story "{story_id}"'))
def given_persona_desires_story(repo_context: dict[str, Any], persona_name: str, story_id: str):
    repo = repo_context["repo"]
    personas_file = repo / "docs" / "project" / "user_stories" / "PERSONAS.md"
    current_p = personas_file.read_text(encoding="utf-8")
    if persona_name.lower() not in current_p.lower():
        personas_file.write_text(
            current_p + f"\n\n## 5. {persona_name.capitalize()} — The Product Manager\n- **Pain Points**:\n  - Silos\n- **Goals**:\n  - Traceability\n",
            encoding="utf-8",
        )

    story_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    num = story_id.split("-")[-1]
    content = f"---\nid: '{num}'\ntitle: Story {story_id}\nstatus: Accepted\npersona: {persona_name}\ngoverning_prd: PRD-0001\n---\n# {story_id}\n"
    (story_dir / f"{num}-{story_id.lower()}.md").write_text(content, encoding="utf-8")


@given(parsers.parse('story "{story_id}" specifies PRD "{prd_id}"'))
def given_story_specifies_prd_2(repo_context: dict[str, Any], story_id: str, prd_id: str):
    pass


@given(parsers.parse('PRD "{prd_id}" is implemented by task "{task_id}"'))
def given_prd_implemented_by_task(repo_context: dict[str, Any], prd_id: str, task_id: str):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    num = task_id.split("-")[-1]
    content = f"---\nid: '{num}'\ntitle: Task {task_id}\nstatus: Complete\ngoverning_prds:\n  - {prd_id}\ngoverning_stories:\n  - US-0046\n---\n# {task_id}\n"
    (backlog_proposed / f"{num}-{task_id.lower()}.md").write_text(content, encoding="utf-8")

    prd_file = repo / "docs" / "project" / "product" / "accepted" / "0001-prd-0001.md"
    if prd_file.exists():
        txt = prd_file.read_text(encoding="utf-8")
        if task_id not in txt:
            prd_file.write_text(txt.replace("linked_stories:", f"implementing_tasks:\n  - {task_id}\nlinked_stories:"), encoding="utf-8")


@given(parsers.parse('commit "{chash}" contains git message "{commit_msg}"'))
def given_commit_contains_message(repo_context: dict[str, Any], chash: str, commit_msg: str):
    repo = repo_context["repo"]
    subprocess.run(["git", "commit", "--allow-empty", "-m", commit_msg], cwd=repo, check=True, capture_output=True)
    real_chash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=repo, text=True).strip()
    repo_context["real_commit_sha"] = real_chash
    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when(parsers.parse('the developer runs "spec-ops graph path --from {from_node} --to {to_node}"'))
def when_developer_runs_graph_path(repo_context: dict[str, Any], from_node: str, to_node: str):
    repo = repo_context["repo"]
    if "a1b2c3d" in to_node and "real_commit_sha" in repo_context:
        to_node = to_node.replace("a1b2c3d", repo_context["real_commit_sha"])
    res = run_spec_ops(repo, ["graph", "path", "--from", from_node, "--to", to_node])
    repo_context["result"] = res


@then("prints the directed shortest path:")
def then_prints_directed_shortest_path(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "persona:taylor" in out or "taylor" in out
    assert "US-0046" in out
    assert "TASK-0046" in out
    assert "Path length: 3 hops." in out


# --- US-0063 Scenario 3 ---
@given(parsers.parse('ADR "{adr_id}" governs {count:d} active backlog tasks across {bc_count:d} bounded contexts'))
def given_adr_governs_active_tasks(repo_context: dict[str, Any], adr_id: str, count: int, bc_count: int):
    repo = repo_context["repo"]
    backlog_proposed = repo / "docs" / "project" / "backlog" / "proposed"
    bcs = ["core", "invariants", "visualizer"]

    tasks = ["TASK-0002", "TASK-0020", "TASK-0042", "TASK-0050", "TASK-0060", "TASK-0070", "TASK-0080", "TASK-0090"]
    for idx, tid in enumerate(tasks[:count]):
        num = tid.split("-")[-1]
        bc = bcs[idx % len(bcs)]
        prs_yaml = "prs: ['#104']" if idx == 0 else ("prs: ['#112']" if idx == 1 else "prs: []")
        content = f"---\nid: '{num}'\ntitle: Task {tid}\nstatus: Refined\ntarget_bc: {bc}\n{prs_yaml}\ngoverning_adrs:\n  - {adr_id}\ngoverning_stories:\n  - US-0001\n---\n# {tid}\n"
        (backlog_proposed / f"{num}-{tid.lower()}.md").write_text(content, encoding="utf-8")

    # Add transitive tasks to reach total 13 nodes affected
    for i in range(1, 6):
        tid = f"TASK-09{i:02d}"
        content = f"---\nid: '09{i:02d}'\ntitle: Transitive {tid}\nstatus: Refined\ndependencies:\n  - TASK-0002\ngoverning_stories:\n  - US-0001\n---\n# {tid}\n"
        (backlog_proposed / f"09{i:02d}-{tid.lower()}.md").write_text(content, encoding="utf-8")

    run_spec_ops(repo, ["graph", "compile", "--force-cold"])


@when(parsers.parse('the developer runs "spec-ops graph blast-radius {entity_id}"'))
def when_developer_runs_blast_radius(repo_context: dict[str, Any], entity_id: str):
    repo = repo_context["repo"]
    res = run_spec_ops(repo, ["graph", "blast-radius", entity_id])
    repo_context["result"] = res


@then("the command outputs:")
def then_command_outputs_blast_radius(repo_context: dict[str, Any]):
    out = repo_context["result"].stdout
    assert "Blast Radius for ADR-0003:" in out
    assert "affected bounded contexts" in out
    assert "Total Downstream Impact: HIGH" in out
