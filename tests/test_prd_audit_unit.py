"""Unit tests for DeepPRDAuditor and PersonaTraceabilityEngine."""

from __future__ import annotations

from pathlib import Path
import pytest

from spec_ops.core.models import CommitInfo, Persona, ProjectData, Task, UserStory, PRD
from spec_ops.prd.audit import (
    DeepPRDAuditor,
    OrphanedOutcome,
    OutcomeAuditResult,
    UnanchoredTask,
    calculate_outcome_coverage,
    run_deep_audit,
    _clean_prd_id,
    _clean_story_id,
    _clean_task_id,
)
from spec_ops.prd.traceability import (
    PersonaCoverageReport,
    PersonaLineageRecord,
    PersonaTraceabilityEngine,
    _clean_prd_id as t_clean_prd_id,
    _clean_story_id as t_clean_story_id,
    _clean_task_id as t_clean_task_id,
)


def test_calculate_outcome_coverage_branches():
    assert calculate_outcome_coverage(0, 0) == 100.0
    assert calculate_outcome_coverage(-5, 2) == 100.0
    assert calculate_outcome_coverage(10, 0) == 0.0
    assert calculate_outcome_coverage(10, -2) == 0.0
    assert calculate_outcome_coverage(5, 5) == 100.0
    assert calculate_outcome_coverage(5, 6) == 100.0
    assert calculate_outcome_coverage(10, 5) == 50.0
    assert calculate_outcome_coverage(3, 1) == 33.3


def test_clean_id_helpers():
    assert _clean_prd_id("prd-0002") == "PRD-0002"
    assert _clean_prd_id("1") == "PRD-0001"
    assert _clean_story_id("us-0004") == "US-0004"
    assert _clean_story_id("4") == "US-0004"
    assert _clean_task_id("task-0007") == "TASK-0007"
    assert _clean_task_id("7") == "TASK-0007"

    assert t_clean_prd_id("prd-0002") == "PRD-0002"
    assert t_clean_story_id("us-0004") == "US-0004"
    assert t_clean_task_id("task-0007") == "TASK-0007"


def test_auditor_requires_config_or_project_data():
    auditor = DeepPRDAuditor()
    with pytest.raises(ValueError, match="DeepPRDAuditor requires either SpecOpsConfig or ProjectData"):
        auditor.audit_all_accepted()


def test_deep_audit_clean_scenario():
    prd = PRD(
        id="PRD-0001",
        title="Verification PRD",
        status="Accepted",
        raw_markdown="---\nid: '0001'\ntitle: Verification PRD\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Output matches schema\n",
    )
    story = UserStory(
        id="US-0001",
        title="Output matches schema",
        status="Accepted",
        governing_prd="PRD-0001",
        raw_markdown="---\nid: '0001'\ntitle: Output matches schema\ngoverning_prd: PRD-0001\noutcome_id: 1\n---\n",
    )
    task = Task(
        id="TASK-0001",
        title="Implement output matches schema",
        status="Complete",
        governing_prds=["PRD-0001"],
        governing_stories=["US-0001"],
        raw_markdown="---\nid: '0001'\ntitle: Implement schema\ngoverning_prds:\n  - PRD-0001\ngoverning_stories:\n  - US-0001\noutcome_id: 1\n---\n",
    )
    data = ProjectData(prds=[prd], stories=[story], tasks=[task])
    auditor = DeepPRDAuditor(project_data=data)
    res = auditor.audit_all_accepted()

    assert res.is_clean
    assert res.drift_count == 0
    assert res.coverage_pct == 100.0
    assert res.covered_outcomes == 1
    assert res.total_outcomes == 1
    assert res.buffer_status == "OPTIMAL"

    rep = auditor.format_report(res)
    assert "Outcome Coverage: 100% (1/1 outcomes covered)" in rep
    assert "Specification Drift: 0 issues detected" in rep


