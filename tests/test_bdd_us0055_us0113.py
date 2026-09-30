"""Executable BDD scenarios for commit verification and dual-custody gate (US-0055, US-0113)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios(
    "features/us_0055_commit_signing_and_dual_custody.feature",
    "features/us_0113_cryptographic_commit_verification_dual_custody.feature",
)


@pytest.fixture
def bdd_signing_context(tmp_path: Path) -> dict[str, Any]:
    """Sets up an initialized git repository with SpecOps structure."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

    backlog = repo / "docs" / "project" / "backlog"
    refined = backlog / "refined"
    complete = backlog / "complete"
    proposed = backlog / "proposed"
    refined.mkdir(parents=True)
    complete.mkdir(parents=True)
    proposed.mkdir(parents=True)

    priority_file = backlog / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Queue\n\n1. **TASK-0042 (Refined)**: [`TASK-0042`](refined/0042-autonomous-feature.md)\n",
        encoding="utf-8",
    )

    toml_file = repo / "specops.toml"
    toml_file.write_text(
        '[project]\nname = "SecureGateApp"\ndocs_dir = "docs/project"\n',
        encoding="utf-8",
    )

    (repo / "setup.cfg").write_text("[mutmut]\nsource_paths = .\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "SecureGateApp"\n\n[tool.mutmut]\nsource_paths = ["."]\n',
        encoding="utf-8",
    )

    (repo / "README.md").write_text("# SecureGateApp\n", encoding="utf-8")

    # Base task in refined on main
    task_file = refined / "0042-autonomous-feature.md"
    task = Task(
        id="0042",
        title="Autonomous Feature",
        status="Refined",
        target_bc="security",
        claimed_by="worker-1",
        branch="feat/0042-autonomous-feature",
        file_path=task_file,
    )
    write_task_file(task)

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit on main"], cwd=repo, check=True, capture_output=True)

    # Create feature branch with changes
    subprocess.run(["git", "checkout", "-b", "feat/0042-autonomous-feature"], cwd=repo, check=True, capture_output=True)
    (repo / "feature.py").write_text("print('autonomous feature code')\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: implement autonomous feature"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "task_id": "TASK-0042",
        "cli_res": None,
        "task": task,
    }


# ==============================================================================
# Given Steps
# ==============================================================================


@given('a project configured with "[security.compliance] require_signed_commits = true"')
def project_configured_require_signed_commits(bdd_signing_context: dict[str, Any]):
    repo: Path = bdd_signing_context["repo"]
    toml_file = repo / "specops.toml"
    toml_file.write_text(
        '[project]\nname = "SecureGateApp"\n\n[security.compliance]\nrequire_signed_commits = true\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "specops.toml"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: require signed commits"], cwd=repo, check=True, capture_output=True)


@given("an autonomous agent has passed all preflight checks on a feature branch")
@given('an autonomous agent has passed all preflight checks on a feature branch for task "TASK-0042"')
def autonomous_agent_preflight_passed(bdd_signing_context: dict[str, Any]):
    repo: Path = bdd_signing_context["repo"]
    # Ensure task is marked claimed by agent and has no signed_off_by
    task_file = repo / "docs" / "project" / "backlog" / "refined" / "0042-autonomous-feature.md"
    task = Task(
        id="0042",
        title="Autonomous Feature",
        status="Refined",
        target_bc="security",
        claimed_by="worker-1",
        branch="feat/0042-autonomous-feature",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_signing_context["task"] = task


@given(parsers.parse('an authorized human reviewer executes "spec-ops review sign TASK-0042 --identity \'{identity}\'"'))
def human_reviewer_executes_review_sign(bdd_signing_context: dict[str, Any], identity: str):
    repo: Path = bdd_signing_context["repo"]

    # Configure authorized signers in specops.toml
    toml_file = repo / "specops.toml"
    toml_file.write_text(
        f'[project]\nname = "SecureGateApp"\n\n[security.compliance]\nauthorized_signers = ["{identity}"]\n',
        encoding="utf-8",
    )

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "review", "sign", "TASK-0042", "--identity", identity],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_signing_context["cli_res"] = res


# ==============================================================================
# When Steps
# ==============================================================================


@when('"spec-ops queue complete <task-id>" or worker squash-merge is executed on a branch with unsigned commits')
@when('the agent attempts to finalize and merge the task via "spec-ops queue complete TASK-0042"')
@when("the agent attempts to finalize the task without human approval")
def execute_queue_complete(bdd_signing_context: dict[str, Any]):
    repo: Path = bdd_signing_context["repo"]
    task_id: str = bdd_signing_context["task_id"]

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "queue", "complete", task_id],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_signing_context["cli_res"] = res


