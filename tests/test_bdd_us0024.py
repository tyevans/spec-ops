"""Executable BDD scenarios for US-0024: Automated Definition of Ready Gatekeeper and Ticket Health Audit."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.models import Task
from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.scaffold.init import init_project

scenarios("features/us_0024_dor_gatekeeper.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "dor_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="DoRTestRepo", target_dir=repo)

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Create baseline accepted ADRs, PRD, and user stories
    adrs_accepted = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_accepted.mkdir(parents=True, exist_ok=True)
    (adrs_accepted / "0001-pmac-traceability.md").write_text(
        "---\nid: '0001'\ntitle: PMaC Traceability\nstatus: Accepted\n---\n# ADR-0001\n",
        encoding="utf-8",
    )

    prd_accepted = repo / "docs" / "project" / "product" / "accepted"
    prd_accepted.mkdir(parents=True, exist_ok=True)
    (prd_accepted / "0005-relational-knowledge-graph.md").write_text(
        "---\nid: '0005'\ntitle: Relational Knowledge Graph\nstatus: Accepted\ntarget_persona: Jordan\n---\n# PRD-0005\n",
        encoding="utf-8",
    )

    stories_accepted = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_accepted.mkdir(parents=True, exist_ok=True)
    (stories_accepted / "us-0024-dor-gatekeeper.md").write_text(
        "---\nid: '0024'\ntitle: Automated DoR Gatekeeper\nstatus: Accepted\npersona: Jordan\n---\n# US-0024\n",
        encoding="utf-8",
    )

    # Create initial PRIORITY.md
    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_file.parent.mkdir(parents=True, exist_ok=True)
    priority_file.write_text(
        "# Backlog Priority Queue\n\n## Refined Buffer\n\n## Proposed\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial scaffold"], cwd=repo, check=True, capture_output=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")

    return {
        "repo": repo,
        "env": env,
        "last_res": None,
    }


# ==============================================================================
# Scenario 1: Promoting Only Fully Compliant Tasks to Refined Buffer
# ==============================================================================


@given("an under-buffered ready queue (< 3 tasks)")
def verify_under_buffered_queue(bdd_context: dict[str, Any]):
    repo: Path = bdd_context["repo"]
    queue = BacklogQueue(repo / "docs" / "project" / "backlog")
    refined = [t for t in queue.list_all_tasks() if t.status == "Refined"]
    assert len(refined) < 3


@given(parsers.parse('proposed task "{task_filename}" satisfies all 7 DoR rules:'))
def setup_fully_compliant_task(bdd_context: dict[str, Any], task_filename: str):
    repo: Path = bdd_context["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)

    task_file = proposed_dir / task_filename
    task = Task(
        id="0024",
        title="Implement Definition of Ready Gatekeeper",
        status="Proposed",
        target_bc="backlog",
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0005"],
        governing_stories=["US-0024"],
        persona="Jordan",
        mutation_scope="src/spec_ops/backlog/dor_gate.py",
        body="""## Acceptance Criteria
