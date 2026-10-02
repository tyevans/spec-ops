"""Unit tests for Autonomous User Persona Journey Friction Auditor and Heuristic Evaluator."""

from __future__ import annotations

import argparse
from pathlib import Path

from spec_ops.core.persona_models import PersonaDocument, PersonaProfile
from spec_ops.docs.models import ParsedCLICommand
from spec_ops.prd.persona_friction import (
    FrictionAuditReport,
    PersonaFrictionAuditor,
    WorkflowFriction,
    compute_friction_index,
    generate_recommendations,
)


def test_compute_friction_index_bounds() -> None:
    """Assert friction index is strictly bounded in [0.0, 10.0]."""
    assert compute_friction_index(1, 0, 0) == 0.0
    assert compute_friction_index(-5, -2, -10) == 0.0
    assert compute_friction_index(50, 50, 100) == 10.0
    assert 0.0 <= compute_friction_index(3, 2, 5) <= 10.0


def test_compute_friction_role_heuristics() -> None:
    """Assert role-specific heuristics correctly adjust friction."""
    # Agent without --json
    agent_score = compute_friction_index(2, 0, 2, has_json=False, has_non_interactive=True, persona_role="Autonomous Coding Agent")
    agent_score_json = compute_friction_index(2, 0, 2, has_json=True, has_non_interactive=True, persona_role="Autonomous Coding Agent")
    assert agent_score > agent_score_json

    # Product manager with multiple positionals and deep command
    pm_score = compute_friction_index(3, 2, 6, True, True, persona_role="Product Manager")
    eng_score = compute_friction_index(3, 2, 6, True, True, persona_role="Systems Architect")
    assert pm_score >= eng_score


def test_generate_recommendations() -> None:
    """Assert ergonomic recommendations match ceremony complexity."""
    p_agent = PersonaProfile(name="Morgan", role="The Autonomous Coding Agent", role_description="LLM Agent")
    p_pm = PersonaProfile(name="Taylor", role="The Product Manager", role_description="PM")

    # Low friction
    recs_low = generate_recommendations("spec-ops health", set(), [], p_agent, 1.5)
    assert any("optimal" in r.lower() for r in recs_low)

    # High depth command
    recs_deep = generate_recommendations("spec-ops prd uat sign", {"--prd", "--outcome"}, ["prd_id"], p_pm, 6.5)
    assert any("alias" in r.lower() for r in recs_deep)
    assert any("studio" in r.lower() or "wizard" in r.lower() for r in recs_deep)

    # Agent lacking --json
    recs_agent = generate_recommendations("spec-ops queue tree", set(), [], p_agent, 5.0)
    assert any("--json" in r for r in recs_agent)

    # Multiple positionals
    recs_pos = generate_recommendations("spec-ops graph cycle", set(), ["src", "dst"], p_pm, 6.0)
    assert any("positional" in r.lower() for r in recs_pos)


def test_workflow_friction_and_report_serialization() -> None:
    """Assert domain model serialization and formatting."""
    wf = WorkflowFriction(
        command="spec-ops prd uat sign",
        persona_id="taylor",
        persona_name="Taylor",
        persona_role="The Product Manager",
        base_score=4.0,
        friction_score=6.5,
        factors=["Depth 4", "Multi-positional"],
        recommendations=["Introduce alias", "Add wizard"],
    )
    d = wf.to_dict()
    assert d["command"] == "spec-ops prd uat sign"
    assert d["friction_score"] == 6.5

    report = FrictionAuditReport(
        workflows=[wf],
        personas_audited=["Taylor"],
        average_friction=6.5,
        threshold=5.0,
        flagged_count=1,
    )
    assert report.has_violations is True
    rep_d = report.to_dict()
    assert rep_d["evaluated_touchpoints"] == 1
    assert rep_d["flagged_count"] == 1

    text = report.format_text()
    assert "High-Friction Touchpoints" in text
    assert "spec-ops prd uat sign" in text

    # Report without threshold
    clean_report = FrictionAuditReport(
        workflows=[wf],
        personas_audited=["Taylor"],
        average_friction=6.5,
        threshold=None,
        flagged_count=0,
    )
    clean_text = clean_report.format_text()
    assert "Top Friction Touchpoints" in clean_text
    assert "Audit completed cleanly" in clean_text


def test_persona_friction_auditor_command_override() -> None:
    """Assert auditor evaluates explicit command overrides."""
    commands = {
        "spec-ops prd create": ParsedCLICommand(
            command="spec-ops prd create",
            options={"--title", "--persona"},
            positionals=[],
        ),
        "spec-ops prd complex": ParsedCLICommand(
            command="spec-ops prd complex",
            options={"--a", "--b", "--c", "--d", "--e", "--f", "--g"},
            positionals=["arg1", "arg2"],
        ),
    }

    auditor = PersonaFrictionAuditor()
    report = auditor.audit(commands_override=commands, persona_filter="taylor", threshold=5.0)

    assert len(report.personas_audited) == 1
    assert report.personas_audited[0] == "Taylor"
    assert len(report.workflows) == 2
    assert report.flagged_count >= 1
    assert report.has_violations is True


def test_persona_friction_auditor_fallback_personas() -> None:
    """Assert fallback personas are loaded if doc is missing."""
    auditor = PersonaFrictionAuditor(root_dir=Path("/nonexistent/path/specops"))
    personas = auditor.load_personas()
    assert len(personas) >= 6
    names = {p.name for p in personas}
    assert "Alex" in names
    assert "Morgan" in names
    assert "Taylor" in names
