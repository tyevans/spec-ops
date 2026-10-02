"""BDD tests for US-0117 / TASK-0171: Autonomous Failure Memory Strategy Indexer and Healing Playbook Generator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.rescue.strategy_indexer import StrategyIndexer
from spec_ops.scaffold.init import init_project

scenarios("features/us_0117_strategy_indexer.feature")


@pytest.fixture
def bdd_rescue_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "rescue_app"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="RescueApp", target_dir=repo)

    # Set up .specops/failures/ with sample post-mortems
    failures_dir = repo / ".specops" / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    (failures_dir / "failure-001.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "TASK-0012",
                    "reason": "ADR-0002 file length limit exceeded (>500 lines) in monolith.py",
                    "failed_invariants": ["ADR-0002"],
                },
                {
                    "task_id": "TASK-0015",
                    "reason": "ADR-0003 prohibited mock backdoor detected in test suite",
                    "failed_invariants": ["ADR-0003"],
                },
            ]
        ),
        encoding="utf-8",
    )

    return {
        "repo": repo,
        "playbook": None,
        "exit_code": None,
        "stdout": "",
        "query_results": None,
    }


@given("a history of resolved worktree failures and post-mortem logs")
def given_history_of_failures(bdd_rescue_ctx: dict[str, Any]) -> None:
    # Failures are in .specops/failures/ in fixture
    pass


@given("an indexed strategy database containing file limit remediation advice")
def given_indexed_strategy_database(bdd_rescue_ctx: dict[str, Any]) -> None:
    repo = bdd_rescue_ctx["repo"]
    indexer = StrategyIndexer(repo)
    playbook = indexer.compile_playbook()
    bdd_rescue_ctx["playbook"] = playbook


@when("the strategy indexer compiles the healing playbook")
def when_compile_playbook(bdd_rescue_ctx: dict[str, Any]) -> None:
    repo = bdd_rescue_ctx["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "rescue", "playbooks"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_rescue_ctx["exit_code"] = res.returncode
    bdd_rescue_ctx["stdout"] = res.stdout


@when('a worker queries the playbook for "ADR-0002" failure signatures')
def when_query_playbook(bdd_rescue_ctx: dict[str, Any]) -> None:
    repo = bdd_rescue_ctx["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "rescue", "playbooks", "--query", "ADR-0002", "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_rescue_ctx["exit_code"] = res.returncode
    bdd_rescue_ctx["stdout"] = res.stdout
    bdd_rescue_ctx["query_results"] = json.loads(res.stdout)


@then("categorized failure strategies are produced with actionable remedies")
def then_categorized_strategies(bdd_rescue_ctx: dict[str, Any]) -> None:
    repo = bdd_rescue_ctx["repo"]
    indexer = StrategyIndexer(repo)
    pb = indexer.compile_playbook()
    assert pb.total_strategies >= 2
    assert any(s.category == "file_length" for s in pb.strategies)
    assert any(s.category == "mock_backdoor" for s in pb.strategies)
    assert "ADR-0002" in bdd_rescue_ctx["stdout"]
    assert "Remedy:" in bdd_rescue_ctx["stdout"]


@then("the matching decomposition strategy is returned with guidance")
def then_matching_strategy(bdd_rescue_ctx: dict[str, Any]) -> None:
    res = bdd_rescue_ctx["query_results"]
    assert res["total_matched"] >= 1
    strat = res["strategies"][0]
    assert "strat-adr0002" in strat["strategy_id"]
    assert "Decompose" in strat["summary"] or "decompose" in strat["actionable_remedy"]


@then("the command terminates with exit code 0")
def then_exit_zero(bdd_rescue_ctx: dict[str, Any]) -> None:
    assert bdd_rescue_ctx["exit_code"] == 0
