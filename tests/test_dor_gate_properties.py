"""Hypothesis generative property invariant tests for Definition of Ready gatekeeper (ADR-0009)."""

from __future__ import annotations

from pathlib import Path
from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from spec_ops.backlog.dor_gate import (
    ALL_DOR_RULES,
    RULE_BOUNDED_CONTEXT,
    RULE_FILE_LIMIT_SCOPE,
    RULE_GHERKIN_SCENARIOS,
    RULE_GOVERNING_ADRS,
    RULE_MUTATION_SCOPE,
    RULE_PERSONA_PRD,
    RULE_YAML_FRONTMATTER,
    DoRAuditReport,
    audit_task_health,
)
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project


@pytest.fixture(scope="module")
def shared_repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, SpecOpsConfig]:
    repo = tmp_path_factory.mktemp("prop_repo")
    init_project(name="PropertyTestRepo", target_dir=repo)
    cfg = SpecOpsConfig(root_dir=repo)

    # Scaffold accepted ADR
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "0001-pmac.md").write_text("---\nid: '0001'\nstatus: Accepted\n---\n", encoding="utf-8")

    # Scaffold accepted PRD
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "0001-prd.md").write_text("---\nid: '0001'\nstatus: Accepted\ntarget_persona: Jordan\n---\n", encoding="utf-8")

    # Scaffold accepted Story
    stories_dir = repo / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0001-story.md").write_text(
        "---\nid: '0001'\nstatus: Accepted\npersona: Jordan\n---\nGiven x\nWhen y\nThen z\n",
        encoding="utf-8",
    )

    return repo, cfg


# ------------------------------------------------------------------------------
# Property 1: Any task missing one or more required DoR elements is rejected
# ------------------------------------------------------------------------------


@settings(max_examples=50, deadline=None)
@given(
    has_valid_frontmatter=st.booleans(),
    has_target_bc=st.booleans(),
    has_adr=st.booleans(),
    has_prd_and_persona=st.booleans(),
    has_gherkin=st.booleans(),
    has_feasible_scope=st.booleans(),
    has_mutation_scope=st.booleans(),
)
def test_property_missing_element_deterministically_rejected(
    shared_repo: tuple[Path, SpecOpsConfig],
    has_valid_frontmatter: bool,
    has_target_bc: bool,
    has_adr: bool,
    has_prd_and_persona: bool,
    has_gherkin: bool,
    has_feasible_scope: bool,
    has_mutation_scope: bool,
):
    """Invariant: If ANY of the 7 DoR rules fails, is_ready is False and errors > 0."""
    _, cfg = shared_repo

    task_id = "0042" if has_valid_frontmatter else ""
    title = "Test Task" if has_valid_frontmatter else ""
    status = "Proposed" if has_valid_frontmatter else ""
    target_bc = "core" if has_target_bc else ""
    governing_adrs = ["ADR-0001"] if has_adr else []
    governing_prds = ["PRD-0001"] if has_prd_and_persona else []
    persona = "Jordan" if has_prd_and_persona else ""
    mutation_scope = "src/core" if has_mutation_scope else ""

    body_parts = []
    if has_gherkin:
        body_parts.append("Given system ready\nWhen trigger runs\nThen expected state")
    if not has_feasible_scope:
        body_parts.append("This task involves modifying 8 different bounded contexts spanning >500 expected lines.")
    body = "\n".join(body_parts)

    task = Task(
        id=task_id,
        title=title,
        status=status,
        target_bc=target_bc,
        governing_adrs=governing_adrs,
        governing_prds=governing_prds,
        persona=persona,
        mutation_scope=mutation_scope,
        body=body,
    )

    report = audit_task_health(task, cfg)
    all_rules_satisfied = (
        has_valid_frontmatter
        and has_target_bc
        and has_adr
        and has_prd_and_persona
        and has_gherkin
        and has_feasible_scope
        and has_mutation_scope
    )

    if not all_rules_satisfied:
        assert report.is_ready is False
        assert len(report.errors) > 0
    else:
        assert report.is_ready is True
        assert len(report.errors) == 0


