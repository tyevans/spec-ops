"""Unit tests for profile composition and override resolution engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.config.models import SliceConfig
from spec_ops.profiles.composer import (
    compose_profiles,
    load_profile_definition,
    merge_overrides,
    parse_adr_content,
    parse_profile_toml,
    resolve_inheritance_dag,
)
from spec_ops.profiles.models import (
    ADRCollisionError,
    BaselineADR,
    Profile,
    ProfileError,
    ProfileInheritanceError,
)


def test_merge_overrides_basic():
    base = {"architecture": {"file_length_limit": 500, "buffer_target": 10}, "project": "Alpha"}
    override = {"architecture": {"file_length_limit": 350}, "quality": {"require_mutation_testing": True}}

    merged = merge_overrides(base, override)
    assert merged["architecture"]["file_length_limit"] == 350
    assert merged["architecture"]["buffer_target"] == 10
    assert merged["project"] == "Alpha"
    assert merged["quality"]["require_mutation_testing"] is True


def test_merge_overrides_empty():
    assert merge_overrides({}, {}) == {}
    assert merge_overrides({"a": 1}, {}) == {"a": 1}
    assert merge_overrides({}, {"b": 2}) == {"b": 2}


def test_compose_profiles_empty():
    comp = compose_profiles([])
    assert comp.profile_ids == []
    assert comp.adrs == []
    assert comp.file_length_limit == 500


def test_compose_profiles_single_builtin():
    comp = compose_profiles(["core"])
    assert comp.profile_ids == ["core"]
    assert len(comp.adrs) == 5
    assert comp.file_length_limit == 500


def test_compose_profiles_base_alias():
    comp = compose_profiles(["base"])
    assert comp.profile_ids == ["core"]
    assert len(comp.adrs) == 5


def test_compose_profiles_inheritance_override():
    parent = Profile(
        id="parent",
        name="Parent Profile",
        description="",
        overrides={"architecture": {"file_length_limit": 450}, "quality": {"require_bdd": True}},
        slices=[SliceConfig(type="spike", name="Spike")],
        invariants=["Parent rule"],
    )
    child = Profile(
        id="child",
        name="Child Profile",
        description="",
        extends=["parent"],
        overrides={"architecture": {"file_length_limit": 300}, "quality": {"require_mutation_testing": True}},
        slices=[SliceConfig(type="audit", name="Audit")],
        invariants=["Child rule"],
        version="2.0.0",
    )

    def loader(pid: str) -> Profile:
        if pid == "parent":
            return parent
        if pid == "child":
            return child
        raise ProfileError(f"Unknown: {pid}")

    comp = compose_profiles([child], loader=loader)
    assert comp.profile_ids == ["parent", "child"]
    assert comp.file_length_limit == 300
    assert comp.overrides["architecture"]["file_length_limit"] == 300
    assert comp.overrides["quality"]["require_bdd"] is True
    assert comp.overrides["quality"]["require_mutation_testing"] is True
    assert len(comp.slices) == 2
    assert {s.type for s in comp.slices} == {"spike", "audit"}
    assert comp.invariants == ["Parent rule", "Child rule"]
    assert comp.version == "2.0.0"


def test_compose_profiles_invalid_file_limit_fallback():
    p = Profile(
        id="p_bad",
        name="Bad File Limit",
        description="",
        overrides={"architecture": {"file_length_limit": "not_an_int"}},
    )
    comp = compose_profiles([p], loader=lambda _: p)
    assert comp.file_length_limit == 500


def test_compose_profiles_adr_collision_error():
    p1 = Profile(
        id="prof_1",
        name="Profile 1",
        description="",
        adrs=[BaselineADR(number=4, slug="zero-trust", title="Zero Trust Sandboxing")],
    )
    p2 = Profile(
        id="prof_2",
        name="Profile 2",
        description="",
        adrs=[BaselineADR(number=4, slug="different-slug", title="Different Decision Title")],
    )

    with pytest.raises(ADRCollisionError) as exc_info:
        compose_profiles([p1, p2], loader=lambda p: p1 if p == "prof_1" else p2)

    msg = str(exc_info.value)
    assert "Profile Error: Conflict detected for ADR-0004 between 'prof_1' and 'prof_2'" in msg
    assert "Suggest next available number ADR-0005" in msg


def test_compose_profiles_adr_shared_slug_deduplication():
    # Same ADR inherited by two branches
    shared_adr = BaselineADR(number=1, slug="spec-as-code", title="Specification as Code")
    p1 = Profile(id="p1", name="P1", description="", adrs=[shared_adr])
    p2 = Profile(id="p2", name="P2", description="", adrs=[shared_adr])

    comp = compose_profiles([p1, p2], loader=lambda p: p1 if p == "p1" else p2)
    assert len(comp.adrs) == 1
    assert comp.adrs[0].canonical_id == "ADR-0001"


def test_circular_dependency_detection():
    p_a = Profile(id="a", name="A", description="", extends=["b"])
    p_b = Profile(id="b", name="B", description="", extends=["c"])
    p_c = Profile(id="c", name="C", description="", extends=["a"])

    registry = {"a": p_a, "b": p_b, "c": p_c}

    with pytest.raises(ProfileInheritanceError) as exc_info:
        resolve_inheritance_dag(p_a, loader=lambda pid: registry[pid])

    err = str(exc_info.value)
    assert "Profile Inheritance Error: Circular dependency detected (a -> b -> c -> a)" in err


def test_parse_adr_content_with_frontmatter():
    text = """---
