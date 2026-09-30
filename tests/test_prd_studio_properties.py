"""Generative Hypothesis property tests for PRD Studio serialization and backdoor invariants (ADR-0009)."""

from __future__ import annotations

import re
import string
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from spec_ops.prd.step_assistant import BACKDOOR_PATTERNS, detect_backdoors
from spec_ops.prd.studio import (
    KNOWN_PERSONAS,
    parse_prd_document,
    serialize_prd_document,
    validate_prd_schema,
)

# Text strategies for Markdown body: include multiline strings, code blocks, lists, newlines
markdown_lines = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=100,
)

markdown_bodies = st.lists(markdown_lines, min_size=0, max_size=15).map(lambda lines: "\n".join(lines))

# Safe string strategies for YAML frontmatter values (avoid YAML control ambiguities)
safe_text = st.text(
    alphabet=string.ascii_letters + string.digits + " _-.",
    min_size=1,
    max_size=50,
)

frontmatter_strategy = st.fixed_dictionaries({
    "id": st.from_regex(r"PRD-[0-9]{4}", fullmatch=True),
    "title": safe_text,
    "status": st.sampled_from(["Idea", "Accepted", "Shipped"]),
    "target_persona": st.sampled_from(list(KNOWN_PERSONAS)),
    "component": safe_text,
})


@settings(max_examples=100)
@given(frontmatter=frontmatter_strategy, body=markdown_bodies)
def test_yaml_markdown_roundtrip_invariant(frontmatter: dict[str, Any], body: str):
    """Property Invariant (ADR-0009):
    YAML serialization and deserialization functions produce bit-exact roundtrips
    without corrupting multiline markdown strings or stripping frontmatter delimiters.
    """
    serialized = serialize_prd_document(frontmatter, body)

    # Invariant 1: Delimiters must exist at start and end of frontmatter
    assert serialized.startswith("---\n"), "Frontmatter must open with '---'"
    assert "\n---\n" in serialized, "Frontmatter must close with '---'"

    parsed_fm, parsed_body = parse_prd_document(serialized)

    # Invariant 2: Frontmatter keys and values are bit-exact
    for key, val in frontmatter.items():
        assert key in parsed_fm, f"Missing key {key} after roundtrip"
        assert parsed_fm[key] == val, f"Value mismatch for {key}: expected {val}, got {parsed_fm[key]}"

    # Invariant 3: Multiline body is preserved without corruption
    assert parsed_body == body, "Markdown body was corrupted during roundtrip"


@settings(max_examples=100)
@given(
    step_prefix=st.sampled_from(["Given", "When", "Then"]),
    action_text=st.text(alphabet=string.ascii_letters + " ", min_size=3, max_size=40),
)
def test_clean_frontdoor_never_flagged_as_backdoor(step_prefix: str, action_text: str):
    """Property Invariant: Standard public actions without backdoor keywords are never falsely flagged."""
    clean_action = "".join(c for c in action_text if c.isalnum() or c == " ").strip()
    if not clean_action:
        return
    full_step = f"{step_prefix} {clean_action}"
    lower = full_step.lower()
    if any(re.search(pat, lower) for pat, _ in BACKDOOR_PATTERNS):
        return

    is_bd, warn, _ = detect_backdoors(full_step)
    assert is_bd is False, f"False positive backdoor detection for step: '{full_step}'"
    assert warn == ""


@settings(max_examples=50)
@given(
    backdoor_keyword=st.sampled_from([
        "database table users",
        "has record 'admin'",
        "mocked API service",
        "direct state manipulation",
        "insert into accounts",
        "select * from orders",
        "internal state of worker",
        "private attribute _secret",
    ]),
    prefix=st.sampled_from(["Given", "When", "Then"]),
)
def test_backdoor_keywords_always_flagged(backdoor_keyword: str, prefix: str):
    """Property Invariant: Steps containing known backdoor patterns are reliably detected."""
    step = f"{prefix} {backdoor_keyword}"
    is_bd, warn, alt = detect_backdoors(step)
    assert is_bd is True, f"Failed to detect backdoor in: '{step}'"
    assert "Backdoor violation (ADR-0003)" in warn
    assert len(alt) > 0
