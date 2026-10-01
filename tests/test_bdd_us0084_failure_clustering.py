"""BDD step definitions for US-0084: Autonomous Failure Post-Mortem Clustering and Prompt Anti-Loop Synthesizer."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.core.parser import parse_task
from spec_ops.rescue.failure_clustering import (
    cluster_failure_entries,
    collect_backlog_failures,
)
from spec_ops.worker.claimer import hydrate_task_prompt

scenarios("features/us_0084_failure_clustering.feature")


@pytest.fixture
def repo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    backlog_dir = repo / "docs" / "project" / "backlog"
    for d in ["refined", "proposed", "complete"]:
        (backlog_dir / d).mkdir(parents=True, exist_ok=True)

    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    (repo / "specops.toml").write_text("[project]\nname = 'TestRepo'\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    monkeypatch.chdir(repo)
    cfg = load_config(repo)
    return {"repo": repo, "backlog_dir": backlog_dir, "config": cfg}


@given("multiple backlog tasks with recorded failure histories citing mock backdoors")
def setup_tasks_with_mock_failures(repo_env: dict[str, Any]):
    backlog_dir = repo_env["backlog_dir"]
    task1 = backlog_dir / "refined" / "0024-mock-task-one.md"
    task1.write_text(
        "---\n"
        "id: '0024'\n"
        "title: First Mock Task\n"
        "status: Refined\n"
        "governing_adrs:\n"
        "  - ADR-0003\n"
        "failure_history:\n"
        "  - attempt_date: '2026-09-29'\n"
        '    reason: "Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing"\n'
        "    failed_invariants:\n"
        "      - ADR-0003\n"
        "---\n\n"
        "# Task: TASK-0024\n"
        "Details...\n",
        encoding="utf-8",
    )

    task2 = backlog_dir / "refined" / "0025-mock-task-two.md"
    task2.write_text(
        "---\n"
        "id: '0025'\n"
        "title: Second Mock Task\n"
        "status: Refined\n"
        "governing_adrs:\n"
        "  - ADR-0003\n"
        "failure_history:\n"
        "  - attempt_date: '2026-09-30'\n"
        '    reason: "Used unittest.mock MagicMock backdoor violating ADR-0003"\n'
        "    failed_invariants:\n"
        "      - ADR-0003\n"
        "---\n\n"
        "# Task: TASK-0025\n"
        "Details...\n",
        encoding="utf-8",
    )

    repo_env["task1"] = task1
    repo_env["task2"] = task2


@when("the failure clustering engine analyzes the backlog")
def analyze_backlog_failures(repo_env: dict[str, Any]):
    backlog_dir = repo_env["backlog_dir"]
    repo = repo_env["repo"]
    entries = collect_backlog_failures(backlog_dir, repo_root=repo)
    clusters = cluster_failure_entries(entries, include_empty=False)
    repo_env["clusters"] = clusters
    repo_env["entries"] = entries


@then(parsers.parse('a common failure cluster for "{cluster_name}" is identified'))
def verify_failure_cluster_identified(repo_env: dict[str, Any], cluster_name: str):
    clusters = repo_env["clusters"]
    matching = [c for c in clusters if c.name.lower() == cluster_name.lower() or cluster_name.lower() in c.name.lower()]
    assert matching, f"Cluster '{cluster_name}' not found in {[c.name for c in clusters]}"
    cluster = matching[0]
    assert cluster.count >= 2, f"Expected cluster to aggregate recurrent failures (count >= 2), got {cluster.count}"
    repo_env["matched_cluster"] = cluster


@then(parsers.parse('associated with {invariant_id}'))
def verify_cluster_invariant(repo_env: dict[str, Any], invariant_id: str):
    cluster = repo_env["matched_cluster"]
    assert cluster.invariant_id == invariant_id, f"Expected invariant {invariant_id}, got {cluster.invariant_id}"


@given("an identified failure cluster for mock backdoors")
def ensure_cluster_for_mock_backdoors(repo_env: dict[str, Any]):
    setup_tasks_with_mock_failures(repo_env)
    analyze_backlog_failures(repo_env)
    verify_failure_cluster_identified(repo_env, "Mock Backdoor Tampering")


@when("a new worker claims a related task")
def worker_claims_related_task(repo_env: dict[str, Any]):
    backlog_dir = repo_env["backlog_dir"]
    repo = repo_env["repo"]
    cfg = repo_env["config"]

    related_task_file = backlog_dir / "refined" / "0042-new-related-task.md"
    related_task_file.write_text(
        "---\n"
        "id: '0042'\n"
        "title: New Related Task\n"
        "status: Refined\n"
        "governing_adrs:\n"
        "  - ADR-0003\n"
        "---\n\n"
        "# Task: TASK-0042\n"
        "This is a fresh task with no failure history of its own.\n",
        encoding="utf-8",
    )

    task = parse_task(related_task_file)
    prompt_str = hydrate_task_prompt(task, cfg)

    prompt_file = repo / ".task-prompt.md"
    prompt_file.write_text(prompt_str, encoding="utf-8")
    repo_env["generated_prompt"] = prompt_str
    repo_env["prompt_file"] = prompt_file


@then(parsers.parse('the generated ".task-prompt.md" includes explicit negative prompt instructions forbidding mocks'))
def verify_prompt_forbidding_mocks(repo_env: dict[str, Any]):
    prompt_str = repo_env["generated_prompt"]
    assert "## Prior Fleet Failures & Prohibitions" in prompt_str
    assert "Mock Backdoor Tampering" in prompt_str
    assert "ADR-0003" in prompt_str
    prompt_lower = prompt_str.lower()
    assert "forbidding mocks" in prompt_lower or "zero mock backdoors" in prompt_lower
