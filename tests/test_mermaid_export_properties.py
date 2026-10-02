"""Generative property tests for Mermaid diagram generator.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0011, ADR-0015.
"""

from datetime import datetime, timezone
import re
from uuid import UUID
from hypothesis import given, settings, strategies as st
from redstring import Entity, ExtractionMethod, Provenance, Relationship

from spec_ops.graph.mermaid_export import generate_dot, generate_mermaid, sanitize_label, sanitize_node_id

safe_text = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=1, max_size=40)
safe_name = st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=48), min_size=1, max_size=30)
entity_types = st.sampled_from(["PRD", "UserStory", "Task", "ADR", "Persona", "Outcome", "PainPoint"])
rel_types = st.sampled_from(["implements", "depends_on", "governed_by", "specifies", "satisfies", "desires"])


@st.composite
def arbitrary_graph_strategy(draw: st.DrawFn) -> tuple[list[Entity], list[Relationship]]:
    num_nodes = draw(st.integers(min_value=2, max_value=10))
    entities: list[Entity] = []
    for i in range(num_nodes):
        name = draw(safe_name)
        etype = draw(entity_types)
        title = draw(safe_text)
        ent = Entity(
            id=UUID(int=1000 + i),
            tenant_id=UUID(int=0),
            name=name,
            normalized_name=name.lower(),
            entity_type=etype,
            description=title,
            properties={"title": title},
            provenance=Provenance(
                source_id="test",
                extraction_method=ExtractionMethod.PATTERN,
                confidence=1.0,
                observed_at=datetime.now(timezone.utc),
            ),
        )
        entities.append(ent)

    num_edges = draw(st.integers(min_value=0, max_value=15))
    relationships: list[Relationship] = []
    for j in range(num_edges):
        src = draw(st.sampled_from(entities))
        tgt = draw(st.sampled_from([e for e in entities if e.id != src.id]))
        rtype = draw(rel_types)
        rel = Relationship(
            id=UUID(int=5000 + j),
            tenant_id=UUID(int=0),
            source_entity_id=src.id,
            target_entity_id=tgt.id,
            relationship_type=rtype,
            confidence=1.0,
            source_id="test",
        )
        relationships.append(rel)

    return entities, relationships


@settings(max_examples=40, deadline=None)
@given(graph=arbitrary_graph_strategy(), direction=st.sampled_from(["TD", "LR", "TB", "RL"]))
def test_mermaid_syntax_bracket_safety_and_node_ids(graph: tuple[list[Entity], list[Relationship]], direction: str) -> None:
    entities, relationships = graph
    output = generate_mermaid(entities, relationships, direction=direction)

    assert output.startswith(f"flowchart {direction}")

    # Invariant 1: Node declaration IDs must contain strictly valid identifier characters
    for line in output.splitlines():
        line_clean = line.strip()
        if '["' in line_clean:
            match = re.match(r"^([a-zA-Z0-9_]+)\[", line_clean)
            assert match is not None, f"Invalid node identifier in line: {line_clean}"

            # Invariant 2: Inside label quotes, unescaped brackets '[' or ']' are forbidden
            label_match = re.search(r'\["(.*)"\]', line_clean)
            if label_match:
                inner_label = label_match.group(1)
                assert "[" not in inner_label, f"Unescaped '[' in label: {inner_label}"
                assert "]" not in inner_label, f"Unescaped ']' in label: {inner_label}"


@settings(max_examples=30, deadline=None)
@given(graph=arbitrary_graph_strategy(), direction=st.sampled_from(["TD", "LR"]))
def test_dot_syntax_validity(graph: tuple[list[Entity], list[Relationship]], direction: str) -> None:
    entities, relationships = graph
    output = generate_dot(entities, relationships, direction=direction)

    assert output.startswith("digraph G {\n")
    assert output.strip().endswith("}")
    assert f'rankdir="{direction}";' in output
