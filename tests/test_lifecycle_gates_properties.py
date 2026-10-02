import string

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.core.lifecycle_gates import (
    ALL_DOD_GATE_RULES,
    ALL_DOR_GATE_RULES,
    DoDGateResult,
    DoRGateResult,
    LifecycleGateOrchestrator,
)
from spec_ops.core.models import Task

SAFE_CHARS = string.ascii_letters + string.digits + "_-"
SAFE_ALPHANUM = st.text(alphabet=SAFE_CHARS, min_size=1, max_size=30)


@given(
    task_id=SAFE_ALPHANUM,
    title=SAFE_ALPHANUM,
    status=st.sampled_from(["Refined", "Proposed", "Complete", "In-Progress"]),
    target_bc=SAFE_ALPHANUM,
    has_artifacts=st.booleans(),
)
def test_property_dor_evaluation_safety(
    task_id: str,
    title: str,
    status: str,
    target_bc: str,
    has_artifacts: bool,
):
    """Asserts that evaluate_dor never crashes on arbitrary task attributes and returns well-formed DoRGateResult."""
    task = Task(
        id=task_id,
        title=title,
        status=status,
        target_bc=target_bc,
        governing_prds=["PRD-0001"] if has_artifacts else [],
        governing_stories=["US-0001"] if has_artifacts else [],
        governing_adrs=["ADR-0001"] if has_artifacts else [],
    )
    res = LifecycleGateOrchestrator.evaluate_dor(task)
    assert isinstance(res, DoRGateResult)
    assert res.task_id == task.canonical_id
    assert res.passed in (True, False)
    assert len(res.rules) == len(ALL_DOR_GATE_RULES)
    assert isinstance(res.violations, list)
    assert isinstance(res.recommendations, list)


@given(
    task_id=SAFE_ALPHANUM,
    frontdoors=st.booleans(),
    bdd=st.booleans(),
    hypothesis=st.booleans(),
    mutation_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    health=st.booleans(),
    lockfile=st.booleans(),
    docs=st.booleans(),
    backlog=st.booleans(),
    trailers=st.booleans(),
    dual_custody=st.booleans(),
)
def test_property_dod_evaluation_safety(
    task_id: str,
    frontdoors: bool,
    bdd: bool,
    hypothesis: bool,
    mutation_score: float,
    health: bool,
    lockfile: bool,
    docs: bool,
    backlog: bool,
    trailers: bool,
    dual_custody: bool,
):
    """Asserts that evaluate_dod passes if and only if all 10 criteria pass and mutation score >= 80%."""
    task = Task(id=task_id, title="Test Task", target_bc="core")
    data = {
        "frontdoors_passed": frontdoors,
        "bdd_passed": bdd,
        "hypothesis_passed": hypothesis,
        "mutation_score": mutation_score,
        "health_passed": health,
        "lockfile_intact": lockfile,
        "docs_synced": docs,
        "backlog_progressed": backlog,
        "commit_trailers_valid": trailers,
        "dual_custody_signed": dual_custody,
    }
    res = LifecycleGateOrchestrator.evaluate_dod(task, verification_data=data)
    assert isinstance(res, DoDGateResult)
    assert len(res.rules) == len(ALL_DOD_GATE_RULES)

    expected_pass = (
        frontdoors
        and bdd
        and hypothesis
        and (mutation_score >= 80.0)
        and health
        and lockfile
        and docs
        and backlog
        and trailers
        and dual_custody
    )
    assert res.passed == expected_pass
