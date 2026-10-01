"""Hypothesis generative property tests for persona parsing, serialization, and discovery (ADR-0009)."""

from __future__ import annotations

from pathlib import Path
import string

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from spec_ops.core.persona_models import (
    EmergingArchetype,
    PersonaDocument,
    PersonaProfile,
)
from spec_ops.core.persona_engine import PersonaEngine

SAFE_CHARS = string.ascii_letters + " "
SAFE_SLUG = string.ascii_letters + string.digits + "_-"


@st.composite
def persona_profiles(draw) -> PersonaProfile:
    name = draw(st.text(alphabet=string.ascii_letters, min_size=2, max_size=15)).title()
    role = draw(st.text(alphabet=SAFE_CHARS, min_size=3, max_size=30)).strip()
    role_desc = draw(st.text(alphabet=SAFE_CHARS, min_size=5, max_size=50)).strip()

    num_pain = draw(st.integers(min_value=1, max_value=3))
    pain_points = [
        draw(st.text(alphabet=SAFE_CHARS, min_size=3, max_size=30)).strip()
        for _ in range(num_pain)
    ]
    # Filter out empty strings
    pain_points = [p for p in pain_points if p] or ["Default pain point"]

    num_goals = draw(st.integers(min_value=1, max_value=3))
    goals = [
        draw(st.text(alphabet=SAFE_CHARS, min_size=3, max_size=30)).strip()
        for _ in range(num_goals)
    ]
    goals = [g for g in goals if g] or ["Default goal"]

    has_custom = draw(st.booleans())
    custom_notes = (
        ["- **Special Requirement**: Enforce deterministic validation."]
        if has_custom
        else []
    )

    return PersonaProfile(
        name=name,
        role=role,
        role_description=role_desc,
        pain_points=pain_points,
        goals=goals,
        goals_label="Goals with SpecOps",
        custom_notes=custom_notes,
    )


@st.composite
def persona_documents(draw) -> PersonaDocument:
    has_fm = draw(st.booleans())
    frontmatter = {"version": "2.0", "status": "living"} if has_fm else {}
    preamble = draw(
        st.sampled_from(
            [
                "# SpecOps User Personas\n\nCore archetypes for autonomous project execution.",
                "# System Personas\n\nStakeholders and autonomous agents.",
            ]
        )
    )
    profiles = draw(st.lists(persona_profiles(), min_size=1, max_size=5))
    return PersonaDocument(
        frontmatter=frontmatter,
        preamble=preamble,
        personas=profiles,
    )


@settings(max_examples=50)
@given(doc=persona_documents())
def test_persona_document_parsing_serialization_idempotence(doc: PersonaDocument):
    """Asserts that serialize -> parse -> serialize is strictly idempotent."""
    s1 = doc.serialize()
    parsed1 = PersonaDocument.parse(s1)
    s2 = parsed1.serialize()

    assert s1 == s2, "Serialization of parsed document did not match original serialization"

    parsed2 = PersonaDocument.parse(s2)
    assert len(parsed1.personas) == len(parsed2.personas)
    for p1, p2 in zip(parsed1.personas, parsed2.personas):
        assert p1.name == p2.name
        assert p1.role == p2.role
        assert p1.role_description == p2.role_description
        assert p1.pain_points == p2.pain_points
        assert p1.goals == p2.goals


def test_repo_personas_md_idempotence():
    """Asserts that the actual repository PERSONAS.md parses and serializes identically."""
    repo_personas = Path("docs/project/user_stories/PERSONAS.md")
    if not repo_personas.is_file():
        pytest.skip("docs/project/user_stories/PERSONAS.md not found")

    content = repo_personas.read_text(encoding="utf-8")
    doc = PersonaDocument.parse(content)
    assert len(doc.personas) == 6
    expected_names = ["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha"]
    assert [p.name for p in doc.personas] == expected_names

    serialized = doc.serialize()
    assert content.strip() == serialized.strip()

    reparsed = PersonaDocument.parse(serialized)
    assert reparsed.serialize().strip() == serialized.strip()


@settings(max_examples=50)
@given(
    names=st.lists(
        st.text(alphabet=string.ascii_letters, min_size=2, max_size=10),
        min_size=1,
        max_size=3,
    )
)
def test_persona_mention_extraction_invariance(names: list[str]):
    """Asserts that compound persona strings correctly extract all constituent archetypes."""
    cleaned_names = [n.title() for n in names if n.strip()]
    if not cleaned_names:
        return

    # Build compound mention e.g. "Alex (The Architect) & Jordan (The Lead)"
    compound = " & ".join(f"{name} (The Role)" for name in cleaned_names)
    mentions = PersonaEngine.extract_persona_mentions(compound)

    extracted_names = [m[0] for m in mentions]
    for name in cleaned_names:
        assert name in extracted_names
