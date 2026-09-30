"""Executable BDD scenarios for US-0027 and US-0031: Task contract hydration and claim gates."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.backlog.worker import BacklogWorkerEngine
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.claimer import (
    initialize_worktree,
)

scenarios(
    "features/us_0027_task_contract_hydration.feature",
    "features/us_0031_autonomous_claim_gates.feature",
)


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    """Initializes a clean git repository scaffolded with SpecOps structure."""
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="WorkerGuardApp", target_dir=repo)

    # Symlink pyproject.toml for mutmut config discovery in subprocesses
    root_pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if root_pyproject.exists() and not (repo / "pyproject.toml").exists():
        (repo / "pyproject.toml").symlink_to(root_pyproject)

    # Empty out template tasks so test scenarios have total control
    for folder in [
        repo / "docs" / "project" / "backlog" / "refined",
        repo / "docs" / "project" / "backlog" / "proposed",
        repo / "docs" / "project" / "backlog" / "complete",
    ]:
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)

    # Write clean empty PRIORITY.md
    (repo / "docs" / "project" / "backlog" / "PRIORITY.md").write_text(
        "# Backlog Priority Index\n\n", encoding="utf-8"
    )

    # Baseline accepted PRD
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0004-autonomous-fleet.md").write_text(
        "---\nid: '0004'\ntitle: Autonomous Fleet\nstatus: Accepted\n---\n\n# PRD-0004\n",
        encoding="utf-8",
    )

    # Baseline accepted ADR
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "0002-modular-file-length-limits.md").write_text(
        "---\nid: '0002'\ntitle: File Length Limits\nstatus: Accepted\n---\n\n# ADR-0002\n",
        encoding="utf-8",
    )

    # Baseline accepted User Story
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0002-health-evaluator.md").write_text(
        "---\nid: '0002'\ntitle: Health Evaluator\nstatus: Accepted\n---\n\n# US-0002\n\n```gherkin\nScenario: Public sample\nGiven state\nWhen event\nThen result\n```\n",
        encoding="utf-8",
    )

    # Dummy passing test
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    # Git init and commit
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return repo


@pytest.fixture
def bdd_context(test_repo: Path) -> dict[str, Any]:
    cfg = load_config(test_repo)
    cfg.quality.preflight = ["true"]
    return {
        "repo": test_repo,
        "config": cfg,
        "worker_engine": BacklogWorkerEngine(cfg),
        "queue": BacklogQueue(cfg.backlog_dir),
        "worktree_dir": None,
        "cli_result": None,
        "task": None,
        "detected_dirty": [],
    }


# ==============================================================================
# US-0027: Machine-Readable Task Contract and Architectural Context Hydration
# ==============================================================================


@given(parsers.parse('a refined backlog task "{task_id}" with target bounded context "{bc}"'))
def create_refined_task_with_bc(bdd_context: dict[str, Any], task_id: str, bc: str):
    repo: Path = bdd_context["repo"]
    clean_id = task_id.replace("TASK-", "")
    task_file = repo / "docs" / "project" / "backlog" / "refined" / f"{clean_id}-task.md"
    task = Task(
        id=clean_id,
        title=f"Sample task {task_id}",
        status="Refined",
        target_bc=bc,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_context["task"] = task


@given(parsers.parse('the task cites governing ADRs "{adrs}" and acceptance criteria from "{stories}"'))
def task_cites_adrs_and_stories(bdd_context: dict[str, Any], adrs: str, stories: str):
    task: Task = bdd_context["task"]
    task.governing_adrs = [a.strip() for a in adrs.split(",")]
    task.governing_stories = [s.strip() for s in stories.split(",")]
    task.governing_prds = ["PRD-0004"]
    write_task_file(task)


@when(parsers.parse('the worker engine initializes the worktree for "{task_id}"'))
def worker_engine_initializes_worktree(bdd_context: dict[str, Any], task_id: str):
    repo: Path = bdd_context["repo"]
    cfg = bdd_context["config"]
    task: Task = bdd_context["task"]
    wt = initialize_worktree(repo, task, cfg)
    bdd_context["worktree_dir"] = wt


@then('a ".task-prompt.md" file is generated at the worktree root')
def prompt_file_generated(bdd_context: dict[str, Any]):
    wt: Path = bdd_context["worktree_dir"]
    prompt_file = wt / ".task-prompt.md"
    assert prompt_file.is_file(), f"Expected {prompt_file} to exist"
    bdd_context["prompt_content"] = prompt_file.read_text(encoding="utf-8")


@then("the prompt explicitly specifies the 500-line file length limit invariant")
def prompt_specifies_file_limit(bdd_context: dict[str, Any]):
    content = bdd_context["prompt_content"]
    assert "500-line file length limit invariant" in content
    assert "fewer than 500 lines" in content


@then("the prompt specifies blackbox frontdoor verification rules with zero private mocks")
def prompt_specifies_blackbox_rules(bdd_context: dict[str, Any]):
    content = bdd_context["prompt_content"]
    assert "blackbox frontdoor verification rules with zero private mocks" in content


@then(parsers.parse('the prompt injects the exact preflight command chain "{preflight_chain}"'))
def prompt_injects_preflight_chain(bdd_context: dict[str, Any], preflight_chain: str):
    content = bdd_context["prompt_content"]
    assert preflight_chain in content


@then(parsers.parse('the prompt instructs the agent that "{backlog_path}" must not be modified on feature branches.'))
def prompt_instructs_backlog_isolation(bdd_context: dict[str, Any], backlog_path: str):
    content = bdd_context["prompt_content"]
    assert backlog_path in content
    assert "must not be modified on feature branches" in content


# ==============================================================================
# US-0031: Autonomous Task Claiming with Dependency and Definition of Ready Gate
# ==============================================================================


@given(parsers.parse('a task "{task_id}" at the top of "docs/project/backlog/PRIORITY.md" in status "Refined"'))
def task_at_top_of_priority_refined(bdd_context: dict[str, Any], task_id: str):
    repo: Path = bdd_context["repo"]
    clean_id = task_id.replace("TASK-", "")
    task_file = repo / "docs" / "project" / "backlog" / "refined" / f"{clean_id}-sample.md"
    task = Task(
        id=clean_id,
        title=f"Sample {task_id}",
        status="Refined",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_context["target_task"] = task

    p_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    p_file.write_text(f"- **{task.canonical_id} (Refined)**: [`{task_file.stem}`](refined/{task_file.name})\n", encoding="utf-8")


@given(parsers.parse('all dependencies of "{task_id}" are in "docs/project/backlog/complete/"'))
def dependencies_in_complete(bdd_context: dict[str, Any], task_id: str):
    repo: Path = bdd_context["repo"]
    task: Task = bdd_context["target_task"]
    dep_file = repo / "docs" / "project" / "backlog" / "complete" / "0001-dep.md"
    dep_task = Task(id="0001", title="Dependency task", status="Complete", file_path=dep_file)
    write_task_file(dep_task)
    task.dependencies = ["TASK-0001"]
    write_task_file(task)


@given(parsers.parse('"{task_id}" frontmatter links to an accepted PRD, governing ADRs, and Gherkin scenarios'))
def task_links_to_prd_adrs_gherkin(bdd_context: dict[str, Any], task_id: str):
    repo: Path = bdd_context["repo"]
    task: Task = bdd_context["target_task"]
    task.governing_prds = ["PRD-0004"]
    task.governing_adrs = ["ADR-0002"]
    task.governing_stories = ["US-0002"]
    task.body = "\n## Acceptance Criteria\n```gherkin\nScenario: Public sample\nGiven state\nWhen event\nThen result\n```\n"
    write_task_file(task)


@when(parsers.parse('the agent runs "{command}"'))
def agent_runs_cli_command(bdd_context: dict[str, Any], command: str):
    repo: Path = bdd_context["repo"]
    args = command.split()
    if args[0] == "spec-ops":
        cmd = [sys.executable, "-m", "spec_ops.cli.main"] + args[1:]
    else:
        cmd = args

    res = subprocess.run(
        cmd,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_context["cli_result"] = res


@then(parsers.parse('the worker engine selects "{task_id}"'))
def worker_engine_selects_task(bdd_context: dict[str, Any], task_id: str):
    res = bdd_context["cli_result"]
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    data = json.loads(res.stdout)
    assert data["task_id"] == task_id
    bdd_context["claimed_metadata"] = data


@then("verifies that all DoR criteria are satisfied")
def verifies_dor_criteria_satisfied(bdd_context: dict[str, Any]):
    data = bdd_context["claimed_metadata"]
    assert len(data["governing_prds"]) > 0
    assert len(data["governing_adrs"]) > 0


@then(parsers.parse('provisions worktree "{worktree_dir}" on branch "{branch}"'))
def provisions_worktree_on_branch(bdd_context: dict[str, Any], worktree_dir: str, branch: str):
    repo: Path = bdd_context["repo"]
    wt_path = repo / worktree_dir
    assert wt_path.is_dir(), f"Expected worktree directory {wt_path} to exist"

    chk = subprocess.run(["git", "branch", "--show-current"], cwd=wt_path, capture_output=True, text=True)
    assert chk.stdout.strip() == branch


@then("returns exit code 0 with the claimed task metadata.")
def returns_exit_code_0_with_metadata(bdd_context: dict[str, Any]):
    res = bdd_context["cli_result"]
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "task_id" in data
    assert "worktree_dir" in data


@given(parsers.parse('a task "{task_id}" at the top of "PRIORITY.md" that depends on "{dep_id}"'))
def task_with_unsatisfied_dep(bdd_context: dict[str, Any], task_id: str, dep_id: str):
    repo: Path = bdd_context["repo"]
    clean_id = task_id.replace("TASK-", "")
    t_file = repo / "docs" / "project" / "backlog" / "refined" / f"{clean_id}-blocked.md"
    task = Task(
        id=clean_id,
        title=f"Blocked task {task_id}",
        status="Refined",
        dependencies=[dep_id],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        body="## Criteria\nScenario: Test\n",
        file_path=t_file,
    )
    write_task_file(task)

    t_next_file = repo / "docs" / "project" / "backlog" / "refined" / "0099-unblocked.md"
    next_task = Task(
        id="0099",
        title="Unblocked fallback task",
        status="Refined",
        dependencies=[],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0002"],
        body="## Criteria\nScenario: Test\n",
        file_path=t_next_file,
    )
    write_task_file(next_task)

    p_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    p_file.write_text(
        f"- **{task.canonical_id} (Refined)**: [`{t_file.stem}`](refined/{t_file.name})\n"
        f"- **{next_task.canonical_id} (Refined)**: [`{t_next_file.stem}`](refined/{t_next_file.name})\n",
        encoding="utf-8",
    )


@given(parsers.parse('"{dep_id}" is not yet in "docs/project/backlog/complete/"'))
def dep_not_in_complete(bdd_context: dict[str, Any], dep_id: str):
    repo: Path = bdd_context["repo"]
    clean_dep = dep_id.replace("TASK-", "")
    assert not (repo / "docs" / "project" / "backlog" / "complete" / f"{clean_dep}.md").exists()


@then(parsers.parse('the worker engine skips "{task_id}" due to unsatisfied dependency'))
def skips_task_due_to_dependency(bdd_context: dict[str, Any], task_id: str):
    res = bdd_context["cli_result"]
    assert f"Task {task_id} skipped: unsatisfied dependencies" in res.stderr


@then('evaluates the next sequential unblocked task in "PRIORITY.md"')
def evaluates_next_task(bdd_context: dict[str, Any]):
    res = bdd_context["cli_result"]
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["task_id"] == "TASK-0099"


@then("reports dependency blocking status in stderr.")
def reports_blocking_status_in_stderr(bdd_context: dict[str, Any]):
    res = bdd_context["cli_result"]
    assert "unsatisfied dependencies" in res.stderr
