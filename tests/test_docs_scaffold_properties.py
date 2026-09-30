"""Generative property tests for Bounded-Context Diataxis Documentation Scaffolding (ADR-0009)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.scaffold.docs_scaffold import (
    DocumentationExistsError,
    InvalidBoundedContextError,
    check_docs_exist,
    get_quadrant_paths,
    get_visualizer_deep_link,
    normalize_title,
    scaffold_bc_docs,
    validate_bc_name,
)

VALID_BC_STRATEGY = st.from_regex(r"^[a-zA-Z0-9_-]{1,40}$", fullmatch=True).filter(
    lambda s: not s.startswith(".") and ".." not in s
)


@given(bc=VALID_BC_STRATEGY)
@settings(max_examples=100)
def test_valid_bc_paths_conform_to_diataxis_invariants(tmp_path: Path, bc: str):
    """Asserts that valid bounded context identifiers strictly conform to Diataxis directory invariants."""
    clean_bc = validate_bc_name(bc)
    assert clean_bc == bc.strip().lower()
    assert "/" not in clean_bc
    assert "\\" not in clean_bc
    assert ".." not in clean_bc

    quad_paths = get_quadrant_paths(tmp_path, bc)
    expected_quads = ["tutorials", "how-to", "reference", "explanation"]
    assert set(quad_paths.keys()) == set(expected_quads)

    docs_root = (tmp_path / "docs").resolve()
    for quad_name, p in quad_paths.items():
        assert p.resolve().is_relative_to(docs_root), f"Path {p} escaped docs root {docs_root}"
        assert p.parent.name == quad_name
        assert p.name == clean_bc

    deep_link = get_visualizer_deep_link(bc)
    assert f"focus={clean_bc}" in deep_link
    assert f"#tab=canvas&focus={clean_bc}" in deep_link


@given(
    bad_bc=st.one_of(
        st.text().filter(
            lambda s: bool(
                re.search(r"[/\\..\x00]", s) or not re.match(r"^[a-zA-Z0-9_-]+$", s.strip(" \t\r\n"))
            )
        ),
        st.sampled_from(["", "   ", "\t", "\n", "../etc", "/billing", "billing/sub", "billing\\sub", "a" * 0]),
    )
)
@settings(max_examples=100)
def test_path_traversal_and_invalid_bc_rejected(tmp_path: Path, bad_bc: str):
    """Asserts that any identifier with path traversal or invalid characters is rejected."""
    with pytest.raises((InvalidBoundedContextError, ValueError)):
        validate_bc_name(bad_bc)

    with pytest.raises((InvalidBoundedContextError, ValueError)):
        get_quadrant_paths(tmp_path, bad_bc)

    with pytest.raises((InvalidBoundedContextError, ValueError)):
        get_visualizer_deep_link(bad_bc)


@given(bc=VALID_BC_STRATEGY, custom_title=st.one_of(st.none(), st.text(min_size=1, max_size=50)))
@settings(max_examples=30)
def test_scaffolding_lifecycle_and_conflict_safety(tmp_path_factory, bc: str, custom_title: str | None):
    """Asserts that scaffolding produces valid Diataxis trees and guards against accidental overwrites."""
    tmp_path = tmp_path_factory.mktemp("scaffold_test")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")

    title = normalize_title(bc, custom_title)
    assert len(title) > 0

    assert not check_docs_exist(tmp_path, bc)
    created = scaffold_bc_docs(tmp_path, bc=bc, title=custom_title, force=False)
    assert len(created) >= 5
    assert check_docs_exist(tmp_path, bc)

    # Attempting to re-scaffold without force must raise DocumentationExistsError
    with pytest.raises(DocumentationExistsError):
        scaffold_bc_docs(tmp_path, bc=bc, title=custom_title, force=False)

    # Scaffolding with force=True succeeds
    recreated = scaffold_bc_docs(tmp_path, bc=bc, title=custom_title, force=True)
    assert len(recreated) >= 5