id: '0015'
title: Automated Dependency Licensing
status: Accepted
date: 2026-09-29
---
# ADR-0015: Automated Dependency Licensing
"""
    adr = parse_adr_content(text, filename="adr-0015-licensing.md")
    assert adr.number == 15
    assert adr.slug == "licensing"
    assert adr.title == "Automated Dependency Licensing"
    assert adr.status == "Accepted"
    assert adr.date == "2026-09-29"


def test_parse_adr_content_without_frontmatter():
    text = """# ADR-0042: Custom Header Title

## Status
Accepted
"""
    adr = parse_adr_content(text, filename="adr-0042-custom-header.md")
    assert adr.number == 42
    assert adr.slug == "custom-header"
    assert adr.title == "Custom Header Title"


def test_parse_profile_toml():
    toml_str = """[profile]
id = "fintech"
name = "Fintech Org Profile"
version = "3.1.0"
description = "Financial compliance standards"
extends = ["core", "security"]

[overrides.architecture]
file_length_limit = 320

[invariants]
rules = ["Rule 1", "Rule 2"]

[[vertical_slices.slices]]
type = "audit"
name = "Audit Slices"
"""
    prof = parse_profile_toml(toml_str)
    assert prof.id == "fintech"
    assert prof.name == "Fintech Org Profile"
    assert prof.version == "3.1.0"
    assert prof.extends == ["core", "security"]
    assert prof.overrides["architecture"]["file_length_limit"] == 320
    assert prof.invariants == ["Rule 1", "Rule 2"]
    assert len(prof.slices) == 1
    assert prof.slices[0].type == "audit"


def test_load_profile_definition_file(tmp_path: Path):
    prof_dir = tmp_path / "custom_p"
    prof_dir.mkdir()
    (prof_dir / "profile.toml").write_text(
        """[profile]
id = "custom_p"
name = "Custom P"
version = "1.0.0"
extends = []
""",
        encoding="utf-8",
    )
    p = load_profile_definition(prof_dir)
    assert p.id == "custom_p"
    assert p.name == "Custom P"


def test_load_profile_definition_not_found():
    with pytest.raises(ProfileError) as exc_info:
        load_profile_definition("non_existent_profile_12345")
    assert "Unknown profile" in str(exc_info.value)
