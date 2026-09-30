"""Generative property-based tests for PRD outcome audit and traceability invariants (ADR-0009)."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.core.models import ADR, PRD, CommitInfo, Persona, ProjectData, Task, UserStory
from spec_ops.prd.audit import (
    DeepPRDAuditor,
    OrphanedOutcome,
    OutcomeAuditResult,
    UnanchoredTask,
    calculate_outcome_coverage,
)
from spec_ops.prd.traceability import PersonaTraceabilityEngine


@st.composite
def random_project_data(draw) -> ProjectData:
    num_prds = draw(st.integers(min_value=0, max_value=4))
    prds: list[PRD] = []
    all_outcome_texts: list[str] = []

    for i in range(1, num_prds + 1):
        pid = f"PRD-{i:04d}"
        num_outcomes = draw(st.integers(min_value=0, max_value=4))
        outcomes = [f"Checkable behavioral requirement {pid}-{j}" for j in range(1, num_outcomes + 1)]
        all_outcome_texts.extend(outcomes)
        outcomes_block = "\n".join(f"{j}. {ot}" for j, ot in enumerate(outcomes, start=1))
        raw_md = f"---\nid: '{i:04d}'\ntitle: PRD {i}\nstatus: Accepted\n---\n\n## Checkable Outcomes\n\n{outcomes_block}\n"
        prds.append(
            PRD(
                id=pid,
                title=f"PRD {i}",
                status="Accepted",
                outcomes=outcomes,
                raw_markdown=raw_md,
            )
        )

    num_stories = draw(st.integers(min_value=0, max_value=6))
    stories: list[UserStory] = []
    for s_idx in range(1, num_stories + 1):
        sid = f"US-{s_idx:04d}"
        linked_prd = draw(st.sampled_from([p.id for p in prds])) if prds else ""
        outcome_id = draw(st.integers(min_value=1, max_value=5))
        persona_name = draw(st.sampled_from(["Alex", "Jordan", "Taylor", "Morgan"]))
        raw_s_md = f"---\nid: '{s_idx:04d}'\ntitle: Story {s_idx}\nstatus: Accepted\npersona: {persona_name}\ngoverning_prd: {linked_prd}\noutcome_id: {outcome_id}\n---\n"
        stories.append(
            UserStory(
                id=sid,
                title=f"Story {s_idx}",
                status="Accepted",
                persona=persona_name,
                governing_prd=linked_prd,
                raw_markdown=raw_s_md,
            )
        )

    num_tasks = draw(st.integers(min_value=0, max_value=8))
    tasks: list[Task] = []
    for t_idx in range(1, num_tasks + 1):
        tid = f"TASK-{t_idx:04d}"
        gov_prds = draw(st.lists(st.sampled_from([p.id for p in prds]), max_size=2)) if prds else []
        gov_stories = draw(st.lists(st.sampled_from([s.id for s in stories]), max_size=2)) if stories else []
        outcome_id = draw(st.integers(min_value=1, max_value=5))
        raw_t_md = f"---\nid: '{t_idx:04d}'\ntitle: Task {t_idx}\nstatus: Refined\noutcome_id: {outcome_id}\n---\n"
        has_commit = draw(st.booleans())
        commits = [CommitInfo(hash="abc1234", author="Ty", date="2026-09-29", subject=f"{tid} work")] if has_commit else []
        tasks.append(
            Task(
                id=tid,
                title=f"Task {t_idx}",
                status=draw(st.sampled_from(["Complete", "Refined", "Proposed"])),
                governing_prds=gov_prds,
                governing_stories=gov_stories,
                raw_markdown=raw_t_md,
                commits=commits,
            )
        )

    personas = [
        Persona(id="alex", name="Alex", role="Architect"),
        Persona(id="jordan", name="Jordan", role="Lead"),
        Persona(id="taylor", name="Taylor", role="Product Manager"),
    ]

    return ProjectData(
        personas=personas,
        stories=stories,
        prds=prds,
        tasks=tasks,
    )


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    total=st.integers(min_value=-50, max_value=200),
    covered=st.integers(min_value=-50, max_value=200),
)
def test_calculate_outcome_coverage_bounds(total: int, covered: int):
    """Property: calculate_outcome_coverage is unconditionally bounded between 0.0 and 100.0."""
    pct = calculate_outcome_coverage(total, covered)
    assert 0.0 <= pct <= 100.0


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(project_data=random_project_data())
def test_deep_audit_generative_properties(project_data: ProjectData):
    """Property: Outcome coverage is bounded [0.0, 100.0], and all diagnostics cite offending IDs."""
    auditor = DeepPRDAuditor(project_data=project_data)
    result = auditor.audit_all_accepted()

    # 1. Coverage percentage invariant
    assert 0.0 <= result.coverage_pct <= 100.0
    if result.total_outcomes == 0:
        assert result.coverage_pct == 100.0
    else:
        assert result.covered_outcomes <= result.total_outcomes

    # 2. Orphaned outcome diagnostic invariants
    for orphan in result.orphaned_outcomes:
        assert orphan.diagnostic.strip() != ""
        assert orphan.prd_id in orphan.diagnostic
        assert orphan.outcome_text in orphan.diagnostic
        assert orphan.suggestion.strip() != ""
        assert orphan.prd_id in orphan.suggestion

    # 3. Unanchored task diagnostic invariants
    for unanchored in result.unanchored_tasks:
        assert unanchored.diagnostic.strip() != ""
        assert unanchored.task_id in unanchored.diagnostic
        assert unanchored.prd_id in unanchored.diagnostic

    # 4. Buffer status and drift invariants
    assert result.drift_count == len(result.orphaned_outcomes) + len(result.unanchored_tasks)
    if result.is_clean:
        assert result.buffer_status == "OPTIMAL"
    else:
        assert result.buffer_status == "INCOMPLETE_COVERAGE"

    # 5. Formatted report contains core summary metrics
    report = auditor.format_report(result)
    assert f"Outcome Coverage: {result.coverage_pct:.0f}%" in report
    assert f"Specification Drift: {result.drift_count} issues detected" in report


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(project_data=random_project_data())
def test_traceability_engine_generative_properties(project_data: ProjectData):
    """Property: Persona lineage records are unbroken and audit reports cite persona names and orphan tasks."""
    engine = PersonaTraceabilityEngine(project_data=project_data)
    lineage = engine.build_lineage()

    for rec in lineage:
        assert rec.persona != ""
        assert rec.prd != ""
        assert rec.story != ""
        assert rec.task != ""
        assert rec.commit != ""
        assert rec.status != ""
        assert rec.permalink.startswith("#tab=prds&entity=")

    report = engine.audit_persona_coverage()
    for w in report.warnings:
        assert "Warning: Persona" in w
        assert "0 active stories in the current milestone" in w

    for ot in report.orphan_tasks:
        assert "Orphan Task:" in ot
        assert "lacks governing user story or persona lineage" in ot
