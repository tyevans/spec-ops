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


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    invs_a=st.lists(st.text(min_size=1, max_size=30), min_size=0, max_size=10, unique=True),
    invs_b=st.lists(st.text(min_size=1, max_size=30), min_size=0, max_size=10, unique=True),
    perm_a_seed=st.integers(min_value=0, max_value=100),
    perm_b_seed=st.integers(min_value=0, max_value=100),
)
def test_profile_diff_commutative_with_respect_to_invariant_ordering(
    invs_a: list[str],
    invs_b: list[str],
    perm_a_seed: int,
    perm_b_seed: int,
):
    """Property (ADR-0009): Profile diff calculation is commutative with respect to invariant ordering."""
    import random
    from spec_ops.profiles.diff import compute_profile_diff

    # Generate permutations
    r_a = random.Random(perm_a_seed)
    r_b = random.Random(perm_b_seed)
    shuffled_a = list(invs_a)
    shuffled_b = list(invs_b)
    r_a.shuffle(shuffled_a)
    r_b.shuffle(shuffled_b)

    prof_a_orig = Profile(id="prof_a", name="A", description="", invariants=invs_a)
    prof_b_orig = Profile(id="prof_b", name="B", description="", invariants=invs_b)

    prof_a_shuf = Profile(id="prof_a", name="A", description="", invariants=shuffled_a)
    prof_b_shuf = Profile(id="prof_b", name="B", description="", invariants=shuffled_b)

    diff1 = compute_profile_diff(prof_a_orig, prof_b_orig)
    diff2 = compute_profile_diff(prof_a_shuf, prof_b_shuf)

    # Invariant diffs must match regardless of ordering
    assert diff1.invariants.added == diff2.invariants.added
    assert diff1.invariants.removed == diff2.invariants.removed

    # Commutativity of additions vs removals when directions flip
    diff_rev = compute_profile_diff(prof_b_orig, prof_a_orig)
    assert diff1.invariants.added == diff_rev.invariants.removed
    assert diff1.invariants.removed == diff_rev.invariants.added


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    adr_titles=st.lists(st.text(min_size=3, max_size=20), min_size=1, max_size=4, unique=True),
    local_edit_text=st.text(min_size=5, max_size=50),
    upstream_edit_text=st.text(min_size=5, max_size=50),
)
def test_migration_abort_preserves_repo_verbatim(
    tmp_path_factory: Any,
    adr_titles: list[str],
    local_edit_text: str,
    upstream_edit_text: str,
):
    """Property (ADR-0009): Aborting a conflicting profile migration cleanly preserves repository state verbatim."""
    import hashlib
    from spec_ops.profiles.migration import execute_profile_migration

    tmp = tmp_path_factory.mktemp("prop_repo")
    adrs_dir = tmp / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)

    base_adrs: list[BaselineADR] = []
    up_adrs: list[BaselineADR] = []

    for i, title in enumerate(adr_titles, start=1):
        slug = f"adr-{i}"
        orig_body = f"# ADR {i}: {title}\nOriginal baseline body.\n"
        (adrs_dir / f"adr-{i:04d}-{slug}.md").write_text(orig_body, encoding="utf-8")
        base_adrs.append(BaselineADR(number=i, slug=slug, title=title, content=orig_body))

        # Upstream modified version
        up_body = f"# ADR {i}: {title}\nUpstream modified: {upstream_edit_text}\n"
        up_adrs.append(BaselineADR(number=i, slug=slug, title=title, content=up_body))

    # Add local conflict to first ADR
    conflict_file = adrs_dir / f"adr-0001-adr-1.md"
    conflict_file.write_text(f"# ADR 1: {adr_titles[0]}\nLocal modified: {local_edit_text}\n", encoding="utf-8")

    (tmp / "specops.toml").write_text('[project]\nname = "prop-test"\n[profiles]\ninstalled = ["core@1.0.0"]\n', encoding="utf-8")
    (tmp / "AGENTS.md").write_text("# Constitution\n1. Rule 1\n", encoding="utf-8")

    # Snapshot entire repo directory before migration
    before_hashes: dict[str, str] = {}
    for p in sorted(tmp.rglob("*")):
        if p.is_file():
            rel = p.relative_to(tmp).as_posix()
            before_hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    base_prof = Profile(id="core", name="Core", description="", version="1.0.0", adrs=base_adrs)
    up_prof = Profile(id="core", name="Core", description="", version="2.0.0", adrs=up_adrs)

    # Execute migration with abort action
    res = execute_profile_migration(up_prof, tmp, base_profile=base_prof, action="abort")
    assert res.success is False
    assert res.aborted is True

    # Snapshot after migration
    after_hashes: dict[str, str] = {}
    for p in sorted(tmp.rglob("*")):
        if p.is_file():
            rel = p.relative_to(tmp).as_posix()
            after_hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    # Assert repo state is preserved verbatim
    assert before_hashes == after_hashes

