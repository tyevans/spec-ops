"""Generative property-based tests for modular architectural profile composition and inheritance (ADR-0009)."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.config.models import SliceConfig
from spec_ops.profiles.composer import (
    compose_profiles,
    resolve_inheritance_dag,
)
from spec_ops.profiles.models import (
    BaselineADR,
    Profile,
    ProfileInheritanceError,
)


@st.composite
def dag_profile_hierarchy(draw: Any) -> tuple[dict[str, Profile], str]:
    """Generates an arbitrary acyclic profile inheritance hierarchy (DAG)."""
    num_nodes = draw(st.integers(min_value=2, max_value=8))
    node_names = [f"prof_{i}" for i in range(num_nodes)]

    profiles: dict[str, Profile] = {}

    for i, name in enumerate(node_names):
        # Edges can only point to previous nodes (j < i), ensuring acyclicity
        possible_parents = node_names[:i]
        num_parents = draw(st.integers(min_value=0, max_value=min(2, len(possible_parents))))
        parents = draw(st.lists(st.sampled_from(possible_parents), min_size=num_parents, max_size=num_parents, unique=True)) if possible_parents else []

        file_limit = draw(st.integers(min_value=100, max_value=600))
        adrs = [
            BaselineADR(
                number=100 * (i + 1) + k,
                slug=f"adr-{i}-{k}",
                title=f"ADR {i} {k}",
                content=f"# ADR {i} {k}",
            )
            for k in range(draw(st.integers(min_value=0, max_value=2)))
        ]
        invariants = draw(st.lists(st.text(min_size=3, max_size=20), max_size=2))

        prof = Profile(
            id=name,
            name=name.title(),
            description=f"Description of {name}",
            extends=parents,
            adrs=adrs,
            overrides={"architecture": {"file_length_limit": file_limit}},
            invariants=invariants,
        )
        profiles[name] = prof

    root_id = node_names[-1]
    return profiles, root_id


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(dag_data=dag_profile_hierarchy())
def test_dag_resolution_determinism(dag_data: tuple[dict[str, Profile], str]):
    """Property: Evaluating DAG profile composition resolves deterministically without side effects."""
    profiles, root_id = dag_data

    def mock_loader(pid: str) -> Profile:
        return profiles[pid]

    # Run resolution twice
    res1 = compose_profiles([profiles[root_id]], loader=mock_loader)
    res2 = compose_profiles([profiles[root_id]], loader=mock_loader)

    assert res1.profile_ids == res2.profile_ids
    assert res1.file_length_limit == res2.file_length_limit
    assert len(res1.adrs) == len(res2.adrs)
    assert [a.canonical_id for a in res1.adrs] == [a.canonical_id for a in res2.adrs]
    assert res1.overrides == res2.overrides
    assert res1.invariants == res2.invariants


@st.composite
def cyclic_profile_hierarchy(draw: Any) -> tuple[dict[str, Profile], str]:
    """Generates a profile inheritance graph that is guaranteed to contain a cycle."""
    cycle_length = draw(st.integers(min_value=2, max_value=6))
    cycle_nodes = [f"cycle_node_{i}" for i in range(cycle_length)]

    profiles: dict[str, Profile] = {}
    for i, name in enumerate(cycle_nodes):
        next_name = cycle_nodes[(i + 1) % cycle_length]
        profiles[name] = Profile(
            id=name,
            name=name,
            description="",
            extends=[next_name],
        )

    root_id = cycle_nodes[0]
    return profiles, root_id


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cyclic_data=cyclic_profile_hierarchy())
def test_cyclic_inheritance_rejected(cyclic_data: tuple[dict[str, Profile], str]):
    """Property: Any profile inheritance graph containing a cycle is rejected with informative error."""
    profiles, root_id = cyclic_data

    def mock_loader(pid: str) -> Profile:
        return profiles[pid]

    with pytest.raises(ProfileInheritanceError) as exc_info:
        compose_profiles([profiles[root_id]], loader=mock_loader)

    err_msg = str(exc_info.value)
    assert "Profile Inheritance Error: Circular dependency detected" in err_msg
    assert "->" in err_msg
