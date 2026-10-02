"""Unit tests for Definition of Ready (DoR) and Definition of Done (DoD) lifecycle gates (ADR-0003)."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.core.lifecycle_gates import (
    ALL_DOD_GATE_RULES,
    ALL_DOR_GATE_RULES,
    DoDGateResult,
    DoRGateResult,
    LifecycleGateOrchestrator,
)
from spec_ops.core.models import Task


def test_dor_gate_result_to_dict():
    res = DoRGateResult(
        task_id="TASK-0188",
        passed=True,
        rules={"Task Metadata Complete": True},
        violations=[],
        recommendations=["Keep it lean"],
    )
    d = res.to_dict()
    assert d["task_id"] == "TASK-0188"
    assert d["passed"] is True
    assert d["rules"]["Task Metadata Complete"] is True
    assert d["recommendations"] == ["Keep it lean"]


def test_dod_gate_result_to_dict():
    res = DoDGateResult(
        task_id="TASK-0188",
        passed=False,
        rules={"Blackbox Frontdoor Verification": False},
        violations=["100% test pass required"],
        recommendations=[],
    )
    d = res.to_dict()
    assert d["task_id"] == "TASK-0188"
    assert d["passed"] is False
    assert len(d["violations"]) == 1


def test_dor_evaluation_empty_task():
    task = Task(id="", title="")
    res = LifecycleGateOrchestrator.evaluate_dor(task)
    assert res.passed is False
    assert any("Missing required frontmatter metadata" in v for v in res.violations)
    assert any("Task must cite governing PRDs" in v for v in res.violations)


def test_dor_evaluation_missing_bdd_and_mutation(tmp_path: Path):
    task_file = tmp_path / "0188-task.md"
    task_file.write_text(
        "---\nid: '0188'\ntitle: Gate Task\nstatus: Refined\ntarget_bc: core\n"
        "governing_prds:\n- PRD-0006\ngoverning_stories:\n- US-0117\ngoverning_adrs:\n- ADR-0001\n---\n"
        "Just a description without scenarios.\n",
        encoding="utf-8",
    )
    task = Task(
        id="0188",
        title="Gate Task",
        status="Refined",
        target_bc="core",
        governing_prds=["PRD-0006"],
        governing_stories=["US-0117"],
        governing_adrs=["ADR-0001"],
        file_path=task_file,
    )
    res = LifecycleGateOrchestrator.evaluate_dor(task)
    assert res.passed is False
    assert any("Gherkin scenarios" in v for v in res.violations)
    assert any("generative property invariants" in v for v in res.violations)
    assert any("Mutmut" in v for v in res.violations)


def test_dod_evaluation_full_pass():
    task = Task(id="0188", title="Gate Task", target_bc="core")
    data = {
        "frontdoors_passed": True,
        "bdd_passed": True,
        "hypothesis_passed": True,
        "mutation_score": 85.5,
        "health_passed": True,
        "lockfile_intact": True,
        "docs_synced": True,
        "backlog_progressed": True,
        "commit_trailers_valid": True,
        "dual_custody_signed": True,
    }
    res = LifecycleGateOrchestrator.evaluate_dod(task, verification_data=data)
    assert res.passed is True
    assert len(res.violations) == 0
    for r in ALL_DOD_GATE_RULES:
        assert res.rules[r] is True

    summary = LifecycleGateOrchestrator.format_gate_report(res)
    assert "Definition of Done (DoD) Gate Audit: TASK-0188" in summary
    assert "✅ PASSED" in summary


def test_dod_evaluation_all_fail():
    task = Task(id="0188", title="Gate Task", target_bc="core")
    res = LifecycleGateOrchestrator.evaluate_dod(task, verification_data={})
    assert res.passed is False
    assert len(res.violations) >= 9
    summary = LifecycleGateOrchestrator.format_gate_report(res)
    assert "❌ FAILED" in summary