```gherkin
Given a fully compliant proposed task
When "spec-ops queue refine" is executed
Then the task transitions to refined/
```
## Mutation Scope
Target module mutmut score >=80% in dor_gate.py
""",
        file_path=task_file,
    )
    write_task_file(task)

    # Register in PRIORITY.md
    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    content = priority_file.read_text(encoding="utf-8")
    entry = f"- [ ] **TASK-0024 (Proposed)**: [`Implement Definition of Ready Gatekeeper`](proposed/{task_filename})\n"
    priority_file.write_text(content + entry, encoding="utf-8")


@when(parsers.parse('the lead executes "{command}"'))
def run_lead_command(bdd_context: dict[str, Any], command: str):
    repo: Path = bdd_context["repo"]
    cmd_parts = [sys.executable, "-m", "spec_ops.cli.main"] + command.split()[1:]
    res = subprocess.run(
        cmd_parts,
        cwd=repo,
        capture_output=True,
        text=True,
        env=bdd_context["env"],
    )
    bdd_context["last_res"] = res


@then(parsers.parse('"{task_id}" is promoted to "{refined_dir_path}"'))
def assert_task_promoted(bdd_context: dict[str, Any], task_id: str, refined_dir_path: str):
    repo: Path = bdd_context["repo"]
    res = bdd_context["last_res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"

    clean_num = task_id.replace("TASK-", "").zfill(4)
    target_dir = repo / refined_dir_path
    matching = list(target_dir.glob(f"{clean_num}*.md"))
    assert len(matching) == 1, f"Task not found in {refined_dir_path}: {list(target_dir.iterdir())}"

    # Verify task file status is Refined
    content = matching[0].read_text(encoding="utf-8")
    assert "status: Refined" in content


@then('"PRIORITY.md" is updated atomically.')
def assert_priority_updated(bdd_context: dict[str, Any]):
    repo: Path = bdd_context["repo"]
    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    content = priority_file.read_text(encoding="utf-8")
    assert "TASK-0024 (Refined)" in content
    assert "refined/0024-" in content


# ==============================================================================
# Scenario 2: Rejecting Half-Baked Proposed Tasks Lacking Gherkin Criteria
# ==============================================================================


@given(parsers.parse('a proposed task "{task_filename}" containing only bullet points and no "Given ... When ... Then" scenarios'))
def setup_half_baked_task(bdd_context: dict[str, Any], task_filename: str):
    repo: Path = bdd_context["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)

    task_file = proposed_dir / task_filename
    task = Task(
        id="0025",
        title="Ambiguous Task",
        status="Proposed",
        target_bc="backlog",
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0005"],
        persona="Jordan",
        mutation_scope="src/spec_ops/backlog/dor_gate.py",
        body="""## Acceptance Criteria
- Check item 1
- Check item 2
- Missing all Gherkin syntax
""",
        file_path=task_file,
    )
    write_task_file(task)


@when(parsers.parse('the lead runs "{command}"'))
def run_lead_backlog_command(bdd_context: dict[str, Any], command: str):
    repo: Path = bdd_context["repo"]
    cmd_parts = [sys.executable, "-m", "spec_ops.cli.main"] + command.split()[1:]
    res = subprocess.run(
        cmd_parts,
        cwd=repo,
        capture_output=True,
        text=True,
        env=bdd_context["env"],
    )
    bdd_context["last_res"] = res


@then("the command exits with code 1")
def assert_exit_code_1(bdd_context: dict[str, Any]):
    res = bdd_context["last_res"]
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}"


@then(parsers.parse('flags "{flag_message}"'))
def assert_flags_message(bdd_context: dict[str, Any], flag_message: str):
    res = bdd_context["last_res"]
    combined = res.stdout + "\n" + res.stderr
    assert flag_message in combined, f"Expected '{flag_message}' in output:\n{combined}"


@then(parsers.parse('the task remains in "{folder_path}"'))
def assert_task_remains_in_folder(bdd_context: dict[str, Any], folder_path: str):
    repo: Path = bdd_context["repo"]
    target_dir = repo / folder_path
    assert list(target_dir.glob("0025*.md")), f"Task 0025 not found in {folder_path}!"
    refined_dir = repo / "docs" / "project" / "backlog" / "refined"
    assert not list(refined_dir.glob("0025*.md")), "Task 0025 was unexpectedly promoted to refined!"


# ==============================================================================
# Scenario 3: Rejecting Tasks Violating Single-Responsibility Scope
# ==============================================================================


@given("a proposed task whose specification proposes modifying 8 different bounded contexts spanning >500 expected lines")
def setup_oversized_task(bdd_context: dict[str, Any]):
    repo: Path = bdd_context["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)

    task_file = proposed_dir / "0026-massive-cross-cutting-task.md"
    task = Task(
        id="0026",
        title="Massive Monolith Task",
        status="Proposed",
        target_bc="core",
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0005"],
        persona="Jordan",
        mutation_scope="src/spec_ops/backlog/dor_gate.py",
        body="""This task proposes modifying 8 different bounded contexts spanning >500 expected lines across the repository.

```gherkin
Given a monolithic specification
When verification runs
Then it should fail
```
""",
        file_path=task_file,
    )
    write_task_file(task)


@then(parsers.parse("the task is rejected with advice to decompose into thin vertical slices or architectural spikes (ADR-0002)."))
def assert_rejected_with_advice(bdd_context: dict[str, Any]):
    res = bdd_context["last_res"]
    combined = res.stdout + "\n" + res.stderr
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}"
    assert "decompose into thin vertical slices or architectural spikes (ADR-0002)" in combined
