"""Executable BDD acceptance tests for US-0019: Bidirectional End-to-End Traceability and Contributor Provenance Audit.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009.
Blackbox frontdoor verification via CLI with zero private mock backdoors.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.visualizer.generator import generate_standalone_html

scenarios("features/us_0019_traceability.feature")

CLI_ENV = {**os.environ, "PYTHONPATH": "src"}


@pytest.fixture
def bdd_trace_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan Lead"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "jordan@specops.dev"], cwd=str(repo), check=True)

    # Create directory tree
    (repo / "docs" / "project" / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "project" / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "project" / "backlog" / "complete").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "project" / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)

    (repo / "specops.toml").write_text('[project]\nname = "TraceabilityApp"\n', encoding="utf-8")

    return {
        "repo": repo,
        "cli_res": None,
        "unanchored_hash": None,
        "unanchored_author": None,
        "orphaned_task_id": None,
    }


def _run_cli(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


# ==============================================================================
# Scenario 1 Steps
# ==============================================================================


@given("a project repository with accepted Personas, PRDs, User Stories, and Backlog Tasks")
def project_with_accepted_entities(bdd_trace_context: dict[str, Any]):
    repo = bdd_trace_context["repo"]

    # PERSONAS.md
    personas_file = repo / "docs" / "project" / "user_stories" / "PERSONAS.md"
    personas_file.write_text(
        "# Customer Personas\n\n## 1. Jordan — The AI-Native Engineering Lead\n- **Role**: Engineering lead.\n",
        encoding="utf-8",
    )

    # PRD-0005
    (repo / "docs" / "project" / "product" / "accepted" / "prd-0005-relational-graph.md").write_text(
        """---
id: '0005'
title: Relational Knowledge Graph
status: Accepted
target_persona: Jordan (The AI-Native Engineering Lead)
---
# PRD-0005: Relational Knowledge Graph
""",
        encoding="utf-8",
    )

    # US-0019
    (repo / "docs" / "project" / "user_stories" / "accepted" / "us-0019-traceability.md").write_text(
        """---
id: '0019'
title: Bidirectional Traceability
status: Accepted
persona: Jordan (The AI-Native Engineering Lead)
governing_prd: PRD-0005
---
# US-0019: Bidirectional Traceability
""",
        encoding="utf-8",
    )

    # TASK-0075
    (repo / "docs" / "project" / "backlog" / "complete" / "0075-provenance-engine.md").write_text(
        """---
id: '0075'
title: Provenance Engine
status: Complete
governing_prds:
  - PRD-0005
governing_stories:
  - US-0019
---
# TASK-0075
""",
        encoding="utf-8",
    )


@given("git history containing merged commits with structured trailers referencing task IDs")
def git_history_with_structured_trailers(bdd_trace_context: dict[str, Any]):
    repo = bdd_trace_context["repo"]
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    msg = "feat(task-0075): implement provenance engine\n\nSpecOps-Task: TASK-0075\nProvenance: spec-ops-worker\n"
    subprocess.run(["git", "commit", "-m", msg], cwd=str(repo), check=True)


@when(parsers.parse('the lead runs "{cmd}"'))
def lead_runs_command(bdd_trace_context: dict[str, Any], cmd: str):
    repo = bdd_trace_context["repo"]
    parts = cmd.split()
    assert parts[0] == "spec-ops"
    res = _run_cli(repo, parts[1:])
    bdd_trace_context["cli_res"] = res


@then("the command exits with code 0")
def command_exits_zero(bdd_trace_context: dict[str, Any]):
    res = bdd_trace_context["cli_res"]
    assert res.returncode == 0, f"Command failed with code {res.returncode}. Stderr: {res.stderr}\nStdout: {res.stdout}"


@then("outputs a verified traceability matrix linking each Persona to its PRDs, Stories, Tasks, and Git Commits")
def outputs_verified_traceability_matrix(bdd_trace_context: dict[str, Any]):
    res = bdd_trace_context["cli_res"]
    stdout = res.stdout
    assert "Verified Traceability Matrix" in stdout or "Traceability" in stdout
    assert "Jordan" in stdout
    assert "PRD-0005" in stdout
    assert "US-0019" in stdout
    assert "TASK-0075" in stdout


@then(parsers.parse('reports "{expected_report}".'))
def reports_traceability_integrity(bdd_trace_context: dict[str, Any], expected_report: str):
    res = bdd_trace_context["cli_res"]
    assert expected_report in res.stdout, f"Expected '{expected_report}' in output:\n{res.stdout}"


# ==============================================================================
# Scenario 2 Steps
# ==============================================================================


@given(parsers.parse('a git commit merged to "{branch}" without a "{trailer1}" or "{trailer2}" trailer'))
def git_commit_without_trailer(bdd_trace_context: dict[str, Any], branch: str, trailer1: str, trailer2: str):
    repo = bdd_trace_context["repo"]

    # Initial file
    dummy_file = repo / "rogue_change.txt"
    dummy_file.write_text("unanchored changes\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    author_name = "Rogue Developer"
    author_email = "rogue@dev.null"
    subprocess.run(
        ["git", "commit", "-m", "rogue commit without task trailers", f"--author={author_name} <{author_email}>"],
        cwd=str(repo),
        check=True,
    )

    # Get the unanchored commit hash
    log_res = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    )
    unanchored_hash = log_res.stdout.strip()
    bdd_trace_context["unanchored_hash"] = unanchored_hash
    bdd_trace_context["unanchored_author"] = author_name


@given(parsers.parse('a completed task in "{folder}" with no linked git commits'))
def completed_task_with_no_commits(bdd_trace_context: dict[str, Any], folder: str):
    repo = bdd_trace_context["repo"]
    target_dir = repo / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    task_file = target_dir / "0099-orphaned-deliverable.md"
    task_file.write_text(
        """---
