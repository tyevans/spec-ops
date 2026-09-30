"""Hypothesis generative property tests for schema validation and migration (ADR-0009)."""

from __future__ import annotations

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.migration import migrate_document_content, parse_frontmatter_and_body
from spec_ops.core.schema_validator import validate_frontmatter_dict

# Strategy for realistic Markdown body segments
st_heading = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r"),
    min_size=1,
    max_size=50,
).map(lambda t: f"# {t.strip() or 'Heading'}\n\n")

st_paragraph = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r"),
    min_size=1,
    max_size=200,
).map(lambda t: f"{t.strip() or 'Paragraph text.'}\n\n")

st_code_block = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="`\r"),
    min_size=0,
    max_size=100,
).map(lambda t: f"```python\ndef generated_code():\n    return '{t[:30]}'\n```\n\n")

st_table = st.text(min_size=1, max_size=20).map(
    lambda t: f"| Column 1 | Column 2 |\n|---|---|\n| {t[:10]} | Val |\n\n"
)

st_comment = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="-\r>"),
    min_size=1,
    max_size=50,
).map(lambda t: f"<!-- Marker: {t.strip()} -->\n\n")

st_body = st.lists(
    st.one_of(st_heading, st_paragraph, st_code_block, st_table, st_comment),
    min_size=1,
    max_size=10,
).map(lambda parts: "".join(parts))

# Strategy for task metadata with potential legacy fields
st_legacy_task_meta = st.fixed_dictionaries(
    {
        "id": st.integers(min_value=1, max_value=9999).map(lambda i: str(i).zfill(4)),
        "title": st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r"), min_size=1, max_size=50).map(lambda t: t.strip() or "Task Title"),
        "status": st.sampled_from(["Proposed", "Refined", "Complete", "In-Progress"]),
        "target_bc": st.sampled_from(["core", "backlog", "prd", "worker", "visualizer"]),
    },
    optional={
        "governing_adr": st.one_of(
            st.integers(min_value=1, max_value=99),
            st.text(min_size=1, max_size=8).map(lambda s: f"ADR-{s}"),
        ),
        "governing_prd": st.integers(min_value=1, max_value=99).map(lambda i: str(i).zfill(4)),
        "story": st.integers(min_value=1, max_value=99).map(lambda i: str(i).zfill(4)),
        "dependency": st.integers(min_value=1, max_value=99).map(lambda i: f"TASK-{str(i).zfill(4)}"),
    },
)


@settings(max_examples=100)
@given(meta=st_legacy_task_meta, body=st_body)
def test_hypothesis_body_preservation_and_idempotence(meta: dict, body: str):
    """Generative property invariant (ADR-0009):

    For any valid Markdown specification, migrate(parse(spec)) preserves 100%
    of non-frontmatter body tokens verbatim (idempotent body preservation invariant).
    """
    yaml_header = yaml.dump(meta, sort_keys=False, default_flow_style=False)
    original_document = f"---\n{yaml_header}---\n{body}"

    # First migration pass
    migrated_doc, was_modified = migrate_document_content(original_document, doc_type="task")

    # Invariant 1: Non-frontmatter body is preserved byte-for-byte verbatim
    _, _, extracted_body = parse_frontmatter_and_body(migrated_doc)
    assert extracted_body == body, "Migrated body does not match original body byte-for-byte."

    # Invariant 2: Migration is strictly idempotent
    second_pass_doc, second_was_modified = migrate_document_content(migrated_doc, doc_type="task")
    assert not second_was_modified, "Second migration pass modified already migrated content."
    assert second_pass_doc == migrated_doc, "Second migration pass altered document content."

    # Invariant 3: Migrated frontmatter passes schema v2.0 validation
    migrated_meta, _, _ = parse_frontmatter_and_body(migrated_doc)
    errors = validate_frontmatter_dict(migrated_meta, doc_type="task")
    assert len(errors) == 0, f"Migrated metadata failed schema v2.0 validation: {[str(e) for e in errors]}"


@settings(max_examples=50)
@given(meta=st_legacy_task_meta, body=st_body)
def test_hypothesis_crlf_preservation(meta: dict, body: str):
    """Property test verifying CRLF line-ending preservation."""
    crlf_body = body.replace("\n", "\r\n")
    yaml_header = yaml.dump(meta, sort_keys=False, default_flow_style=False).replace("\n", "\r\n")
    original_crlf_doc = f"---\r\n{yaml_header}---\r\n{crlf_body}"

    migrated_doc, _ = migrate_document_content(original_crlf_doc, doc_type="task")
    _, _, extracted_body = parse_frontmatter_and_body(migrated_doc)
    assert extracted_body == crlf_body, "CRLF body not preserved byte-for-byte."
