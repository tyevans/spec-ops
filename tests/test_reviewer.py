"""Unit and integration tests for architectural and specification review engine."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from spec_ops.backlog.queue import BacklogQueue
from spec_ops.backlog.reviewer import (
    ReviewResult,
    TaskReviewEngine,
    build_review_prompt,
    parse_review_output,
)
from spec_ops.worker import BacklogWorkerEngine, WorkerResult
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project


def make_dummy_task(
    id_str: str = "0099",
    title: str = "Implement Widget Service",
    body: str = "Must implement the widget service adhering to ADR-0003 and ADR-0007.",
    target_bc: str = "widget",
    governing_adrs: list[str] | None = None,
) -> Task:
    return Task(
        id=id_str,
        title=title,
        status="Refined",
        target_bc=target_bc,
        governing_adrs=governing_adrs or ["ADR-0003", "ADR-0007"],
        governing_prds=["PRD-0004"],
        governing_stories=["US-0028"],
        body=body,
        file_path=Path("docs/project/backlog/refined/0099-test.md"),
    )


def test_build_review_prompt():
    config = SpecOpsConfig()
    task = make_dummy_task()
    worktree = Path("/tmp/dummy-worktree")
    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new"

    prompt = build_review_prompt(task, config, worktree, diff_text=diff)

    assert "Architectural & Specification Review: TASK-0099" in prompt
    assert "CRITICAL INVARIANT: CI PREFLIGHT CONCURRENCY" in prompt
    assert "Do NOT run test suites, linters, or typecheckers." in prompt
    assert "Target Bounded Context: widget" in prompt
    assert "ADR-0003, ADR-0007" in prompt
    assert "Must implement the widget service adhering to ADR-0003 and ADR-0007." in prompt
    assert "STATUS: APPROVED" in prompt
    assert "STATUS: CHANGES_REQUESTED" in prompt
    assert diff in prompt


def test_parse_review_output_approved():
    approved_text = """
    I have inspected the modifications.
    STATUS: APPROVED
    The implementation is clean, adheres to bounded contexts, and covers the full specification.
    """
    res = parse_review_output(approved_text)
    assert res.approved is True
    assert res.feedback == ""


def test_parse_review_output_changes_requested():
    changes_text = """
    STATUS: CHANGES_REQUESTED

    ## Review Feedback
    - Missing error handling when ID is negative.
    - Violates ADR-0003: private mock used in tests.
    """
    res = parse_review_output(changes_text)
    assert res.approved is False
    assert "Missing error handling when ID is negative" in res.feedback
    assert "Violates ADR-0003" in res.feedback


def test_parse_review_output_empty():
    res = parse_review_output("")
    assert res.approved is False
    assert "Empty response" in res.feedback


def test_parse_review_output_heuristics():
    lgtm_text = "APPROVED: All acceptance criteria and ADRs verified."
    res = parse_review_output(lgtm_text)
    assert res.approved is True

    rejected_text = "STATUS: REJECTED\nIncomplete implementation of task requirements."
    res_rej = parse_review_output(rejected_text)
    assert res_rej.approved is False
    assert "Incomplete implementation" in res_rej.feedback


def test_task_review_engine_get_git_diff(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)

    test_file = tmp_path / "hello.py"
    test_file.write_text("print('v1')\n", encoding="utf-8")
    subprocess.run(["git", "add", "hello.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

    # Modify tracked file
    test_file.write_text("print('v2')\n", encoding="utf-8")

    # Add untracked file
    untracked_file = tmp_path / "new_module.py"
    untracked_file.write_text("def new(): pass\n", encoding="utf-8")

    cfg = SpecOpsConfig(root_dir=tmp_path)
    engine = TaskReviewEngine(cfg)
    diff = engine.get_git_diff(tmp_path)

    assert "-print('v1')" in diff
    assert "+print('v2')" in diff
    assert "new_module.py" in diff


def test_task_review_engine_dry_run(tmp_path: Path):
    cfg = SpecOpsConfig(root_dir=tmp_path)
    engine = TaskReviewEngine(cfg)
    task = make_dummy_task()

    res = engine.run_review(task, tmp_path, dry_run=True)
    assert res.approved is True
    prompt_file = tmp_path / ".task-review-prompt.md"
    assert prompt_file.is_file()
    assert "TASK-0099" in prompt_file.read_text(encoding="utf-8")


def test_worker_concurrent_preflight_and_review_both_pass(tmp_path: Path):
    init_project(tmp_path, name="ConcurrentReviewTest")
    config = SpecOpsConfig(root_dir=tmp_path)
    config.quality.preflight = ["python3 -c 'print(\"CI passed\")'"]
    # Script that writes code modification and outputs review approval
    agent_script = (
        "python3 -c 'import sys, pathlib; "
        "pathlib.Path(\"service.py\").write_text(\"class Service: pass\\n\"); "
        "print(\"agent done\")'"
    )
    reviewer_script = (
        "python3 -c 'print(\"STATUS: APPROVED\\nArchitectural invariants satisfied.\")'"
    )
    config.execution.agent_command = agent_script
    config.execution.reviewer_command = reviewer_script
    config.execution.agent_max_attempts = 2

    worker = BacklogWorkerEngine(config)
    task = make_dummy_task()

    # Pre-setup a dummy git repo for worktree
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("test", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

    ok, log = worker.invoke_agent(task, tmp_path, dry_run=False)
    assert ok is True
    assert "Preflight and architectural review passed" in log


def test_worker_review_feedback_repair_loop(tmp_path: Path):
    init_project(tmp_path, name="ReviewFeedbackRepairTest")
    config = SpecOpsConfig(root_dir=tmp_path)
    config.quality.preflight = ["python3 -c 'print(\"CI passed\")'"]

    # Implementation agent creates file on attempt 1, and updates it on attempt 2
    agent_script = (
        "python3 -c 'import sys, pathlib; "
        "p = pathlib.Path(\"service.py\"); "
        "content = p.read_text() if p.exists() else \"\"; "
        "p.write_text(content + \"# updated\\n\"); "
        "print(\"agent done\")'"
    )
    # Reviewer rejects on attempt 1, approves on attempt 2
    counter_file = tmp_path / ".review_counter"
    reviewer_script = (
        f"python3 -c 'import pathlib; "
        f"cf = pathlib.Path(\"{counter_file}\"); "
        f"count = int(cf.read_text()) if cf.exists() else 0; "
        f"cf.write_text(str(count + 1)); "
        f"print(\"STATUS: CHANGES_REQUESTED\\n## Review Feedback\\n- Missing docstring\") if count == 0 else print(\"STATUS: APPROVED\")'"
    )

    config.execution.agent_command = agent_script
    config.execution.reviewer_command = reviewer_script
    config.execution.agent_max_attempts = 3

    worker = BacklogWorkerEngine(config)
    task = make_dummy_task()

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("test", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

    ok, log = worker.invoke_agent(task, tmp_path, dry_run=False)
    assert ok is True
    assert "passed on attempt 2" in log

    # Verify that counter reached 2
    assert counter_file.read_text().strip() == "2"


def test_worker_skip_review_flag(tmp_path: Path):
    config = SpecOpsConfig(root_dir=tmp_path)
    config.quality.preflight = ["python3 -c 'print(\"CI passed\")'"]
    agent_script = (
        "python3 -c 'import pathlib; "
        "pathlib.Path(\"mod.py\").write_text(\"x = 1\\n\"); "
        "print(\"agent done\")'"
    )
    # Reviewer script would fail if invoked
    reviewer_script = "python3 -c 'print(\"STATUS: CHANGES_REQUESTED\\nFailure\")'"
    config.execution.agent_command = agent_script
    config.execution.reviewer_command = reviewer_script

    worker = BacklogWorkerEngine(config)
    task = make_dummy_task()

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("test", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

    # When skip_review=True, reviewer is not invoked and attempt 1 succeeds
    ok, log = worker.invoke_agent(task, tmp_path, dry_run=False, skip_review=True)
    assert ok is True
    assert "Preflight passed on attempt 1" in log
