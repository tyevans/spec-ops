"""Executable BDD acceptance tests for US-0029: Machine-Readable JSON Output for CLI Inspection."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0029_cli_inspection_json.feature")

CLI_ENV = {**os.environ, "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


@pytest.fixture
def us0029_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="JsonCliApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Morgan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "morgan@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "cli_result": None,
        "json_payload": None,
        "violating_file": None,
        "mismatched_task_id": None,
    }


# ==============================================================================
# Scenario: Inspecting Next Backlog Task with Machine-Readable JSON
# ==============================================================================


@given('a project backlog with refined tasks in "docs/project/backlog/refined/"')
def setup_refined_tasks(us0029_context: dict[str, Any]):
    repo: Path = us0029_context["repo"]
    refined_dir = repo / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)

    task_file = refined_dir / "0030-json-output-task.md"
    task = Task(
        id="0030",
        title="Structured CLI JSON Inspection",
        status="Refined",
        target_bc="cli",
        dependencies=[],
        governing_adrs=["ADR-0001", "ADR-0002", "ADR-0003"],
        governing_prds=["PRD-0004"],
        governing_stories=["US-0029"],
        file_path=task_file,
    )
    write_task_file(task)

    # Sync into PRIORITY.md
    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Queue\n\n- **TASK-0030 (Refined)**: [`0030-json-output-task`](refined/0030-json-output-task.md)\n",
        encoding="utf-8",
    )


@when('the agent runs "spec-ops queue next --json"')
def run_queue_next_json(us0029_context: dict[str, Any]):
    repo: Path = us0029_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "queue", "next", "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    us0029_context["cli_result"] = res
    if res.stdout.strip():
        us0029_context["json_payload"] = json.loads(res.stdout)


@then("the command exits with return code 0")
def verify_return_code_zero(us0029_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = us0029_context["cli_result"]
    assert res.returncode == 0


@then("the output is valid JSON conforming to the Task schema")
def verify_valid_task_json_schema(us0029_context: dict[str, Any]):
    payload = us0029_context["json_payload"]
    assert isinstance(payload, dict)
    assert payload.get("id") == "0030"
    assert payload.get("canonical_id") == "TASK-0030"
    assert payload.get("title") == "Structured CLI JSON Inspection"


@then('the JSON payload includes fields "id", "canonical_id", "title", "target_bc", "dependencies", and "governing_adrs"')
def verify_mandatory_task_fields(us0029_context: dict[str, Any]):
    payload: dict[str, Any] = us0029_context["json_payload"]
    mandatory_fields = ["id", "canonical_id", "title", "target_bc", "dependencies", "governing_adrs"]
    for field in mandatory_fields:
        assert field in payload, f"Field '{field}' missing from JSON payload"


@then("no ANSI color codes or decorative terminal banners are present in the output.")
def verify_no_ansi_codes_or_banners(us0029_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = us0029_context["cli_result"]
    stdout = res.stdout
    assert not ANSI_ESCAPE_RE.search(stdout), "ANSI escape sequence detected in JSON output"
    assert "===" not in stdout, "Terminal banner detected in JSON output"


# ==============================================================================
# Scenario: Parsing Health Violations via Structured JSON
# ==============================================================================


@given("a repository containing one file exceeding 500 lines and one unsynced priority task")
def setup_health_violations(us0029_context: dict[str, Any]):
    repo: Path = us0029_context["repo"]

    # 1. Create file exceeding 500 lines
    oversized = repo / "src" / "oversized_module.py"
    oversized.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Line {i}\n" for i in range(1, 520)]
    oversized.write_text("".join(lines), encoding="utf-8")
    us0029_context["violating_file"] = oversized

    # 2. Create unsynced priority task in proposed/ but marked Complete in PRIORITY.md
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0099-unsynced-task.md"
    task = Task(id="0099", title="Unsynced Task", status="Proposed", file_path=task_file)
    write_task_file(task)

    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Queue\n\n- **TASK-0099 (Complete)**: [`0099-unsynced-task`](complete/0099-unsynced-task.md)\n",
        encoding="utf-8",
    )
    us0029_context["mismatched_task_id"] = "TASK-0099"


@when('the agent runs "spec-ops health --json"')
def run_health_json(us0029_context: dict[str, Any]):
    repo: Path = us0029_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health", "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    us0029_context["cli_result"] = res
    if res.stdout.strip():
        us0029_context["json_payload"] = json.loads(res.stdout)


@then("the command exits with return code 1")
def verify_return_code_one(us0029_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = us0029_context["cli_result"]
    assert res.returncode == 1


@then('the output is a valid JSON object containing "status: error"')
def verify_status_error_in_json(us0029_context: dict[str, Any]):
    payload = us0029_context["json_payload"]
    assert isinstance(payload, dict)
    assert payload.get("status") == "error"
    assert payload.get("healthy") is False


@then('the "violations" array contains the violating file path, line count, and offending rule "ADR-0002"')
def verify_violations_array(us0029_context: dict[str, Any]):
    payload: dict[str, Any] = us0029_context["json_payload"]
    violations = payload.get("violations", [])
    assert len(violations) >= 1

    v0 = violations[0]
    assert "oversized_module.py" in str(v0.get("path"))
    assert v0.get("lines", 0) >= 519
    assert v0.get("rule") == "ADR-0002"


@then('the "priority_sync" object reports the mismatched task IDs.')
def verify_priority_sync_mismatched_tasks(us0029_context: dict[str, Any]):
    payload: dict[str, Any] = us0029_context["json_payload"]
    priority_sync = payload.get("priority_sync", {})
    assert priority_sync.get("ok") is False
    mismatched = priority_sync.get("mismatched_tasks", [])
    assert "TASK-0099" in mismatched
