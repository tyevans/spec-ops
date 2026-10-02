"""Hypothesis property-based tests for Persona Journey Friction Auditor."""

from __future__ import annotations

from hypothesis import given, strategies as st

from spec_ops.prd.persona_friction import compute_friction_index


@given(
    depth=st.integers(min_value=-500, max_value=5000),
    pos=st.integers(min_value=-500, max_value=5000),
    opts=st.integers(min_value=-500, max_value=5000),
    has_json=st.booleans(),
    has_non_interactive=st.booleans(),
    role=st.text(max_size=100),
)
def test_property_friction_index_strictly_bounded(
    depth: int,
    pos: int,
    opts: int,
    has_json: bool,
    has_non_interactive: bool,
    role: str,
) -> None:
    """Invariant: Friction score is always strictly bounded within [0.0, 10.0]."""
    score = compute_friction_index(
        depth=depth,
        positionals_count=pos,
        options_count=opts,
        has_json=has_json,
        has_non_interactive=has_non_interactive,
        persona_role=role,
    )
    assert isinstance(score, float)
    assert 0.0 <= score <= 10.0
    # Assert rounded to 2 decimal places
    assert score == round(score, 2)


@given(
    depth=st.integers(min_value=1, max_value=20),
    pos=st.integers(min_value=0, max_value=20),
    opts=st.integers(min_value=0, max_value=50),
    delta_pos=st.integers(min_value=1, max_value=10),
)
def test_property_friction_index_monotonic_with_positionals(
    depth: int,
    pos: int,
    opts: int,
    delta_pos: int,
) -> None:
    """Invariant: Adding positional arguments never reduces cognitive friction."""
    score1 = compute_friction_index(depth, pos, opts, True, True, "Staff Engineer")
    score2 = compute_friction_index(depth, pos + delta_pos, opts, True, True, "Staff Engineer")
    assert score2 >= score1


@given(
    depth=st.integers(min_value=1, max_value=10),
    pos=st.integers(min_value=0, max_value=10),
    opts=st.integers(min_value=0, max_value=20),
)
def test_property_agent_json_never_increases_friction(
    depth: int,
    pos: int,
    opts: int,
) -> None:
    """Invariant: Adding --json output never increases friction for autonomous agents."""
    no_json = compute_friction_index(depth, pos, opts, has_json=False, has_non_interactive=True, persona_role="Autonomous Agent")
    with_json = compute_friction_index(depth, pos, opts, has_json=True, has_non_interactive=True, persona_role="Autonomous Agent")
    assert with_json <= no_json
