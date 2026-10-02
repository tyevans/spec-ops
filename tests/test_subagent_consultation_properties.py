import string

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.core.subagent_consultation import (
    ConsultedSpecReference,
    SpecConsultationValidator,
    SubagentConsultationRequest,
    SubagentConsultationResponse,
)

SAFE_CHARS = string.ascii_letters + string.digits + "_-"
SAFE_ALPHANUM = st.text(alphabet=SAFE_CHARS, min_size=1, max_size=30)
SPEC_TYPES = st.sampled_from(["persona", "prd", "story", "adr", "backlog"])


@given(
    sender=SAFE_ALPHANUM,
    recipient=SAFE_ALPHANUM,
    phase=SAFE_ALPHANUM,
    task_id=SAFE_ALPHANUM,
    target_bc=SAFE_ALPHANUM,
    spec_type=SPEC_TYPES,
    spec_id=SAFE_ALPHANUM,
)
def test_property_subagent_consultation_evaluation_safety(
    sender: str,
    recipient: str,
    phase: str,
    task_id: str,
    target_bc: str,
    spec_type: str,
    spec_id: str,
):
    """Asserts that evaluating arbitrary consultation requests never crashes and always returns valid response dataclass."""
    spec_ref = ConsultedSpecReference(
        spec_type=spec_type,
        identifier=spec_id,
        is_valid=True,
    )
    req = SubagentConsultationRequest(
        sender_role=sender,
        recipient_role=recipient,
        phase=phase,
        task_id=task_id,
        target_bc=target_bc,
        consulted_specs=[spec_ref],
        changed_files=[f"src/spec_ops/{target_bc}/module.py"],
    )

    resp = SpecConsultationValidator.evaluate_peer_consultation(req)
    assert isinstance(resp, SubagentConsultationResponse)
    assert resp.approved in (True, False)
    assert resp.execution_state in ("APPROVED", "BLOCKED", "NEEDS_REVISION")
    assert isinstance(resp.feedback, list)
    assert isinstance(resp.guidance, str)
    assert len(resp.guidance) > 0


@given(
    backlog_path=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_/-", min_size=1, max_size=40).map(
        lambda s: f"docs/project/backlog/{s}.md"
    ),
    target_bc=SAFE_ALPHANUM,
)
def test_property_backlog_modifications_strictly_rejected(backlog_path: str, target_bc: str):
    """Asserts that any modification targeting docs/project/backlog/ is unconditionally flagged as ADR-0005 violation."""
    spec_ref = ConsultedSpecReference(spec_type="adr", identifier="0005", is_valid=True)
    req = SubagentConsultationRequest(
        sender_role="implementation-agent",
        recipient_role="review-agent",
        phase="implementation",
        task_id="TASK-0187",
        target_bc=target_bc,
        consulted_specs=[spec_ref],
        changed_files=[backlog_path],
    )
    resp = SpecConsultationValidator.evaluate_peer_consultation(req)
    assert resp.approved is False
    assert resp.execution_state == "BLOCKED"
    assert any("ADR-0005" in err for err in resp.adr_violations)
