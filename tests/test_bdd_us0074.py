"""Executable BDD scenarios for US-0074: Deterministic Multi-Criteria Priority Re-Ranking."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0074_topological_reordering.feature")

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
def repo_ctx(tmp_path: Path) -> dict[str, Any]:
    """Sets up a clean test repository with git initialized and fresh backlog."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="RerankerTestRepo", target_dir=repo)

    root_pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if root_pyproject.exists() and not (repo / "pyproject.toml").exists():
        (repo / "pyproject.toml").symlink_to(root_pyproject)

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "agent@specops.io"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Agent"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, capture_output=True, check=True)

    backlog = repo / "docs" / "project" / "backlog"
    for folder in [backlog / "refined", backlog / "proposed", backlog / "complete"]:
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)

    priority_file = backlog / "PRIORITY.md"
    priority_file.write_text("# Backlog Priority Index\n\nStrict sequential order of execution for engineering tasks.\n\n", encoding="utf-8")

    return {"repo": repo, "result": None, "tasks": {}, "priority_file": priority_file}


# --- Scenario 1: Topological Re-ordering to Resolve Priority Inversion ---

@given(parsers.parse('task "{dependent}" depends on task "{prerequisite}"'))
def given_task_depends(repo_ctx: dict[str, Any], dependent: str, prerequisite: str):
    repo = repo_ctx["repo"]
    backlog = repo / "docs" / "project" / "backlog"

    dep_num = dependent.replace("TASK-", "")
    t_dep = Task(
        id=dep_num,
        title=f"Dependent Task {dependent}",
        status="Refined",
        dependencies=[prerequisite],
        file_path=backlog / "refined" / f"{dep_num}-dependent.md",
    )
    write_task_file(t_dep)
    repo_ctx["tasks"][dependent] = t_dep

    prereq_num = prerequisite.replace("TASK-", "")
    t_pre = Task(
        id=prereq_num,
        title=f"Prerequisite Task {prerequisite}",
        status="Refined",
        dependencies=[],
        file_path=backlog / "refined" / f"{prereq_num}-prerequisite.md",
    )
    write_task_file(t_pre)
    repo_ctx["tasks"][prerequisite] = t_pre


