"""Executable BDD acceptance tests for US-0084 and US-0036."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.worker.commits import format_task_commit_message, parse_commit_trailers
from spec_ops.worker.integration import squash_merge_and_commit

scenarios("features/us_0084_conventional_commit_slice_trailers.feature")
scenarios("features/us_0036_context_enriched_pr_review_lineage.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="CommitReviewApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)

    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_dummy.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    config = load_config(root_dir=repo)
    return {
        "repo": repo,
        "config": config,
        "task": None,
        "cli_res": None,
        "branch": None,
        "commit_msg": None,
    }


# ==============================================================================
# Steps for US-0084
# ==============================================================================


@given(parsers.parse('a refined task "{task_id}" with slice type "{slice_type}" and title "{title}"'))
def setup_refined_task_slice(bdd_ctx: dict[str, Any], task_id: str, slice_type: str, title: str):
    repo: Path = bdd_ctx["repo"]
    clean_num = task_id.upper().replace("TASK-", "").replace("SPIKE-", "")
    task_file = repo / "docs" / "project" / "backlog" / "refined" / f"{clean_num}-test-task.md"
    task = Task(
        id=clean_num,
        title=title,
        status="Refined",
        slice_type=slice_type,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task"] = task


@given(parsers.parse('governing ADRs "{adrs}" and governing PRD "{prd}"'))
def setup_governing_adrs_and_prd(bdd_ctx: dict[str, Any], adrs: str, prd: str):
    task: Task = bdd_ctx["task"]
    task.governing_adrs = [a.strip() for a in adrs.split(",") if a.strip()]
    task.governing_prds = [p.strip() for p in prd.split(",") if p.strip()]
    write_task_file(task)


@when("the worker engine creates the final squash commit")
def worker_creates_squash_commit(bdd_ctx: dict[str, Any]):
    repo: Path = bdd_ctx["repo"]
    task: Task = bdd_ctx["task"]
    branch = f"task/{task.canonical_id}"
    bdd_ctx["branch"] = branch

    subprocess.run(["git", "checkout", "-b", branch], cwd=repo, check=True, capture_output=True)
    (repo / "solution.py").write_text("print('solution implemented')\n", encoding="utf-8")
    subprocess.run(["git", "add", "solution.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "wip: agent progress"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    commit_msg = format_task_commit_message(task)
    bdd_ctx["commit_msg"] = commit_msg

    queue = BacklogQueue(repo)
    ok, msg = squash_merge_and_commit(
        repo,
        branch,
        commit_msg,
        on_staged=lambda: queue.complete_task(task),
        main_branch="main",
    )
    assert ok, f"Squash merge failed: {msg}"


@then(parsers.parse('the commit subject line is formatted as "{expected_subject}"'))
def verify_commit_subject_line(bdd_ctx: dict[str, Any], expected_subject: str):
    repo: Path = bdd_ctx["repo"]
    res = subprocess.run(["git", "log", "-1", "--pretty=format:%s"], cwd=repo, check=True, capture_output=True, text=True)
    actual_subject = res.stdout.strip()
    assert actual_subject == expected_subject


@then("the commit body contains standard RFC-822 git trailers:")
def verify_commit_body_trailers(bdd_ctx: dict[str, Any], datatable: Any = None):
    repo: Path = bdd_ctx["repo"]
    res = subprocess.run(["git", "log", "-1", "--pretty=full"], cwd=repo, check=True, capture_output=True, text=True)
    full_log = res.stdout

    trailers = parse_commit_trailers(full_log)
    expected_rows = [
        ("SpecOps-Task", "TASK-0018"),
        ("SpecOps-Slice", "spike"),
        ("SpecOps-PRD", "PRD-0001"),
        ("SpecOps-ADR", "ADR-0007, ADR-0009"),
        ("Provenance", "spec-ops-worker (autonomous)"),
    ]
    for key, val in expected_rows:
        assert key in trailers, f"Trailer key '{key}' missing from commit:\n{full_log}"
        assert trailers[key] == val, f"Trailer '{key}' mismatch: expected '{val}', got '{trailers[key]}'"


@then(parsers.parse('"{cmd}" outputs the structured trailers cleanly.'))
def verify_git_log_pretty_full(bdd_ctx: dict[str, Any], cmd: str):
    repo: Path = bdd_ctx["repo"]
    args = cmd.split()
    res = subprocess.run(args, cwd=repo, check=True, capture_output=True, text=True)
    out = res.stdout
    assert "SpecOps-Task: TASK-0018" in out
    assert "SpecOps-Slice: spike" in out
    assert "SpecOps-PRD: PRD-0001" in out
    assert "SpecOps-ADR: ADR-0007, ADR-0009" in out
    assert "Provenance: spec-ops-worker (autonomous)" in out


@given(parsers.parse('a task "{task_id}" with slice type "{slice_type}" and title "{title}"'))
def setup_task_with_slice(bdd_ctx: dict[str, Any], task_id: str, slice_type: str, title: str):
    repo: Path = bdd_ctx["repo"]
    clean_num = task_id.upper().replace("TASK-", "").replace("SPIKE-", "")
    task_file = repo / "docs" / "project" / "backlog" / "refined" / f"{clean_num}-refactor.md"
    task = Task(
        id=clean_num,
        title=title,
        status="Refined",
        slice_type=slice_type,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task"] = task


@when("the worker finalizes and squash-merges the task")
def worker_finalizes_and_squash_merges(bdd_ctx: dict[str, Any]):
    repo: Path = bdd_ctx["repo"]
    task: Task = bdd_ctx["task"]
    branch = f"task/{task.canonical_id}"
    bdd_ctx["branch"] = branch

    subprocess.run(["git", "checkout", "-b", branch], cwd=repo, check=True, capture_output=True)
    (repo / "refactored.py").write_text("# modular\n", encoding="utf-8")
    subprocess.run(["git", "add", "refactored.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "refactor: modularize"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    commit_msg = format_task_commit_message(task)
    queue = BacklogQueue(repo)
    ok, msg = squash_merge_and_commit(
        repo,
        branch,
        commit_msg,
        on_staged=lambda: queue.complete_task(task),
        main_branch="main",
    )
    assert ok, f"Squash merge failed: {msg}"


@then(parsers.parse('the commit subject is formatted as "{expected_subject}"'))
def verify_commit_subject(bdd_ctx: dict[str, Any], expected_subject: str):
    repo: Path = bdd_ctx["repo"]
    res = subprocess.run(["git", "log", "-1", "--pretty=format:%s"], cwd=repo, check=True, capture_output=True, text=True)
    assert res.stdout.strip() == expected_subject


@then(parsers.parse('the trailers verify that "{expected_trailer}" is recorded.'))
def verify_trailers_recorded(bdd_ctx: dict[str, Any], expected_trailer: str):
    repo: Path = bdd_ctx["repo"]
    res = subprocess.run(["git", "log", "-1", "--pretty=full"], cwd=repo, check=True, capture_output=True, text=True)
    assert expected_trailer in res.stdout


# ==============================================================================
# Steps for US-0036
# ==============================================================================


@given(parsers.parse('a task branch "{branch_name}" created by an autonomous agent for "{task_id}"'))
def setup_task_branch_for_review(bdd_ctx: dict[str, Any], branch_name: str, task_id: str):
    repo: Path = bdd_ctx["repo"]
    clean_num = task_id.upper().replace("TASK-", "").lstrip("0")

    # 1. PRD-0001
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0001-autonomous-engine.md").write_text(
        "---\nid: '0001'\ntitle: SpecOps Autonomous Project Management Engine\nstatus: Accepted\ntarget_persona: Alex\n---\n# PRD-0001\n",
        encoding="utf-8",
    )

    # 2. ADR-0002 and ADR-0003
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "adr-0002-file-limit.md").write_text(
        "# ADR-0002: Modular Source File Length Limit (<500 Lines Anti-Rot Rule)\n## Status\nAccepted\n",
        encoding="utf-8",
    )
    (adrs_dir / "adr-0003-frontdoor-tdd.md").write_text(
        "# ADR-0003: Blackbox Frontdoor Verification and Zero Backdoor Testing\n## Status\nAccepted\n",
        encoding="utf-8",
    )

    # 3. User Story US-0015
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0015-review-brief.md").write_text(
        "---\nid: '0015'\ntitle: Review Brief\npersona: Alex (The Agentic Systems Architect)\ngoverning_prd: PRD-0001\n---\n"
        "# US-0015\n## Scenarios\n```gherkin\nScenario: Generating an architectural review brief for an agent PR\n  Given something\n```\n",
        encoding="utf-8",
    )

    # 4. Task in refined
    task_file = repo / "docs" / "project" / "backlog" / "refined" / f"{clean_num.zfill(4)}-review-brief.md"
    task = Task(
        id=clean_num,
        title="Review Brief Implementation",
        status="Refined",
        governing_prds=["PRD-0001"],
        governing_adrs=["ADR-0002", "ADR-0003"],
        governing_stories=["US-0015"],
        branch=branch_name,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task"] = task

    # Commit documentation on main
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: add specs for TASK-0015"], cwd=repo, check=True, capture_output=True)

    # Create task branch and commit changed source file
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo, check=True, capture_output=True)
    src_dir = repo / "src" / "sample"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "review_feature.py").write_text("\n".join(f"# Line {i}" for i in range(50)) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)

    agent_msg = format_task_commit_message(task, body="Implement review command", provenance="spec-ops-worker (autonomous)")
    subprocess.run(["git", "commit", "-m", agent_msg], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)


@when('the engineer executes "spec-ops review TASK-0015"')
def engineer_executes_review(bdd_ctx: dict[str, Any]):
    repo: Path = bdd_ctx["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "review", "TASK-0015"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_ctx["cli_res"] = res


@then("the CLI outputs a structured architectural review summary including:")
def verify_structured_review_summary(bdd_ctx: dict[str, Any], datatable: Any = None):
    res = bdd_ctx["cli_res"]
    assert res.returncode == 0, f"spec-ops review failed: {res.stderr}\n{res.stdout}"
    out = res.stdout

    assert "PRD-0001 (SpecOps Autonomous Project Management Engine)" in out
    assert "ADR-0002 (<500 lines limit)" in out
    assert "ADR-0003 (Frontdoor TDD)" in out
    assert "Scenario: Generating an architectural review brief for an agent PR" in out
    assert "Persona -> PRD -> User Story -> Task" in out


@then("all changed source files are summarized with line delta and file-limit headroom")
def verify_changed_source_files_headroom(bdd_ctx: dict[str, Any]):
    out = bdd_ctx["cli_res"].stdout
    assert "review_feature.py" in out
    assert "+50/-0" in out or "(+50/-0)" in out
    assert "headroom: 450 lines remaining until 500-line limit" in out


@then("zero private internal mocks are flagged in the verification report.")
def verify_zero_mocks_flagged(bdd_ctx: dict[str, Any]):
    out = bdd_ctx["cli_res"].stdout
    assert "0 private internal mocks flagged" in out


@given("a pull request branch containing both human and agent commits")
def setup_pr_branch_with_human_and_agent_commits(bdd_ctx: dict[str, Any]):
    if bdd_ctx.get("task") is None:
        setup_task_branch_for_review(bdd_ctx, "task/TASK-0015", "TASK-0015")
    repo: Path = bdd_ctx["repo"]
    branch = "task/TASK-0015"
    subprocess.run(["git", "checkout", branch], cwd=repo, check=True, capture_output=True)

    # Add a human commit missing SpecOps-Task trailer
    (repo / "human_change.py").write_text("# manual tweak\n", encoding="utf-8")
    subprocess.run(["git", "add", "human_change.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "refactor: manual cleanup by human"],
        cwd=repo,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "Riley Developer", "GIT_AUTHOR_EMAIL": "riley@example.com", "GIT_COMMITTER_NAME": "Riley Developer", "GIT_COMMITTER_EMAIL": "riley@example.com"},
    )
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)


@when('the engineer executes "spec-ops review TASK-0015 --provenance"')
def engineer_executes_review_provenance(bdd_ctx: dict[str, Any]):
    repo: Path = bdd_ctx["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "review", "TASK-0015", "--provenance"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_ctx["cli_res"] = res


@then("the review report identifies which commits were authored by autonomous workers versus human contributors")
def verify_author_distinction(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["cli_res"]
    assert res.returncode == 0, f"Command failed: {res.stderr}\n{res.stdout}"
    out = res.stdout
    assert "Autonomous Worker" in out
    assert "Human Contributor" in out


@then(parsers.parse('any commit missing the "{trailer}" git trailer is flagged with a warning.'))
def verify_missing_trailer_warning(bdd_ctx: dict[str, Any], trailer: str):
    out = bdd_ctx["cli_res"].stdout
    assert f'missing "{trailer}"' in out