# ------------------------------------------------------------------------------
# Property 2: Compliant tasks always pass all 7 criteria
# ------------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(
    task_num=st.integers(min_value=1, max_value=9999),
    title=st.text(min_size=3, max_size=50).filter(lambda s: s.strip() != ""),
    persona=st.sampled_from(["Alex", "Jordan", "Morgan", "Riley", "Taylor"]),
    bc=st.sampled_from(["core", "backlog", "prd", "visualizer", "security"]),
)
def test_property_fully_compliant_task_always_passes(
    shared_repo: tuple[Path, SpecOpsConfig],
    task_num: int,
    title: str,
    persona: str,
    bc: str,
):
    """Invariant: Fully compliant task satisfies all 7 DoR rules and achieves is_ready=True."""
    _, cfg = shared_repo
    task = Task(
        id=f"{task_num:04d}",
        title=title.replace("\n", " ").replace("\r", " "),
        status="Proposed",
        target_bc=bc,
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0001"],
        persona=persona,
        mutation_scope=f"src/spec_ops/{bc}",
        body="Given a valid precondition\nWhen the frontdoor executes\nThen contract holds",
    )
    report = audit_task_health(task, cfg)
    assert report.is_ready is True
    assert len(report.errors) == 0
    for r in ALL_DOR_RULES:
        assert report.rules[r] is True


# ------------------------------------------------------------------------------
# Property 3: Scope violations deterministically trigger single-responsibility advice
# ------------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(
    num_bcs=st.integers(min_value=2, max_value=10),
    expected_lines=st.integers(min_value=501, max_value=5000),
)
def test_property_scope_violation_invariants(
    shared_repo: tuple[Path, SpecOpsConfig],
    num_bcs: int,
    expected_lines: int,
):
    """Invariant: Tasks modifying >1 BC or >500 expected lines are rejected with ADR-0002 advice."""
    _, cfg = shared_repo
    task = Task(
        id="0099",
        title="Oversized Slice",
        status="Proposed",
        target_bc="core",
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0001"],
        persona="Jordan",
        mutation_scope="src/core",
        body=f"Specification proposes modifying {num_bcs} different bounded contexts spanning >500 expected lines.\n"
        f"Given x\nWhen y\nThen z\n",
        expected_lines=expected_lines,
    )
    report = audit_task_health(task, cfg, strict=True)
    assert report.is_ready is False
    assert report.rules[RULE_FILE_LIMIT_SCOPE] is False
    assert any("violates single-responsibility scope" in err for err in report.errors)
    assert any("Decompose into thin vertical slices or architectural spikes (ADR-0002)" in rec for rec in report.recommendations)


# ------------------------------------------------------------------------------
# Property 4: Missing Gherkin scenarios always cite ADR-0006
# ------------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(
    notes=st.text(min_size=1, max_size=100).filter(
        lambda t: "given" not in t.lower() and "when" not in t.lower() and "then" not in t.lower()
    )
)
def test_property_missing_gherkin_always_flags_adr0006(
    shared_repo: tuple[Path, SpecOpsConfig],
    notes: str,
):
    """Invariant: Tasks lacking Gherkin syntax deterministically flag missing ADR-0006 criteria."""
    _, cfg = shared_repo
    task = Task(
        id="0099",
        title="No Gherkin Task",
        status="Proposed",
        target_bc="core",
        governing_adrs=["ADR-0001"],
        governing_prds=["PRD-0001"],
        persona="Jordan",
        mutation_scope="src/core",
        body=f"## Problem Notes\n{notes}\n",
    )
    report = audit_task_health(task, cfg)
    assert report.is_ready is False
    assert report.rules[RULE_GHERKIN_SCENARIOS] is False
    assert any("TASK-0099: DoR Violation - Missing executable Gherkin acceptance criteria (ADR-0006)" in err for err in report.errors)


# ------------------------------------------------------------------------------
# Property 5: format_report output invariants
# ------------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(
    task_id=st.from_regex(r"TASK-\d{4}", fullmatch=True),
    is_ready=st.booleans(),
    rule_statuses=st.lists(st.booleans(), min_size=len(ALL_DOR_RULES), max_size=len(ALL_DOR_RULES)),
    err_text=st.text(min_size=1, max_size=30).filter(lambda s: s.strip() != ""),
)
def test_property_format_report_structure(
    task_id: str,
    is_ready: bool,
    rule_statuses: list[bool],
    err_text: str,
):
    """Invariant: format_report() contains task ID, every DoR rule, and matching Pass/Fail rows."""
    rules_dict = {rule: rule_statuses[i] for i, rule in enumerate(ALL_DOR_RULES)}
    errors = [err_text] if not is_ready else []
    report = DoRAuditReport(task_id=task_id, is_ready=is_ready, rules=rules_dict, errors=errors)

    rendered = report.format_report()
    assert task_id in rendered
    assert "Rule Check                         | Status" in rendered
    for rule, status in rules_dict.items():
        assert rule in rendered
        expected_status = "Pass" if status else "Fail"
        assert f"{rule:<34} | {expected_status}" in rendered
    if errors:
        assert "Violations:" in rendered
        assert f"❌ {err_text}" in rendered
