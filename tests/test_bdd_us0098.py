"""Executable BDD scenarios for US-0098: Empirical Spike Validation and Automated ADR Synthesis."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.curator import BacklogCurator
from spec_ops.backlog.queue import write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project

scenarios("features/us_0098_spike_graduation.feature")


@pytest.fixture
def grad_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="GraduationApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Ensure baseline ADRs up to ADR-0009 exist
    adrs_accepted = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_accepted.mkdir(parents=True, exist_ok=True)
    (adrs_accepted / "adr-0008-agent-constitution-and-diataxis-documentation-standards.md").write_text(
        "# ADR-0008: Agent Constitution\n\n## Status\nAccepted\n", encoding="utf-8"
    )
    (adrs_accepted / "adr-0009-property-and-mutation-testing-with-hypothesis-and-mutmut.md").write_text(
        "# ADR-0009: Property and Mutation Testing\n\n## Status\nAccepted\n", encoding="utf-8"
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "last_res": None,
        "spike_id": "SPIKE-0002",
        "worktree": repo / ".worktrees" / "spike-0002",
        "dependent_task_file": None,
    }


# ============================================================================
# Scenario: Successfully graduating a proven spike with empirical benchmark data into an ADR
# ============================================================================


@given(parsers.parse('a completed spike "{spike_id}" with hypothesis "{hypothesis}"'))
def setup_completed_spike(grad_context: dict[str, Any], spike_id: str, hypothesis: str):
    repo: Path = grad_context["repo"]
    grad_context["spike_id"] = spike_id
    grad_context["hypothesis"] = hypothesis

    # Create proposed spike task
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    spike_task_file = proposed_dir / "0002-duckdb-spike.md"
    task = Task(
        id=spike_id,
        title="DuckDB Benchmark Spike",
        status="Proposed",
        hypothesis=hypothesis,
        timebox="2h",
        body=f"Investigate hypothesis: {hypothesis}",
        file_path=spike_task_file,
    )
    write_task_file(task)

    # Create a downstream task depending on SPIKE-0002
    downstream_file = proposed_dir / "0020-implement-duckdb-graph-engine.md"
    downstream_task = Task(
        id="0020",
        title="Implement DuckDB Graph Engine",
        status="Proposed",
        dependencies=[spike_id],
        body="Implement graph querying via DuckDB.",
        file_path=downstream_file,
    )
    write_task_file(downstream_task)
    grad_context["dependent_task_file"] = downstream_file

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: propose spike and dependent task"], cwd=repo, check=True, capture_output=True)

    # Start spike worktree
    start_cmd = [sys.executable, "-m", "spec_ops.cli.main", "spike", "start", spike_id]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")
    subprocess.run(start_cmd, cwd=repo, check=True, capture_output=True, env=env)


@given(parsers.parse('the spike test suite in "{test_file_path}" passes with recorded benchmark output: "{benchmark_output}"'))
def record_test_spike_output(grad_context: dict[str, Any], test_file_path: str, benchmark_output: str):
    repo: Path = grad_context["repo"]
    wt: Path = repo / ".worktrees" / "spike-0002"
    test_file = wt / test_file_path
    assert test_file.exists()

    # Append benchmark output to test_spike.py and record in benchmark.txt
    original = test_file.read_text(encoding="utf-8")
    test_file.write_text(original + f'\n# Recorded benchmark output: "{benchmark_output}"\n', encoding="utf-8")

    bench_txt = test_file.parent / "benchmark.txt"
    bench_txt.write_text(benchmark_output, encoding="utf-8")
    grad_context["benchmark_output"] = benchmark_output


@when(parsers.parse('Alex runs "{cmd}"'))
def alex_runs_command(grad_context: dict[str, Any], cmd: str):
    repo: Path = grad_context["repo"]
    tokens = shlex.split(cmd)
    args = [sys.executable, "-m", "spec_ops.cli.main"] + tokens[1:]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")

    res = subprocess.run(
        args,
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    grad_context["last_res"] = res


@then(parsers.parse('a new ADR file "{adr_rel_path}" is authored'))
def verify_adr_authored(grad_context: dict[str, Any], adr_rel_path: str):
    repo: Path = grad_context["repo"]
    adr_path = repo / adr_rel_path
    assert adr_path.exists(), (
        f"ADR file {adr_path} does not exist.\n"
        f"STDOUT: {grad_context['last_res'].stdout}\n"
        f"STDERR: {grad_context['last_res'].stderr}"
    )
    grad_context["authored_adr"] = adr_path


@then(parsers.parse('the ADR context and decision sections cite the empirical benchmark findings from "{spike_id}"'))
def verify_adr_cites_findings(grad_context: dict[str, Any], spike_id: str):
    adr_path: Path = grad_context["authored_adr"]
    content = adr_path.read_text(encoding="utf-8")
    assert "## Context" in content
    assert "## Decision" in content
    assert spike_id in content
    bench_out = grad_context.get("benchmark_output", "142ms")
    assert bench_out in content


@then(parsers.parse('"{spike_id}" is moved to "{dest_folder}" with status "{expected_status}"'))
def verify_spike_moved(grad_context: dict[str, Any], spike_id: str, dest_folder: str, expected_status: str):
    repo: Path = grad_context["repo"]
    complete_dir = repo / dest_folder
    assert complete_dir.exists()

    found = None
    for p in complete_dir.glob("*.md"):
        task = parse_task(p)
        if task.id == spike_id or task.canonical_id == f"SPIKE-{spike_id.replace('SPIKE-', '').zfill(4)}":
            found = task
            break

    assert found is not None, f"Spike {spike_id} not found in {dest_folder}"
    assert found.status == expected_status


@then(parsers.parse('all downstream tasks in "{folder}" listing "{spike_id}" as a dependency have that dependency resolved.'))
def verify_downstream_tasks_resolved(grad_context: dict[str, Any], folder: str, spike_id: str):
    dep_file: Path = grad_context["dependent_task_file"]
    assert dep_file.exists()
    task = parse_task(dep_file)
    assert spike_id not in task.dependencies


# ============================================================================
# Scenario: Documenting a disproven hypothesis with rationale and blocking dependent implementation slices
# ============================================================================


@given(parsers.parse('an architectural spike "{spike_id}" with hypothesis "{hypothesis}"'))
def setup_disproven_spike(grad_context: dict[str, Any], spike_id: str, hypothesis: str):
    repo: Path = grad_context["repo"]
    grad_context["spike_id"] = spike_id
    grad_context["hypothesis"] = hypothesis

    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    spike_task_file = proposed_dir / "0003-sqlite-spike.md"
    task = Task(
        id=spike_id,
        title="In-Memory SQLite Spike",
        status="Proposed",
        hypothesis=hypothesis,
        timebox="2h",
        body=f"Investigate hypothesis: {hypothesis}",
        file_path=spike_task_file,
    )
    write_task_file(task)

    # Downstream task depending on SPIKE-0003
    downstream_file = proposed_dir / "0021-sqlite-sync-engine.md"
    downstream_task = Task(
        id="0021",
        title="SQLite Sync Engine",
        status="Proposed",
        dependencies=[spike_id],
        body="Implement sync engine via in-memory SQLite.",
        file_path=downstream_file,
    )
    write_task_file(downstream_task)
    grad_context["dependent_task_file"] = downstream_file

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: propose spike 3"], cwd=repo, check=True, capture_output=True)

    start_cmd = [sys.executable, "-m", "spec_ops.cli.main", "spike", "start", spike_id]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")
    subprocess.run(start_cmd, cwd=repo, check=True, capture_output=True, env=env)


@given(parsers.parse("benchmark testing reveals p95 latency is {latency} (failing hypothesis)"))
def record_failing_benchmark(grad_context: dict[str, Any], latency: str):
    repo: Path = grad_context["repo"]
    wt = repo / ".worktrees" / "spike-0003"
    bench_txt = wt / "spikes" / "spike_0003" / "benchmark.txt"
    bench_txt.write_text(f"p95 latency is {latency}", encoding="utf-8")
    grad_context["benchmark_output"] = f"p95 latency is {latency}"


@then("an informational ADR or Architectural Finding is generated documenting why SQLite was rejected")
def verify_rejection_adr(grad_context: dict[str, Any]):
    repo: Path = grad_context["repo"]
    proposed_adrs = repo / "docs" / "project" / "adrs" / "proposed"
    found_adr = None
    for p in proposed_adrs.glob("*.md"):
        content = p.read_text(encoding="utf-8")
        if "reject" in content.lower() or "sqlite" in content.lower():
            found_adr = p
            break
    assert found_adr is not None, "Rejection ADR was not found in adrs/proposed/"
    content = found_adr.read_text(encoding="utf-8")
    assert "85ms" in content or "SQLite locking" in content


@then(parsers.parse('any proposed implementation tasks depending on {spike_id} are marked "{expected_status}"'))
def verify_dependent_task_blocked(grad_context: dict[str, Any], spike_id: str, expected_status: str):
    dep_file: Path = grad_context["dependent_task_file"]
    task = parse_task(dep_file)
    assert task.status == expected_status


@then('the backlog curator is prevented from promoting blocked tasks to "Refined".')
def verify_curator_skips_blocked_task(grad_context: dict[str, Any]):
    repo: Path = grad_context["repo"]
    config = load_config(root_dir=repo)
    curator = BacklogCurator(config)
    res = curator.curate()
    dep_file: Path = grad_context["dependent_task_file"]
    task = parse_task(dep_file)
    assert task.status != "Refined"
    assert task.canonical_id not in res.tasks_refined


# ============================================================================
# Scenario: Cleaning up disposable spike worktree upon graduation
# ============================================================================


@given(parsers.parse('"{spike_id}" has been successfully graduated into "{adr_id}"'))
def setup_graduated_spike_clean(grad_context: dict[str, Any], spike_id: str, adr_id: str):
    setup_completed_spike(grad_context, spike_id, "DuckDB outperforms SQLite for 1M graph node queries under 200ms")
    record_test_spike_output(grad_context, "spikes/spike_0002/test_spike.py", "p95 latency = 142ms")
    alex_runs_command(grad_context, f"spec-ops spike graduate {spike_id} --result proven --title 'Adopt DuckDB for Graph Query Acceleration'")


@when("graduation completes")
def graduation_completes(grad_context: dict[str, Any]):
    # Graduation was completed in given step
    pass


@then(parsers.parse('the ephemeral worktree "{wt_path}" is removed cleanly'))
def verify_worktree_removed(grad_context: dict[str, Any], wt_path: str):
    repo: Path = grad_context["repo"]
    wt = repo / wt_path
    assert not wt.exists(), f"Worktree {wt} was not removed"


@then(parsers.parse('the spike branch "{branch}" is tagged "{tag_name}" for audit history.'))
def verify_spike_branch_tagged(grad_context: dict[str, Any], branch: str, tag_name: str):
    repo: Path = grad_context["repo"]
    chk = subprocess.run(
        ["git", "tag", "--list", tag_name],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert tag_name in chk.stdout, f"Tag {tag_name} not found"


@then("spike pre-commit hooks and transient metadata are cleaned up")
def verify_hooks_and_metadata_cleaned(grad_context: dict[str, Any]):
    repo: Path = grad_context["repo"]
    chk = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert chk.returncode != 0 or chk.stdout.strip() != ".specops/hooks"
    assert not (repo / ".specops" / "hooks" / "pre-commit").exists()
    assert not (repo / ".specops" / "spike.json").exists()

