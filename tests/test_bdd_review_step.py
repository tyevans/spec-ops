"""Executable BDD scenarios for US-0115: Concurrent Architectural Task Review."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.worker import BacklogWorkerEngine
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0115_task_review_step.feature")


@pytest.fixture
def review_bdd_context(tmp_path: Path) -> dict[str, Any]:
    """Shared state container for US-0115 BDD scenarios."""
    return {"dir": tmp_path, "res": None}


@given("an initialized SpecOps project with an isolated task worktree")
def setup_project_with_worktree(review_bdd_context: dict[str, Any]):
    root = review_bdd_context["dir"]
    init_project(root, name="BddReviewApp")
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    (root / "README.md").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

    config = SpecOpsConfig(root_dir=root)
    config.quality.preflight = ["python3 -c 'print(\"CI OK\")'"]
    config.execution.agent_command = "python3 -c 'import pathlib; pathlib.Path(\"app.py\").write_text(\"def run(): pass\\n\")'"
    config.execution.reviewer_command = "python3 -c 'print(\"STATUS: APPROVED\\nLGTM\")'"

    task = Task(
        id="0115",
        title="Review Step Implementation",
        status="Refined",
        target_bc="core",
        governing_adrs=["ADR-0003"],
        body="Implement review step adhering to architecture standards.",
        file_path=root / "docs" / "project" / "backlog" / "refined" / "0115-task.md",
    )
    review_bdd_context["config"] = config
    review_bdd_context["worker"] = BacklogWorkerEngine(config)
    review_bdd_context["task"] = task


@when("the worker executes the task with concurrent CI preflight and architectural review")
def execute_worker_concurrent(review_bdd_context: dict[str, Any]):
    worker: BacklogWorkerEngine = review_bdd_context["worker"]
    task = review_bdd_context["task"]
    root = review_bdd_context["dir"]
    ok, log = worker.invoke_agent(task, root, dry_run=False)
    review_bdd_context["invoke_ok"] = ok
    review_bdd_context["invoke_log"] = log


@then("both CI preflight and architectural review approve the implementation")
def verify_both_approved(review_bdd_context: dict[str, Any]):
    assert review_bdd_context["invoke_ok"] is True
    assert "Preflight and architectural review passed" in review_bdd_context["invoke_log"]


@then("the task modifications are verified cleanly")
def verify_task_modifications(review_bdd_context: dict[str, Any]):
    root = review_bdd_context["dir"]
    assert (root / "app.py").is_file()


@given("an isolated task worktree where reviewer requests changes on attempt 1")
def setup_worktree_reviewer_requests_changes(review_bdd_context: dict[str, Any]):
    root = review_bdd_context["dir"]
    init_project(root, name="BddRepairApp")
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    (root / "README.md").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

    counter_file = root / ".bdd_rev_counter"
    config = SpecOpsConfig(root_dir=root)
    config.quality.preflight = ["python3 -c 'print(\"CI OK\")'"]
    config.execution.agent_command = (
        "python3 -c 'import pathlib; "
        "p = pathlib.Path(\"service.py\"); "
        "c = p.read_text() if p.exists() else \"\"; "
        "p.write_text(c + \"# code\\n\")'"
    )
    config.execution.reviewer_command = (
        f"python3 -c 'import pathlib; "
        f"cf = pathlib.Path(\"{counter_file}\"); "
        f"count = int(cf.read_text()) if cf.exists() else 0; "
        f"cf.write_text(str(count + 1)); "
        f"print(\"STATUS: CHANGES_REQUESTED\\n## Review Feedback\\n- Missing docstring\") if count == 0 else print(\"STATUS: APPROVED\")'"
    )
    config.execution.agent_max_attempts = 3

    task = Task(
        id="0116",
        title="Repair Review Feedback",
        status="Refined",
        target_bc="core",
        governing_adrs=["ADR-0003"],
        body="Implement repair logic.",
        file_path=root / "docs" / "project" / "backlog" / "refined" / "0116-task.md",
    )
    review_bdd_context["config"] = config
    review_bdd_context["worker"] = BacklogWorkerEngine(config)
    review_bdd_context["task"] = task
    review_bdd_context["counter_file"] = counter_file


@when("the worker feeds review feedback into the implementation agent repair loop")
def execute_worker_repair(review_bdd_context: dict[str, Any]):
    worker: BacklogWorkerEngine = review_bdd_context["worker"]
    task = review_bdd_context["task"]
    root = review_bdd_context["dir"]
    ok, log = worker.invoke_agent(task, root, dry_run=False)
    review_bdd_context["repair_ok"] = ok
    review_bdd_context["repair_log"] = log


@then("the agent resolves the review feedback on attempt 2")
def verify_repair_attempt(review_bdd_context: dict[str, Any]):
    counter_file = review_bdd_context["counter_file"]
    assert counter_file.read_text().strip() == "2"
    assert "passed on attempt 2" in review_bdd_context["repair_log"]


@then("the task passes review and preflight verification")
def verify_task_passes_all(review_bdd_context: dict[str, Any]):
    assert review_bdd_context["repair_ok"] is True