@when("the cryptographic signature is verified against the authorized signers keyring")
def signature_verified_against_keyring(bdd_signing_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_signing_context["cli_res"]
    assert res.returncode == 0


# ==============================================================================
# Then Steps
# ==============================================================================


@then("the command aborts with returncode 1")
def verify_command_aborts_returncode_1(bdd_signing_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_signing_context["cli_res"]
    assert res.returncode == 1


@then('outputs "Compliance Violation: Commit lacks valid cryptographic signature (GPG/SSH)".')
@then(parsers.re(r'outputs "Compliance Violation: Commit (?P<sha>\S+)?\s*lacks valid cryptographic signature \(GPG/SSH\)".?'))
def verify_compliance_violation_output(bdd_signing_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_signing_context["cli_res"]
    combined = (res.stderr + "\n" + res.stdout)
    if "Compliance Violation: Commit" not in combined:
        print("DEBUG COMBINED:\n", combined)
    assert "Compliance Violation: Commit" in combined
    assert "lacks valid cryptographic signature (GPG/SSH)" in combined


@then('SpecOps blocks task transition to "complete/"')
@then('SpecOps blocks the task transition to "complete/"')
def verify_blocks_transition(bdd_signing_context: dict[str, Any]):
    repo: Path = bdd_signing_context["repo"]
    res: subprocess.CompletedProcess = bdd_signing_context["cli_res"]
    assert res.returncode == 1

    refined_file = repo / "docs" / "project" / "backlog" / "refined" / "0042-autonomous-feature.md"
    complete_file = repo / "docs" / "project" / "backlog" / "complete" / "0042-autonomous-feature.md"
    assert refined_file.exists()
    assert not complete_file.exists()


@then('outputs "Dual-Custody Gate: Autonomous agent task requires verified human review sign-off. Run \'spec-ops review sign TASK-0042 --identity <key-id>\'".')
@then('requires an authorized human reviewer to execute "spec-ops review sign <task-id> --identity <key-id>"')
def verify_dual_custody_gate_output(bdd_signing_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_signing_context["cli_res"]
    combined = (res.stderr + "\n" + res.stdout)
    assert "Dual-Custody Gate: Autonomous agent task requires verified human review sign-off" in combined
    assert "spec-ops review sign" in combined


@then('task frontmatter records "signed_off_by: \'Riley <riley@example.com>\'" and sign-off timestamp')
def verify_task_frontmatter_records_signoff(bdd_signing_context: dict[str, Any]):
    repo: Path = bdd_signing_context["repo"]
    task_file = repo / "docs" / "project" / "backlog" / "refined" / "0042-autonomous-feature.md"
    content = task_file.read_text(encoding="utf-8")
    assert "signed_off_by: Riley <riley@example.com>" in content
    assert "signed_off_at:" in content


@then('subsequent execution of "spec-ops queue complete TASK-0042" merges cleanly to "main" with the structured "SpecOps-Signed-By" git trailer.')
def verify_subsequent_queue_complete_merges_cleanly(bdd_signing_context: dict[str, Any]):
    repo: Path = bdd_signing_context["repo"]
    task_id: str = bdd_signing_context["task_id"]

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "queue", "complete", task_id],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "passed integration gate" in res.stdout

    # Verify task file is now in complete/
    complete_file = repo / "docs" / "project" / "backlog" / "complete" / "0042-autonomous-feature.md"
    assert complete_file.exists()

    # Verify git log on main contains SpecOps-Signed-By trailer
    log_res = subprocess.run(
        ["git", "log", "-n", "1", "--format=%B"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "SpecOps-Signed-By: Riley <riley@example.com>" in log_res.stdout
    assert "SpecOps-Task: TASK-0042" in log_res.stdout


@then('once signed, task frontmatter records "signed_off_by: <reviewer>" and the task merges cleanly.')
def verify_once_signed_records_and_merges_cleanly(bdd_signing_context: dict[str, Any]):
    repo: Path = bdd_signing_context["repo"]
    task_id: str = bdd_signing_context["task_id"]

    # Sign the task
    sign_res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "review", "sign", task_id, "--identity", "Riley <riley@example.com>"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert sign_res.returncode == 0

    task_file = repo / "docs" / "project" / "backlog" / "refined" / "0042-autonomous-feature.md"
    assert "signed_off_by: Riley <riley@example.com>" in task_file.read_text(encoding="utf-8")

    # Complete the task
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "queue", "complete", task_id],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "passed integration gate" in res.stdout

    complete_file = repo / "docs" / "project" / "backlog" / "complete" / "0042-autonomous-feature.md"
    assert complete_file.exists()