@given(parsers.parse('in "PRIORITY.md", "{first_task}" is listed at position {pos1:d} while "{second_task}" is listed at position {pos2:d}'))
def given_priority_positions(repo_ctx: dict[str, Any], first_task: str, pos1: int, second_task: str, pos2: int):
    repo = repo_ctx["repo"]
    backlog = repo / "docs" / "project" / "backlog"
    max_pos = max(pos1, pos2)

    # Scaffold filler tasks for all positions 1..max_pos
    lines: list[str] = []
    for p in range(1, max_pos + 1):
        if p == pos1:
            cid = first_task
            t = repo_ctx["tasks"][cid]
            lines.append(f"- **{cid} ({t.status})**: [`{t.file_path.stem}`](refined/{t.file_path.name})")
        elif p == pos2:
            cid = second_task
            t = repo_ctx["tasks"][cid]
            lines.append(f"- **{cid} ({t.status})**: [`{t.file_path.stem}`](refined/{t.file_path.name})")
        else:
            num = f"{p:04d}"
            cid = f"TASK-{num}"
            f_task = Task(
                id=num,
                title=f"Placeholder Task {num}",
                status="Refined",
                dependencies=[],
                file_path=backlog / "refined" / f"{num}-placeholder.md",
            )
            write_task_file(f_task)
            repo_ctx["tasks"][cid] = f_task
            lines.append(f"- **{cid} (Refined)**: [`{num}-placeholder`](refined/{num}-placeholder.md)")

    p_file = backlog / "PRIORITY.md"
    p_file.write_text("# Backlog Priority Index\n\nStrict sequential order of execution for engineering tasks.\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


@when(parsers.parse('the architect runs "{command}"'))
def when_architect_runs_command(repo_ctx: dict[str, Any], command: str):
    parts = command.split()
    args = parts[1:]  # strip 'spec-ops'
    res = run_spec_ops(repo_ctx["repo"], args)
    repo_ctx["result"] = res


@then("the re-ranking algorithm detects the priority inversion")
def then_detects_inversion(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    combined = res.stdout + res.stderr
    assert "priority inversion" in combined.lower() or "inversion" in combined.lower()


@then(parsers.parse('reorders "PRIORITY.md" so that prerequisite "{prereq}" strictly precedes dependent "{dep}"'))
def then_prereq_strictly_precedes(repo_ctx: dict[str, Any], prereq: str, dep: str):
    p_file = repo_ctx["repo"] / "docs" / "project" / "backlog" / "PRIORITY.md"
    content = p_file.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.strip().startswith("-")]

    prereq_idx = next((i for i, l in enumerate(lines) if prereq in l), -1)
    dep_idx = next((i for i, l in enumerate(lines) if dep in l), -1)

    assert prereq_idx != -1, f"Prerequisite {prereq} not in PRIORITY.md"
    assert dep_idx != -1, f"Dependent {dep} not in PRIORITY.md"
    assert prereq_idx < dep_idx, f"Expected {prereq} (pos {prereq_idx}) < {dep} (pos {dep_idx})"


@then("verifies 0 circular dependency cycles before writing the updated index.")
def then_verifies_zero_cycles(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0
    assert "circular dependency" not in res.stderr.lower()


# --- Scenario 2: Multi-Criteria Weighted Priority Scoring ---

@given(parsers.parse('proposed task "{task_id}" blocks {count:d} downstream tasks in "{milestone}"'))
def given_blocks_downstream_tasks(repo_ctx: dict[str, Any], task_id: str, count: int, milestone: str):
    repo = repo_ctx["repo"]
    backlog = repo / "docs" / "project" / "backlog"
    num = task_id.replace("TASK-", "")

    t = Task(
        id=num,
        title=f"Task {task_id}",
        status="Proposed",
        target_release=milestone,
        dependencies=[],
        file_path=backlog / "proposed" / f"{num}-feature.md",
    )
    write_task_file(t)
    repo_ctx["tasks"][task_id] = t

    p_file = backlog / "PRIORITY.md"
    content = p_file.read_text(encoding="utf-8")
    content += f"- **{task_id} (Proposed)**: [`{num}-feature`](proposed/{num}-feature.md)\n"

    # Create the downstream tasks blocked by task_id
    for i in range(1, count + 1):
        child_num = f"{int(num) + 100 + i:04d}"
        child_id = f"TASK-{child_num}"
        child_task = Task(
            id=child_num,
            title=f"Downstream Task {child_id}",
            status="Proposed",
            target_release=milestone,
            dependencies=[task_id],
            file_path=backlog / "proposed" / f"{child_num}-downstream.md",
        )
        write_task_file(child_task)
        repo_ctx["tasks"][child_id] = child_task
        content += f"- **{child_id} (Proposed)**: [`{child_num}-downstream`](proposed/{child_num}-downstream.md)\n"

    p_file.write_text(content, encoding="utf-8")


@then(parsers.parse('"{first_task}" is assigned a higher priority rank than "{second_task}" based on downstream fan-out weight and target milestone deadline'))
def then_higher_priority_rank(repo_ctx: dict[str, Any], first_task: str, second_task: str):
    p_file = repo_ctx["repo"] / "docs" / "project" / "backlog" / "PRIORITY.md"
    content = p_file.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.strip().startswith("-")]

    idx1 = next((i for i, l in enumerate(lines) if first_task in l), -1)
    idx2 = next((i for i, l in enumerate(lines) if second_task in l), -1)

    assert idx1 != -1, f"{first_task} not in PRIORITY.md"
    assert idx2 != -1, f"{second_task} not in PRIORITY.md"
    assert idx1 < idx2, f"Expected {first_task} (pos {idx1}) to precede {second_task} (pos {idx2})"


@then(parsers.parse('"{file_name}" reflects the updated sequential ordering.'))
def then_priority_reflects_ordering(repo_ctx: dict[str, Any], file_name: str):
    p_file = repo_ctx["repo"] / "docs" / "project" / "backlog" / file_name
    assert p_file.exists()
    assert repo_ctx["result"].returncode == 0


# --- Scenario 3: Respecting Architect Pin Overrides ---

@given(parsers.parse('task "{task_id}" contains "priority_pin: {pin_val}" in its YAML frontmatter'))
def given_task_contains_priority_pin(repo_ctx: dict[str, Any], task_id: str, pin_val: str):
    repo = repo_ctx["repo"]
    backlog = repo / "docs" / "project" / "backlog"
    num = task_id.replace("TASK-", "")

    pin_int = int(pin_val) if pin_val.isdigit() else None
    t = Task(
        id=num,
        title=f"Pinned Task {task_id}",
        status="Refined",
        dependencies=[],
        priority_pin=pin_int,
        pinned=True,
        file_path=backlog / "refined" / f"{num}-pinned.md",
    )
    write_task_file(t)
    repo_ctx["tasks"][task_id] = t

    # Add other unpinned tasks so task_id is initially NOT at position 1
    p_file = backlog / "PRIORITY.md"
    lines: list[str] = []
    # Add an unpinned task at position 1 initially
    other_num = "0001"
    other_id = f"TASK-{other_num}"
    other_task = Task(
        id=other_num,
        title="Other Task 0001",
        status="Refined",
        dependencies=[],
        file_path=backlog / "refined" / f"{other_num}-other.md",
    )
    write_task_file(other_task)
    repo_ctx["tasks"][other_id] = other_task
    lines.append(f"- **{other_id} (Refined)**: [`{other_num}-other`](refined/{other_num}-other.md)")

    # Put pinned task at position 2 initially
    lines.append(f"- **{task_id} (Refined)**: [`{num}-pinned`](refined/{num}-pinned.md)")

    # Add another unpinned task at position 3
    other_num3 = "0003"
    other_id3 = f"TASK-{other_num3}"
    other_task3 = Task(
        id=other_num3,
        title="Other Task 0003",
        status="Refined",
        dependencies=[],
        file_path=backlog / "refined" / f"{other_num3}-other.md",
    )
    write_task_file(other_task3)
    repo_ctx["tasks"][other_id3] = other_task3
    lines.append(f"- **{other_id3} (Refined)**: [`{other_num3}-other`](refined/{other_num3}-other.md)")

    p_file.write_text("# Backlog Priority Index\n\nStrict sequential order of execution for engineering tasks.\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


@then(parsers.parse('"{task_id}" remains locked at position {expected_pos:d} in "{file_name}"'))
def then_task_locked_at_position(repo_ctx: dict[str, Any], task_id: str, expected_pos: int, file_name: str):
    p_file = repo_ctx["repo"] / "docs" / "project" / "backlog" / file_name
    content = p_file.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.strip().startswith("-")]

    target_idx = expected_pos - 1
    assert target_idx < len(lines), f"Position {expected_pos} out of range (total {len(lines)})"
    assert task_id in lines[target_idx], f"Expected {task_id} at line {expected_pos}, found: {lines[target_idx]}"


@then("all other unpinned tasks are sorted topologically around it without violating prerequisite constraints.")
def then_all_other_sorted_topologically(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0