def test_deep_audit_orphans_and_unanchored():
    prd = PRD(
        id="PRD-0004",
        title="Isolation PRD",
        status="Accepted",
        raw_markdown="---\nid: '0004'\ntitle: Isolation PRD\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Multi-tenant workspace isolation\n",
    )
    # Rogue task claiming PRD-0001 which is not even in target_prds
    rogue_task = Task(
        id="TASK-0105",
        title="Rogue Task",
        status="Proposed",
        governing_prds=["PRD-0001"],
    )
    data = ProjectData(prds=[prd], stories=[], tasks=[rogue_task])
    auditor = DeepPRDAuditor(project_data=data)
    res = auditor.audit_all_accepted()

    assert not res.is_clean
    assert res.drift_count == 2
    assert len(res.orphaned_outcomes) == 1
    assert len(res.unanchored_tasks) == 1
    assert res.buffer_status == "INCOMPLETE_COVERAGE"

    orphan = res.orphaned_outcomes[0]
    assert orphan.prd_id == "PRD-0004"
    assert "Multi-tenant workspace isolation" in orphan.diagnostic
    assert "Run 'spec-ops prd decompose PRD-0004 --by-outcomes'" in orphan.suggestion

    unanchored = res.unanchored_tasks[0]
    assert unanchored.task_id == "TASK-0105"
    assert unanchored.prd_id == "PRD-0001"
    assert "Unanchored Task: TASK-0105 references PRD-0001" in unanchored.diagnostic

    rep = auditor.format_report(res)
    assert "⚠️ Orphaned Outcomes:" in rep
    assert "⚠️ Unanchored Tasks:" in rep
    assert "Buffer Health: INCOMPLETE_COVERAGE" in rep


def test_deep_audit_filter_by_prd_id():
    prd1 = PRD(
        id="PRD-0001",
        title="PRD 1",
        status="Accepted",
        raw_markdown="---\nid: '0001'\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Outcome 1\n",
    )
    prd2 = PRD(
        id="PRD-0002",
        title="PRD 2",
        status="Accepted",
        raw_markdown="---\nid: '0002'\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Outcome 2\n",
    )
    data = ProjectData(prds=[prd1, prd2], stories=[], tasks=[])
    auditor = DeepPRDAuditor(project_data=data)
    res = auditor.audit_all_accepted(prd_id="PRD-0002")

    assert res.total_outcomes == 1
    assert res.orphaned_outcomes[0].prd_id == "PRD-0002"


def test_traceability_engine_requires_config_or_data():
    engine = PersonaTraceabilityEngine()
    with pytest.raises(ValueError, match="PersonaTraceabilityEngine requires either SpecOpsConfig or ProjectData"):
        engine.build_lineage()


def test_traceability_engine_lineage_and_audit():
    p = Persona(id="taylor", name="Taylor", role="Product Manager")
    s = UserStory(
        id="US-0006",
        title="Living Graph",
        status="Accepted",
        persona="Taylor",
        feature="FEAT-VIS-01",
        governing_prd="PRD-0001",
    )
    t = Task(
        id="TASK-0008",
        title="Graph Canvas",
        status="Complete",
        governing_prds=["PRD-0001"],
        governing_stories=["US-0006"],
        commits=[CommitInfo(hash="abc12345678", author="Ty", date="2026-09-29", subject="canvas")],
    )
    orphan_task = Task(
        id="TASK-0099",
        title="No Story Task",
        status="Proposed",
    )
    data = ProjectData(personas=[p], stories=[s], tasks=[t, orphan_task])
    engine = PersonaTraceabilityEngine(project_data=data)

    lineage = engine.build_lineage()
    assert len(lineage) == 1
    rec = lineage[0]
    assert rec.persona == "Taylor"
    assert rec.prd == "PRD-0001"
    assert rec.story == "US-0006"
    assert rec.task == "TASK-0008"
    assert rec.commit == "abc1234"
    assert rec.status == "Complete"
    assert rec.permalink == "#tab=prds&entity=PRD-0001&filter=FEAT-VIS-01"
    assert rec.to_row() == ["Taylor", "PRD-0001", "US-0006", "TASK-0008", "abc1234", "Complete"]

    tbl = engine.format_lineage_table(lineage)
    assert "| Taylor | PRD-0001 | US-0006 | TASK-0008 | abc1234 | Complete |" in tbl

    report = engine.audit_persona_coverage()
    assert "Taylor" in report.distribution
    assert len(report.orphan_tasks) == 1
    assert "TASK-0099" in report.orphan_tasks[0]
    assert report.has_warnings

    formatted = engine.format_persona_coverage(report)
    assert "=== Persona Coverage & Workload Distribution Matrix ===" in formatted
    assert "Taylor" in formatted
    assert "Orphan Task: TASK-0099" in formatted
