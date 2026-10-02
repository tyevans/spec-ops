"""BDD step definitions for US-0117: Multi-Agent SDLC Subagent Delegation and Spec Consultation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.subagent_consultation import (
    ConsultedSpecReference,
    SpecConsultationValidator,
    SubagentConsultationRequest,
    SubagentConsultationResponse,
)

scenarios("features/us_0117_subagent_delegation.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parent.parent
    return {"repo_root": repo_root}


@given("an orchestrator agent coordinating a project lifecycle")
def setup_lead_orchestrator(bdd_ctx: dict[str, Any]):
    bdd_ctx["lead_role"] = "lead-orchestrator"
    bdd_ctx["delegated_phases"] = ["persona", "prd", "story", "slicing", "implementation"]


@when("the orchestrator delegates tasks across SDLC phases (personas, stories, PRD, tasks, implementation)")
def orchestrator_delegates_phases(bdd_ctx: dict[str, Any]):
    repo_root: Path = bdd_ctx["repo_root"]
    subagent_requests: list[SubagentConsultationRequest] = []

    # Implementation subagent consulting real repo specs
    specs = [
        ConsultedSpecReference(spec_type="persona", identifier="PERSONAS.md"),
        ConsultedSpecReference(spec_type="prd", identifier="0006"),
        ConsultedSpecReference(spec_type="story", identifier="0117"),
        ConsultedSpecReference(spec_type="adr", identifier="0001"),
    ]
    for s in specs:
        SpecConsultationValidator.verify_spec_reference(repo_root, s)

    req = SubagentConsultationRequest(
        sender_role="implementation-agent",
        recipient_role="lead-orchestrator",
        phase="implementation",
        task_id="TASK-0187",
        target_bc="core",
        consulted_specs=specs,
        changed_files=["src/spec_ops/core/subagent_consultation.py"],
        inquiry_type="execution_report",
        query="Completed implementation with spec consultation.",
    )
    subagent_requests.append(req)
    bdd_ctx["requests"] = subagent_requests
    bdd_ctx["responses"] = [
        SpecConsultationValidator.evaluate_peer_consultation(req, repo_root=repo_root)
        for req in subagent_requests
    ]


@then('specialized subagents consult existing approved specs in "docs/project/" to guide implementation')
def verify_subagents_consult_specs(bdd_ctx: dict[str, Any]):
    req: SubagentConsultationRequest = bdd_ctx["requests"][0]
    assert len(req.consulted_specs) >= 4
    for spec in req.consulted_specs:
        assert spec.is_valid is True
        assert spec.path.startswith("docs/project/")
        assert len(spec.title) > 0


@then("report execution state back to the lead orchestrator.")
def verify_execution_state_reported(bdd_ctx: dict[str, Any]):
    resp: SubagentConsultationResponse = bdd_ctx["responses"][0]
    assert resp.approved is True
    assert resp.execution_state == "APPROVED"
    assert len(resp.seam_violations) == 0
    assert len(resp.adr_violations) == 0


@given("an implementation subagent working in an isolated worktree")
def setup_worktree_subagent(bdd_ctx: dict[str, Any]):
    bdd_ctx["target_bc"] = "core"


@when("the subagent requests peer consultation for proposed cross-context modifications")
def subagent_requests_cross_context(bdd_ctx: dict[str, Any]):
    repo_root: Path = bdd_ctx["repo_root"]
    req = SubagentConsultationRequest(
        sender_role="implementation-agent",
        recipient_role="review-agent",
        phase="implementation",
        task_id="TASK-0187",
        target_bc="core",
        consulted_specs=[
            ConsultedSpecReference(spec_type="adr", identifier="0007", is_valid=True),
        ],
        changed_files=["src/spec_ops/visualizer/export.py"],
        inquiry_type="peer_review",
    )
    bdd_ctx["seam_response"] = SpecConsultationValidator.evaluate_peer_consultation(req, repo_root=repo_root)


@then("the peer review evaluates the request against active ADRs and bounded contexts")
def verify_peer_review_evaluation(bdd_ctx: dict[str, Any]):
    resp: SubagentConsultationResponse = bdd_ctx["seam_response"]
    assert len(resp.seam_violations) > 0
    assert any("Boundary seam crossing" in s for s in resp.seam_violations)
    assert any("visualizer" in s for s in resp.seam_violations)


@then("returns actionable feedback and approval state before commit staging.")
def verify_actionable_feedback(bdd_ctx: dict[str, Any]):
    resp: SubagentConsultationResponse = bdd_ctx["seam_response"]
    assert resp.approved is False
    assert resp.execution_state == "NEEDS_REVISION"
    assert len(resp.feedback) > 0
    assert any("interface contract between 'core' and 'visualizer'" in f for f in resp.feedback)


@given("an implementation subagent with missing or unapproved specifications")
def setup_missing_specs_subagent(bdd_ctx: dict[str, Any]):
    bdd_ctx["empty_request"] = SubagentConsultationRequest(
        sender_role="implementation-agent",
        recipient_role="review-agent",
        phase="implementation",
        task_id="TASK-0187",
        target_bc="core",
        consulted_specs=[],
        changed_files=["src/spec_ops/core/new_file.py"],
    )


@when("peer consultation evaluates the subagent request")
def evaluate_missing_specs(bdd_ctx: dict[str, Any]):
    repo_root: Path = bdd_ctx["repo_root"]
    bdd_ctx["empty_response"] = SpecConsultationValidator.evaluate_peer_consultation(
        bdd_ctx["empty_request"], repo_root=repo_root
    )


@then("missing specification errors are flagged")
def verify_missing_specs_flagged(bdd_ctx: dict[str, Any]):
    resp: SubagentConsultationResponse = bdd_ctx["empty_response"]
    assert resp.approved is False
    assert len(resp.missing_specs) > 0
    assert any("No approved specifications" in s for s in resp.missing_specs)


@then("the consultation guidance requires anchoring changes to accepted living specs.")
def verify_consultation_guidance(bdd_ctx: dict[str, Any]):
    resp: SubagentConsultationResponse = bdd_ctx["empty_response"]
    assert len(resp.guidance) > 0
    assert "Peer consultation blocked or needs revision" in resp.guidance
    assert any("Consult governing ADRs, PRDs, and user stories" in f for f in resp.feedback)
