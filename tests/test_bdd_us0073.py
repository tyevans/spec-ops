"""Executable BDD scenarios for US-0073: Automated Reactive Unblocking and Cascading Buffer Replenishment."""

from __future__ import annotations

import json
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

scenarios("features/us_0073_automated_reactive_unblocking_and_buffer_replenishment.feature")

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
    """Sets up a clean test repository with git initialized."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="CascadeUnblockTest", target_dir=repo)

    root_pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if root_pyproject.exists() and not (repo / "pyproject.toml").exists():
        (repo / "pyproject.toml").symlink_to(root_pyproject)

    # Initialize git repo so git commands succeed
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "agent@specops.io"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Agent"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, capture_output=True, check=True)

    # Clean out task directories
    for folder in [
        repo / "docs" / "project" / "backlog" / "refined",
        repo / "docs" / "project" / "backlog" / "proposed",
        repo / "docs" / "project" / "backlog" / "complete",
    ]:
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)

    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_file.write_text("# Backlog Priority Index\n\n", encoding="utf-8")

    return {"repo": repo, "result": None, "tasks": {}}


# --- Scenario 1 Steps ---

@given('task "TASK-0013" is in "docs/project/backlog/refined/" and currently claimed')
def given_task_13_refined_claimed(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"
    task = Task(
        id="0013",
        title="Prerequisite Task",
        status="Refined",
        claimed_by="agent-alpha",
        signed_off_by="lead@specops.io",
        branch="main",
        priority_rank=1,
        file_path=backlog_dir / "refined" / "0013-prereq.md",
    )
    write_task_file(task)
    repo_ctx["tasks"]["TASK-0013"] = task

    # Update PRIORITY.md
    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(
        p_file.read_text(encoding="utf-8")
        + "- **TASK-0013 (Refined)**: [`0013-prereq`](refined/0013-prereq.md)\n",
        encoding="utf-8",
    )


@given('proposed task "TASK-0014" has "dependencies: [TASK-0013]" in "docs/project/backlog/proposed/"')
def given_task_14_proposed_dependent(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"
    task = Task(
        id="0014",
        title="Downstream Task",
        status="Proposed",
        dependencies=["TASK-0013"],
        priority_rank=2,
        target_bc="backlog",
        file_path=backlog_dir / "proposed" / "0014-downstream.md",
    )
    write_task_file(task)
    repo_ctx["tasks"]["TASK-0014"] = task

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(
        p_file.read_text(encoding="utf-8")
        + "- **TASK-0014 (Proposed)**: [`0014-downstream`](proposed/0014-downstream.md)\n",
        encoding="utf-8",
    )


@given("the refined buffer currently has 2 available ready tasks (below buffer target of 10)")
def given_refined_buffer_has_2_tasks(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"
    # TASK-0013 is 1st task. Add 1 more ready task to make it 2.
    extra_task = Task(
        id="0099",
        title="Other Ready Task",
        status="Refined",
        priority_rank=99,
        file_path=backlog_dir / "refined" / "0099-other.md",
    )
    write_task_file(extra_task)
    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(
        p_file.read_text(encoding="utf-8")
        + "- **TASK-0099 (Refined)**: [`0099-other`](refined/0099-other.md)\n",
        encoding="utf-8",
    )


@when('the orchestrator executes "spec-ops queue complete TASK-0013"')
def when_execute_complete_13(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["queue", "complete", "TASK-0013"])
    repo_ctx["result"] = res


@then('"TASK-0013" is moved to "docs/project/backlog/complete/"')
def then_task_13_moved_to_complete(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0, f"spec-ops queue complete TASK-0013 failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    repo = repo_ctx["repo"]
    complete_path = repo / "docs" / "project" / "backlog" / "complete" / "0013-prereq.md"
    refined_path = repo / "docs" / "project" / "backlog" / "refined" / "0013-prereq.md"
    assert complete_path.exists(), f"TASK-0013 was not moved to complete: {complete_path}"
    assert not refined_path.exists(), f"TASK-0013 still exists in refined: {refined_path}"


@then('the cascade unblocking evaluator identifies "TASK-0014" as newly unblocked')
def then_evaluator_identifies_14_unblocked(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    assert "TASK-0014" in res.stdout or (repo_ctx["repo"] / "docs" / "project" / "backlog" / "refined" / "0014-downstream.md").exists()


@then('"TASK-0014" is automatically promoted to "docs/project/backlog/refined/"')
def then_task_14_promoted_to_refined(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    promoted_path = repo / "docs" / "project" / "backlog" / "refined" / "0014-downstream.md"
    proposed_path = repo / "docs" / "project" / "backlog" / "proposed" / "0014-downstream.md"
    assert promoted_path.exists(), f"TASK-0014 was not promoted to refined: {promoted_path}"
    assert not proposed_path.exists(), f"TASK-0014 still in proposed: {proposed_path}"


@then('"PRIORITY.md" is updated atomically to reflect "TASK-0014 (Refined)".')
def then_priority_md_updated_to_refined(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    p_content = (repo / "docs" / "project" / "backlog" / "PRIORITY.md").read_text(encoding="utf-8")
    assert "**TASK-0014 (Refined)**" in p_content
    assert "refined/0014-downstream.md" in p_content


# --- Scenario 2 Steps ---

@given("the ready buffer already contains 10 tasks (at target buffer capacity)")
def given_buffer_at_target_capacity(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"
    p_file = backlog_dir / "PRIORITY.md"
    p_lines = [p_file.read_text(encoding="utf-8").strip()]

    # Populate 10 other tasks in refined
    for i in range(1, 11):
        tid = f"{i:04d}"
        t = Task(
            id=tid,
            title=f"Buffer Filler Task {i}",
            status="Refined",
            priority_rank=i,
            file_path=backlog_dir / "refined" / f"{tid}-filler.md",
        )
        write_task_file(t)
        p_lines.append(f"- **TASK-{tid} (Refined)**: [`{tid}-filler`](refined/{tid}-filler.md)")

    # Also add TASK-0024 in complete or as claimed/refined task
    t24 = Task(
        id="0024",
        title="Prerequisite Task 24",
        status="Refined",
        priority_rank=50,
        file_path=backlog_dir / "refined" / "0024-task.md",
    )
    write_task_file(t24)
    p_lines.append("- **TASK-0024 (Refined)**: [`0024-task`](refined/0024-task.md)")

    p_file.write_text("\n".join(p_lines) + "\n", encoding="utf-8")


@given('proposed task "TASK-0025" depends solely on completed task "TASK-0024"')
def given_task_25_depends_on_24(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"
    t25 = Task(
        id="0025",
        title="Excess Downstream Task",
        status="Proposed",
        dependencies=["TASK-0024"],
        priority_rank=90,
        file_path=backlog_dir / "proposed" / "0025-excess.md",
    )
    write_task_file(t25)

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(
        p_file.read_text(encoding="utf-8")
        + "- **TASK-0025 (Proposed)**: [`0025-excess`](proposed/0025-excess.md)\n",
        encoding="utf-8",
    )


@when('"TASK-0024" is completed via "spec-ops queue complete TASK-0024"')
def when_complete_task_24(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["queue", "complete", "TASK-0024"])
    repo_ctx["result"] = res


@then('"TASK-0025" frontmatter is tagged with "unblocked: true"')
def then_task_25_tagged_unblocked(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    t25_file = repo / "docs" / "project" / "backlog" / "proposed" / "0025-excess.md"
    content = t25_file.read_text(encoding="utf-8")
    assert "unblocked: true" in content or "unblocked: True" in content


@then('"TASK-0025" remains in "docs/project/backlog/proposed/" to prevent over-buffering beyond the target limit of 10')
def then_task_25_remains_in_proposed(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    t25_prop = repo / "docs" / "project" / "backlog" / "proposed" / "0025-excess.md"
    t25_ref = repo / "docs" / "project" / "backlog" / "refined" / "0025-excess.md"
    assert t25_prop.exists(), f"TASK-0025 missing from proposed: {t25_prop}"
    assert not t25_ref.exists(), f"TASK-0025 unexpectedly promoted to refined: {t25_ref}"


@then('a log message reports "TASK-0025 unblocked but held in proposed to preserve lean ready buffer (10/10)".')
def then_log_message_reports_held(repo_ctx: dict[str, Any]):
    res = repo_ctx["result"]
    combined = res.stdout + "\n" + res.stderr
    expected = "TASK-0025 unblocked but held in proposed to preserve lean ready buffer (10/10)"
    assert expected in combined, f"Expected message '{expected}' not in output:\n{combined}"


# --- Scenario 3 Steps ---

@given("autonomous agent workers are registered to listen for queue events")
def given_workers_registered_for_events(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"

    t30 = Task(
        id="0030",
        title="Telemetry Trigger Task",
        status="Refined",
        priority_rank=1,
        target_bc="backlog",
        file_path=backlog_dir / "refined" / "0030-trigger.md",
    )
    write_task_file(t30)

    t31 = Task(
        id="0031",
        title="Telemetry Unblocked Task",
        status="Proposed",
        dependencies=["TASK-0030"],
        priority_rank=2,
        target_bc="backlog",
        file_path=backlog_dir / "proposed" / "0031-target.md",
    )
    write_task_file(t31)

    p_file = backlog_dir / "PRIORITY.md"
    p_file.write_text(
        p_file.read_text(encoding="utf-8")
        + "- **TASK-0030 (Refined)**: [`0030-trigger`](refined/0030-trigger.md)\n"
        + "- **TASK-0031 (Proposed)**: [`0031-target`](proposed/0031-target.md)\n",
        encoding="utf-8",
    )


@when('"TASK-0030" completes and reactively promotes "TASK-0031" into "refined/"')
def when_task_30_completes(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["queue", "complete", "TASK-0030"])
    repo_ctx["result"] = res
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    assert (repo / "docs" / "project" / "backlog" / "refined" / "0031-target.md").exists()


@then('SpecOps emits a machine-readable JSON event to ".spec-ops/events/unblocked.json"')
def then_emits_json_event(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    event_path = repo / ".spec-ops" / "events" / "unblocked.json"
    assert event_path.exists(), f"Telemetry event file missing at {event_path}"
    data = json.loads(event_path.read_text(encoding="utf-8"))
    assert data["event"] == "task_unblocked"


@then("the event payload contains the unblocked task ID, target bounded context, and priority rank.")
def then_event_payload_contains_required_fields(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    event_path = repo / ".spec-ops" / "events" / "unblocked.json"
    data = json.loads(event_path.read_text(encoding="utf-8"))
    assert data["task_id"] == "TASK-0031"
    assert data["target_bc"] == "backlog"
    assert data["priority_rank"] == 2
