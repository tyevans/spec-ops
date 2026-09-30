"""Executable BDD scenarios for US-0097: Governed Worktree Sandboxing and Test Harness Scaffolding."""

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

scenarios("features/us_0097_spike_sandboxing.feature")


@pytest.fixture
def spike_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="SpikeApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Morgan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "morgan@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "last_res": None,
        "spike_id": "SPIKE-0002",
        "worktree": repo / ".worktrees" / "spike-0002",
    }


# ============================================================================
# Scenario: Scaffolding a sandboxed spike worktree and hypothesis test harness
# ============================================================================


@given(parsers.parse('a proposed spike task "{spike_id}" with hypothesis "{hypothesis}"'))
def setup_proposed_spike_task(spike_context: dict[str, Any], spike_id: str, hypothesis: str):
    repo: Path = spike_context["repo"]
    spike_context["spike_id"] = spike_id
    spike_context["hypothesis"] = hypothesis

    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0002-duckdb-spike.md"

    task = Task(
        id=spike_id,
        title="DuckDB Benchmark Spike",
        status="Proposed",
        hypothesis=hypothesis,
        timebox="2h",
        body=f"Investigate hypothesis: {hypothesis}",
        file_path=task_file,
    )
    write_task_file(task)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"docs: propose {spike_id}"], cwd=repo, check=True, capture_output=True)


@when(parsers.parse('Morgan executes "{cmd}"'))
def morgan_executes_cli_command(spike_context: dict[str, Any], cmd: str):
    repo: Path = spike_context["repo"]
    tokens = cmd.split()
    args = [sys.executable, "-m", "spec_ops.cli.main"] + tokens[1:]

    res = subprocess.run(
        args,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    spike_context["last_res"] = res


@then(parsers.parse('an isolated git worktree is created at "{wt_path}" on branch "{branch}"'))
def verify_worktree_and_branch_created(spike_context: dict[str, Any], wt_path: str, branch: str):
    repo: Path = spike_context["repo"]
    full_wt = repo / wt_path
    assert full_wt.exists(), f"Worktree {full_wt} does not exist"

    chk = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert branch in chk.stdout, f"Branch {branch} was not created"


@then(parsers.parse('an isolated harness directory is generated at "{harness_path}" containing:'))
def verify_harness_contents(spike_context: dict[str, Any], harness_path: str, datatable: Any = None):
    repo: Path = spike_context["repo"]
    wt: Path = spike_context["worktree"]
    harness_dir = wt / harness_path

    assert harness_dir.exists(), f"Harness dir {harness_dir} does not exist"
    assert (wt / "spikes" / "spike_0002" / "harness.py").exists()
    assert (wt / "spikes" / "spike_0002" / "test_spike.py").exists()
    assert (wt / "spikes" / "spike_0002" / "README.md").exists()


@then(parsers.parse('"{test_file_path}" contains an executable benchmark skeleton asserting the hypothesis.'))
def verify_test_spike_skeleton(spike_context: dict[str, Any], test_file_path: str):
    wt: Path = spike_context["worktree"]
    test_file = wt / test_file_path
    assert test_file.exists()
    content = test_file.read_text(encoding="utf-8")
    assert "def test_" in content
    assert "run_benchmark" in content
    assert spike_context["hypothesis"] in content


# ============================================================================
# Scenario: Enforcing write isolation to prevent spike code from modifying "src/"
# ============================================================================


@given(parsers.parse('Morgan is executing spike code inside "{wt_path}"'))
def morgan_in_worktree(spike_context: dict[str, Any], wt_path: str):
    repo: Path = spike_context["repo"]
    wt: Path = repo / wt_path
    if not wt.exists():
        setup_proposed_spike_task(spike_context, "SPIKE-0002", "DuckDB outperforms SQLite")
        morgan_executes_cli_command(spike_context, "spec-ops spike start SPIKE-0002")
    assert wt.exists()
    spike_context["current_worktree"] = wt


@when(parsers.parse('Morgan attempts to edit or create files within "{forbidden_dir}"'))
def attempt_edit_src(spike_context: dict[str, Any], forbidden_dir: str):
    wt: Path = spike_context["current_worktree"]
    target_dir = wt / forbidden_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    polluted_file = target_dir / "unauthorized_patch.py"
    polluted_file.write_text("# Contaminated code\n", encoding="utf-8")

    # Run in-worktree preflight hook
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "spike", "preflight"],
        cwd=wt,
        capture_output=True,
        text=True,
    )
    spike_context["preflight_res"] = res


@then("the in-worktree preflight hook rejects the modification")
def verify_preflight_hook_rejects(spike_context: dict[str, Any]):
    res = spike_context["preflight_res"]
    assert res.returncode != 0, f"Expected non-zero return code, got {res.returncode}"


@then(parsers.parse('displays "{expected_message}".'))
def verify_rejection_message(spike_context: dict[str, Any], expected_message: str):
    res = spike_context["preflight_res"]
    output = (res.stdout + "\n" + res.stderr).strip()
    assert expected_message in output


# ============================================================================
# Scenario: Enforcing spike timebox expiration
# ============================================================================


@given(parsers.parse('"{spike_id}" specifies a frontmatter "timebox: {timebox}"'))
def set_spike_timebox(spike_context: dict[str, Any], spike_id: str, timebox: str):
    repo: Path = spike_context["repo"]
    wt: Path = repo / ".worktrees" / "spike-0002"
    if not wt.exists():
        setup_proposed_spike_task(spike_context, spike_id, "DuckDB outperforms SQLite")
        morgan_executes_cli_command(spike_context, f"spec-ops spike start {spike_id}")
    spike_context["timebox"] = timebox
    spike_context["current_worktree"] = wt


@given(parsers.parse("the worker has spent {hours:d} hours in the spike worktree without recording empirical findings"))
def simulate_timebox_elapsed(spike_context: dict[str, Any], hours: int):
    spike_context["simulated_elapsed"] = hours * 3600.0


@when(parsers.parse('the worker runs "{cmd}"'))
def worker_runs_check(spike_context: dict[str, Any], cmd: str):
    wt: Path = spike_context.get("current_worktree") or spike_context["worktree"]
    tokens = cmd.split()
    elapsed = str(spike_context.get("simulated_elapsed", 7200.0))
    args = [sys.executable, "-m", "spec_ops.cli.main"] + tokens[1:] + ["--elapsed", elapsed]

    res = subprocess.run(
        args,
        cwd=wt,
        capture_output=True,
        text=True,
    )
    spike_context["check_res"] = res


@then(parsers.parse('SpecOps issues a timebox warning: "{expected_warning}".'))
def verify_timebox_warning(spike_context: dict[str, Any], expected_warning: str):
    res = spike_context["check_res"]
    output = (res.stdout + "\n" + res.stderr).strip()
    assert expected_warning in output
