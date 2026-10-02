"""BDD step definitions for US-0117: Embedded Definition of Ready (DoR) and Definition of Done (DoD) Lifecycle Gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.lifecycle_gates import (
    ALL_DOD_GATE_RULES,
    ALL_DOR_GATE_RULES,
    DoDGateResult,
    DoRGateResult,
    LifecycleGateOrchestrator,
)
from spec_ops.core.models import Task

scenarios("features/us_0117_lifecycle_gates.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parent.parent
    return {"repo_root": repo_root}


@given("a backlog task missing required governing artifacts and BDD specifications")
def task_missing_artifacts(bdd_ctx: dict[str, Any], tmp_path: Path):
    task_file = tmp_path / "0999-unrefined.md"
    task_file.write_text("# Bare Task\nNo frontmatter or scenarios.\n", encoding="utf-8")
    task = Task(
        id="0999",
        title="Unrefined Task",
        file_path=task_file,
    )
    bdd_ctx["dor_task"] = task


@when("the lifecycle orchestrator evaluates the Definition of Ready gate")
def evaluate_dor_gate(bdd_ctx: dict[str, Any]):
    task: Task = bdd_ctx["dor_task"]
    bdd_ctx["dor_result"] = LifecycleGateOrchestrator.evaluate_dor(task)


@then("the task fails the DoR gate check")
def verify_dor_failed(bdd_ctx: dict[str, Any]):
    res: DoRGateResult = bdd_ctx["dor_result"]
    assert res.passed is False
    assert len(res.violations) > 0


@then("actionable violations and recommendations are reported for remediation.")
def verify_dor_violations(bdd_ctx: dict[str, Any]):
    res: DoRGateResult = bdd_ctx["dor_result"]
    assert any("governing PRDs" in v for v in res.violations)
    report_text = LifecycleGateOrchestrator.format_gate_report(res)
    assert "FAILED" in report_text
    assert "Rule Check" in report_text


@given("a fully refined backlog task satisfying all 7 DoR rules")
def task_fully_refined(bdd_ctx: dict[str, Any], tmp_path: Path):
    task_file = tmp_path / "0188-refined.md"
    task_file.write_text(
        "---\n"
        "id: '0188'\n"
        "title: Embedded Lifecycle Gates\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_prds:\n- PRD-0006\n"
        "governing_stories:\n- US-0117\n"
        "governing_adrs:\n- ADR-0001\n"
        "---\n\n"
        "## Acceptance Criteria\n"
        "```gherkin\nScenario: Pass Gate\n  Given ok\n  When run\n  Then ok\n```\n\n"
        "## Hypothesis Invariant Properties\n- @given(...) properties\n\n"
        "## Mutation Testing Scope\n- Minimum 80% kill score under mutmut.\n\n"
        "INVEST criteria satisfied with files <500 lines.\n"
        "Docs reviewed.\n",
        encoding="utf-8",
    )
    task = Task(
        id="0188",
        title="Embedded Lifecycle Gates",
        status="Refined",
        target_bc="core",
        governing_prds=["PRD-0006"],
        governing_stories=["US-0117"],
        governing_adrs=["ADR-0001"],
        file_path=task_file,
    )
    bdd_ctx["dor_task"] = task


@then("the task passes the DoR gate check")
def verify_dor_passed(bdd_ctx: dict[str, Any]):
    res: DoRGateResult = bdd_ctx["dor_result"]
    assert res.passed is True
    assert len(res.violations) == 0


@then("is approved for in-worktree active implementation.")
def verify_dor_approved(bdd_ctx: dict[str, Any]):
    res: DoRGateResult = bdd_ctx["dor_result"]
    for rule in ALL_DOR_GATE_RULES:
        assert res.rules[rule] is True


@given("an implementation diff missing blackbox frontdoor tests or mutation kill thresholds")
def implementation_failing(bdd_ctx: dict[str, Any]):
    bdd_ctx["dod_task"] = Task(id="0188", title="Task 0188", target_bc="core")
    bdd_ctx["dod_data"] = {
        "frontdoors_passed": False,
        "bdd_passed": True,
        "hypothesis_passed": True,
        "mutation_score": 65.0,  # Below 80% threshold
        "health_passed": True,
        "lockfile_intact": True,
        "docs_synced": True,
        "backlog_progressed": True,
        "commit_trailers_valid": True,
        "dual_custody_signed": True,
    }


@when("the lifecycle orchestrator evaluates the Definition of Done gate")
def evaluate_dod_gate(bdd_ctx: dict[str, Any]):
    task: Task = bdd_ctx["dod_task"]
    data: dict[str, Any] = bdd_ctx["dod_data"]
    bdd_ctx["dod_result"] = LifecycleGateOrchestrator.evaluate_dod(task, verification_data=data)


@then("the task fails the DoD gate check")
def verify_dod_failed(bdd_ctx: dict[str, Any]):
    res: DoDGateResult = bdd_ctx["dod_result"]
    assert res.passed is False
    assert len(res.violations) >= 2


@then("integration is blocked until all 10 DoD rules pass.")
def verify_dod_blocked(bdd_ctx: dict[str, Any]):
    res: DoDGateResult = bdd_ctx["dod_result"]
    assert any("Frontdoor" in v or "test pass rate" in v for v in res.violations)
    assert any("Mutant kill score" in v for v in res.violations)
    report_text = LifecycleGateOrchestrator.format_gate_report(res)
    assert "FAILED" in report_text


@given("an implementation that satisfies 100% frontdoor tests, health, lockfile, and human sign-off")
def implementation_passing(bdd_ctx: dict[str, Any]):
    bdd_ctx["dod_task"] = Task(id="0188", title="Task 0188", target_bc="core")
    bdd_ctx["dod_data"] = {
        "frontdoors_passed": True,
        "bdd_passed": True,
        "hypothesis_passed": True,
        "mutation_score": 100.0,
        "health_passed": True,
        "lockfile_intact": True,
        "docs_synced": True,
        "backlog_progressed": True,
        "commit_trailers_valid": True,
        "dual_custody_signed": True,
    }


@then("the task passes the DoD gate check")
def verify_dod_passed(bdd_ctx: dict[str, Any]):
    res: DoDGateResult = bdd_ctx["dod_result"]
    assert res.passed is True
    assert len(res.violations) == 0


@then("is approved for integration into main.")
def verify_dod_approved(bdd_ctx: dict[str, Any]):
    res: DoDGateResult = bdd_ctx["dod_result"]
    for rule in ALL_DOD_GATE_RULES:
        assert res.rules[rule] is True
    report_text = LifecycleGateOrchestrator.format_gate_report(res)
    assert "PASSED" in report_text
