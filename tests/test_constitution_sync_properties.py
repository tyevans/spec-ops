"""Property-based generative tests for living constitution synchronization (ADR-0009)."""

from __future__ import annotations

from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from spec_ops.scaffold.constitution_sync import (
    BEGIN_CUSTOM_INVARIANTS,
    END_CUSTOM_INVARIANTS,
    check_constitution,
    extract_custom_invariants,
    inject_custom_invariants,
    sync_constitution,
    wrap_custom_invariants,
)
from spec_ops.scaffold.init import init_project


@given(custom_text=st.text(alphabet=st.characters(blacklist_categories=("Cs",))))
@settings(max_examples=100)
def test_property_boundary_parsing_and_wrapping_roundtrip(custom_text: str):
    """Property Invariant: Wrapping and extraction preserves arbitrary custom text verbatim."""
    assume(END_CUSTOM_INVARIANTS not in custom_text)
    wrapped = wrap_custom_invariants(custom_text)
    extracted = extract_custom_invariants(wrapped)
    assert extracted == custom_text


@given(
    prefix=st.text(max_size=200),
    custom_text=st.text(max_size=200),
    suffix=st.text(max_size=200),
)
@settings(max_examples=50)
def test_property_inject_custom_invariants_preserves_content(
    prefix: str,
    custom_text: str,
    suffix: str,
):
    """Property Invariant: Injection into arbitrary markdown preserves surrounding context and custom text."""
    assume(BEGIN_CUSTOM_INVARIANTS not in prefix and END_CUSTOM_INVARIANTS not in prefix)
    assume(BEGIN_CUSTOM_INVARIANTS not in suffix and END_CUSTOM_INVARIANTS not in suffix)
    assume(BEGIN_CUSTOM_INVARIANTS not in custom_text and END_CUSTOM_INVARIANTS not in custom_text)

    # When delimiters are already present in document
    initial_doc = f"{prefix}\n{BEGIN_CUSTOM_INVARIANTS}old text{END_CUSTOM_INVARIANTS}\n{suffix}"
    injected = inject_custom_invariants(initial_doc, custom_text)
    assert extract_custom_invariants(injected) == custom_text
    assert prefix in injected
    assert suffix in injected


@given(
    custom_text=st.text(min_size=1, max_size=500),
    passes=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=25)
def test_property_arbitrary_custom_invariants_preserved_across_sync_passes(
    tmp_path_factory,
    custom_text: str,
    passes: int,
):
    """Generative property test asserting arbitrary text within custom invariant delimiters

    is preserved verbatim across repeated constitution synchronization passes (ADR-0009).
    """
    assume(END_CUSTOM_INVARIANTS not in custom_text)
    assume(BEGIN_CUSTOM_INVARIANTS not in custom_text)
    assume("\r" not in custom_text)

    repo_dir = tmp_path_factory.mktemp("prop_repo")
    init_project(name="PropConstitutionApp", target_dir=repo_dir)

    agents_path = repo_dir / "AGENTS.md"
    content = agents_path.read_text(encoding="utf-8")
    content = inject_custom_invariants(content, custom_text)
    agents_path.write_text(content, encoding="utf-8")

    # Execute repeated synchronization passes
    for _ in range(passes):
        ok, msg = sync_constitution(repo_dir)
        assert ok is True
        current_content = agents_path.read_text(encoding="utf-8")
        extracted = extract_custom_invariants(current_content)
        assert extracted == custom_text

        # docs/operating-manual.md should also reflect the preserved custom invariants
        manual_path = repo_dir / "docs" / "operating-manual.md"
        assert manual_path.is_file()
        manual_extracted = extract_custom_invariants(manual_path.read_text(encoding="utf-8"))
        assert manual_extracted == custom_text

        # Constitution check must report in-sync
        in_sync, diff, _ = check_constitution(repo_dir)
        assert in_sync is True
        assert diff == ""
