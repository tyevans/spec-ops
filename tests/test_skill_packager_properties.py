"""Generative property invariant tests for universal skill packager.

Target bounded context: scaffold. Governed by ADR-0001, ADR-0003, ADR-0009.
Source file strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

import posixpath
from hypothesis import given, strategies as st
import pytest

from spec_ops.scaffold.skill_packager import (
    SUPPORTED_SKILL_TARGETS,
    generate_skill_bundle,
    validate_bundle_links,
)


@given(target=st.sampled_from(list(SUPPORTED_SKILL_TARGETS)))
def test_property_skill_bundle_has_zero_broken_links(target: str):
    """Property Invariant: All generated skill bundles must be self-consistent with 0 broken links."""
    bundle = generate_skill_bundle(target=target, project_name="HypothesisProject")
    assert len(bundle) > 0

    # Links must validate cleanly
    broken = validate_bundle_links(bundle)
    assert broken == [], f"Target '{target}' generated broken links: {broken}"

    # Paths must be normalized POSIX relative paths
    for rel_path, content in bundle.items():
        assert not rel_path.startswith("/")
        assert not rel_path.startswith("\\")
        assert ".." not in rel_path
        assert posixpath.normpath(rel_path) == rel_path
        assert len(content.strip()) > 0


@given(
    target=st.sampled_from(["antigravity", "claude", "cursor"]),
    bad_slug=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))),
)
def test_property_injected_broken_link_is_always_detected(target: str, bad_slug: str):
    """Property Invariant: Injecting an unresolvable relative link must always be flagged as a broken link."""
    bundle = generate_skill_bundle(target=target)
    # Pick the primary skill/rule markdown file
    candidate_key = next(k for k in bundle.keys() if k.endswith(".md") or k.endswith(".mdc"))
    fake_target = f"./references/nonexistent_{bad_slug}.md"
    injected_bundle = dict(bundle)
    injected_bundle[candidate_key] = bundle[candidate_key] + f"\n\n[Broken Link]({fake_target})\n"

    broken = validate_bundle_links(injected_bundle)
    assert len(broken) >= 1
    assert any(fake_target.split("/")[-1] in msg for msg in broken)


@given(
    target=st.sampled_from(["antigravity", "claude", "cursor"]),
    slug=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Nd"))),
)
def test_property_external_urls_and_anchors_never_flagged_broken(target: str, slug: str):
    """Property Invariant: Valid external URLs, mailto, and anchors must never cause false positive link errors."""
    bundle = generate_skill_bundle(target=target)
    candidate_key = next(k for k in bundle.keys() if k.endswith(".md") or k.endswith(".mdc"))
    safe_links = (
        f"\n\n- [Web](https://spec-ops.dev/{slug})\n"
        f"- [Anchor](#{slug})\n"
        f"- [Mail](mailto:dev@{slug}.org)\n"
    )
    injected_bundle = dict(bundle)
    injected_bundle[candidate_key] = bundle[candidate_key] + safe_links

    broken = validate_bundle_links(injected_bundle)
    assert broken == []


@given(target=st.sampled_from(list(SUPPORTED_SKILL_TARGETS)))
def test_property_bundle_generation_is_deterministic(target: str):
    """Property Invariant: Bundle generation is idempotent and deterministic across repeated runs."""
    bundle_a = generate_skill_bundle(target=target, project_name="DeterminismTest")
    bundle_b = generate_skill_bundle(target=target, project_name="DeterminismTest")

    assert set(bundle_a.keys()) == set(bundle_b.keys())
    for k in bundle_a:
        assert bundle_a[k] == bundle_b[k]