id: '0099'
title: Orphaned Task Without Commits
status: Complete
---
# TASK-0099
""",
        encoding="utf-8",
    )
    bdd_trace_context["orphaned_task_id"] = "TASK-0099"


@then("the command exits with code 1")
def command_exits_one(bdd_trace_context: dict[str, Any]):
    res = bdd_trace_context["cli_res"]
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then("reports a warning identifying the unanchored commit hash and author")
def reports_warning_identifying_unanchored_commit(bdd_trace_context: dict[str, Any]):
    res = bdd_trace_context["cli_res"]
    chash = bdd_trace_context["unanchored_hash"]
    author = bdd_trace_context["unanchored_author"]
    stdout = res.stdout + res.stderr
    assert "Unanchored commit" in stdout or "unanchored" in stdout.lower()
    assert chash in stdout, f"Commit hash {chash} not in output:\n{stdout}"
    assert author in stdout, f"Author {author} not in output:\n{stdout}"


@then("highlights the orphaned task as missing delivery provenance.")
def highlights_orphaned_task_missing_provenance(bdd_trace_context: dict[str, Any]):
    res = bdd_trace_context["cli_res"]
    task_id = bdd_trace_context["orphaned_task_id"]
    stdout = res.stdout + res.stderr
    assert task_id in stdout
    assert "missing delivery provenance" in stdout.lower() or "orphaned" in stdout.lower()


# ==============================================================================
# Scenario 3 Steps
# ==============================================================================


@given(parsers.parse('a repository with commits authored by autonomous workers containing "{provenance_trailer}"'))
def repository_with_autonomous_commits(bdd_trace_context: dict[str, Any], provenance_trailer: str):
    repo = bdd_trace_context["repo"]
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)

    # Create 14 completed tasks delivered by autonomous agents
    for i in range(1, 15):
        tid = f"TASK-{i:04d}"
        (complete_dir / f"{i:04d}-auto-task.md").write_text(
            f"---\nid: '{i:04d}'\ntitle: Auto Task {i}\nstatus: Complete\n---\n# {tid}\n",
            encoding="utf-8",
        )

    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)

    # Create 28 commits authored by autonomous workers
    for c_idx in range(1, 29):
        # Associate with tasks 1..14 (2 commits per task)
        task_num = ((c_idx - 1) % 14) + 1
        tid = f"TASK-{task_num:04d}"
        msg = (
            f"feat({tid.lower()}): autonomous commit {c_idx}\n\n"
            f"SpecOps-Task: {tid}\n"
            f"{provenance_trailer}\n"
            f"Pass-Rate: 93.3%\n"
        )
        (repo / f"auto_file_{c_idx}.txt").write_text(f"content {c_idx}\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
        subprocess.run(
            ["git", "commit", "-m", msg, "--author=Autonomous Agent <agent@specops.dev>"],
            cwd=str(repo),
            check=True,
        )


@given("commits authored by human developers")
def commits_authored_by_human_developers(bdd_trace_context: dict[str, Any]):
    repo = bdd_trace_context["repo"]
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"

    # Create 9 completed tasks delivered by human developers
    for i in range(15, 24):
        tid = f"TASK-{i:04d}"
        (complete_dir / f"{i:04d}-human-task.md").write_text(
            f"---\nid: '{i:04d}'\ntitle: Human Task {i}\nstatus: Complete\n---\n# {tid}\n",
            encoding="utf-8",
        )

    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)

    # Create 15 commits authored by human developers
    for c_idx in range(1, 16):
        task_num = 15 + ((c_idx - 1) % 9)
        tid = f"TASK-{task_num:04d}"
        msg = f"feat({tid.lower()}): human commit {c_idx}\n\nSpecOps-Task: {tid}\n"
        (repo / f"human_file_{c_idx}.txt").write_text(f"content {c_idx}\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
        subprocess.run(
            ["git", "commit", "-m", msg, "--author=Human Developer <human@specops.dev>"],
            cwd=str(repo),
            check=True,
        )


@then("the output breaks down delivered tasks by contributor type:")
def output_breaks_down_by_contributor_type(bdd_trace_context: dict[str, Any]):
    res = bdd_trace_context["cli_res"]
    stdout = res.stdout
    assert "Contributor Class" in stdout
    assert "Tasks Delivered" in stdout
    assert "Merged Commits" in stdout
    assert "Verification Pass Rate" in stdout

    # Autonomous Agents: 14 delivered, 28 merged, 93.3%
    assert "Autonomous Agents" in stdout
    assert "14" in stdout
    assert "28" in stdout
    assert "93.3%" in stdout

    # Human Developers: 9 delivered, 15 merged, 100.0%
    assert "Human Developers" in stdout
    assert "9" in stdout
    assert "15" in stdout
    assert "100.0%" in stdout


@then("updates the visualizer Traceability view with contributor filter chips.")
def updates_visualizer_contributor_filter_chips(bdd_trace_context: dict[str, Any]):
    repo = bdd_trace_context["repo"]
    res = bdd_trace_context["cli_res"]
    assert "Updated visualizer Traceability view with contributor filter chips." in res.stdout

    # Verify visualizer standalone bundle includes contributor filter chips
    config = load_config(root_dir=repo)
    html = generate_standalone_html(config)
    assert "contributor-filter-chips" in html or "Autonomous Agents" in html
