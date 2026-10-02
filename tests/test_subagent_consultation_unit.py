"""Unit tests for subagent consultation models, protocol, and validator (ADR-0003 compliant)."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.core.subagent_consultation import (
    ConsultedSpecReference,
    SpecConsultationValidator,
    SubagentConsultationRequest,
    SubagentConsultationResponse,
)


def test_consulted_spec_reference_to_dict():
    ref = ConsultedSpecReference(
        spec_type="adr",
        identifier="ADR-0001",
        path="docs/project/adrs/accepted/adr-0001.md",
        title="Specification as Code",
        status="Accepted",
        invariants_or_outcomes=["Specs in git"],
        is_valid=True,
    )
    data = ref.to_dict()
    assert data["identifier"] == "ADR-0001"
    assert data["spec_type"] == "adr"
    assert data["status"] == "Accepted"
    assert data["invariants_or_outcomes"] == ["Specs in git"]
    assert data["is_valid"] is True


def test_subagent_consultation_request_and_response_to_dict():
    req = SubagentConsultationRequest(
        sender_role="implementation-agent",
        recipient_role="review-agent",
        phase="implementation",
        task_id="TASK-0187",
        target_bc="core",
        inquiry_type="peer_review",
        query="Verify changes",
    )
    req_dict = req.to_dict()
    assert req_dict["task_id"] == "TASK-0187"
    assert req_dict["sender_role"] == "implementation-agent"

    resp = SubagentConsultationResponse(
        approved=True,
        feedback=["Clean implementation"],
        execution_state="APPROVED",
        guidance="Ready for commit staging",
    )
    resp_dict = resp.to_dict()
    assert resp_dict["approved"] is True
    assert resp_dict["execution_state"] == "APPROVED"


def test_resolve_spec_file_and_verify(tmp_path: Path):
    repo_root = tmp_path
    stories_dir = repo_root / "docs" / "project" / "user_stories"
    stories_dir.mkdir(parents=True)
    personas_file = stories_dir / "PERSONAS.md"
    personas_file.write_text("# Personas\n\nAlex\n", encoding="utf-8")

    adrs_dir = repo_root / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True)
    adr_file = adrs_dir / "adr-0001-specification-as-code.md"
    adr_file.write_text(
        "---\nid: '0001'\ntitle: Specification as Code\nstatus: Accepted\n---\n\n- Invariant: Specs must be version-locked\n",
        encoding="utf-8",
    )

    prd_dir = repo_root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True)
    prd_file = prd_dir / "prd-0006-autonomous-sdlc.md"
    prd_file.write_text(
        "---\nid: '0006'\ntitle: Autonomous SDLC\nstage: accepted\n---\n\nCheckable Outcomes:\n- Outcome 1: Inline skill\n",
        encoding="utf-8",
    )

    story_file = stories_dir / "accepted" / "us-0117-orchestrator.md"
    story_file.parent.mkdir(parents=True, exist_ok=True)
    story_file.write_text(
        "---\nid: '0117'\ntitle: Orchestrator Skill\nstatus: Accepted\n---\n\nScenario: Orchestration Run\n  Given foo\n",
        encoding="utf-8",
    )

    # 1. Resolve and verify persona
    ref_persona = SpecConsultationValidator.verify_spec_reference(
        repo_root, ConsultedSpecReference(spec_type="persona", identifier="PERSONAS.md")
    )
    assert ref_persona.is_valid is True
    assert ref_persona.title == "PERSONAS"

    # 2. Resolve and verify ADR
    ref_adr = SpecConsultationValidator.verify_spec_reference(
        repo_root, ConsultedSpecReference(spec_type="adr", identifier="0001")
    )
    assert ref_adr.is_valid is True
    assert ref_adr.title == "Specification as Code"
    assert any("must be version-locked" in inv for inv in ref_adr.invariants_or_outcomes)

    # 3. Resolve and verify PRD
    ref_prd = SpecConsultationValidator.verify_spec_reference(
        repo_root, ConsultedSpecReference(spec_type="prd", identifier="PRD-0006")
    )
    assert ref_prd.is_valid is True
    assert ref_prd.title == "Autonomous SDLC"
    assert any("Inline skill" in o for o in ref_prd.invariants_or_outcomes)

    # 4. Resolve and verify story
    ref_story = SpecConsultationValidator.verify_spec_reference(
        repo_root, ConsultedSpecReference(spec_type="story", identifier="US-0117")
    )
    assert ref_story.is_valid is True
    assert ref_story.title == "Orchestrator Skill"
    assert any("Orchestration Run" in sc for sc in ref_story.invariants_or_outcomes)


def test_verify_spec_reference_not_found(tmp_path: Path):
    ref = SpecConsultationValidator.verify_spec_reference(
        tmp_path, ConsultedSpecReference(spec_type="adr", identifier="9999")
    )
    assert ref.is_valid is False
    assert "not found" in ref.error_message


def test_evaluate_peer_consultation_backlog_violation():
    req = SubagentConsultationRequest(
        sender_role="implementation-agent",
        recipient_role="review-agent",
        phase="implementation",
        task_id="TASK-0187",
        target_bc="core",
        consulted_specs=[ConsultedSpecReference(spec_type="adr", identifier="0001", is_valid=True)],
        changed_files=["docs/project/backlog/refined/0187.md"],
    )
    resp = SpecConsultationValidator.evaluate_peer_consultation(req)
    assert resp.approved is False
    assert resp.execution_state == "BLOCKED"
    assert any("ADR-0005" in v for v in resp.adr_violations)
    assert any("Backlog files must never be modified" in f for f in resp.feedback)


def test_format_consultation_brief():
    req = SubagentConsultationRequest(
        sender_role="implementation-agent",
        recipient_role="review-agent",
        phase="implementation",
        task_id="TASK-0187",
        target_bc="core",
        consulted_specs=[
            ConsultedSpecReference(
                spec_type="adr",
                identifier="ADR-0001",
                title="Specification as Code",
                status="Accepted",
                invariants_or_outcomes=["Specs in git"],
            )
        ],
        changed_files=["src/spec_ops/core/subagent_consultation.py"],
        inquiry_type="peer_review",
        query="Please inspect seam boundaries.",
    )
    brief = SpecConsultationValidator.format_consultation_brief(req)
    assert "# Multi-Agent Consultation Brief: TASK-0187" in brief
    assert "implementation-agent -> **Recipient**: review-agent" in brief
    assert "ADR-0001" in brief
    assert "Please inspect seam boundaries." in brief
