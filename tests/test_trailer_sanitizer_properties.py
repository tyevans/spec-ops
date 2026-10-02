"""Hypothesis property tests for RFC-822 trailer parsing and sanitization.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0014, ADR-0016; PRD-0002; TASK-0168.
"""

from __future__ import annotations

from hypothesis import given, settings
import hypothesis.strategies as st

from spec_ops.security.trailer_sanitizer import parse_rfc822_trailers


# Valid RFC-822 header keys: alphanumeric with hyphens or underscores, starting with letter
header_key_strategy = st.from_regex(r"^[A-Za-z][A-Za-z0-9_-]{0,25}$", fullmatch=True)

# Valid single-line trailer values (no newlines)
header_val_strategy = st.text(
    alphabet=st.characters(whitelist_categories=["Lu", "Ll", "Nd", "Zs", "Po"]),
    min_size=1,
    max_size=60,
).filter(lambda s: "\n" not in s and "\r" not in s and bool(s.strip()))


@settings(max_examples=100, deadline=None)
@given(
    trailers=st.dictionaries(
        keys=header_key_strategy,
        values=header_val_strategy,
        min_size=1,
        max_size=10,
    )
)
def test_rfc822_trailer_parsing_preserves_all_keys_and_values(
    trailers: dict[str, str]
):
    """Asserts that any well-formed RFC-822 trailer block is parsed without truncation or key loss."""
    # Build commit message with trailer block
    trailer_lines = [f"{k}: {v.strip()}" for k, v in trailers.items()]
    message = "feat(core): example subject line\n\nDetailed commit body.\n\n" + "\n".join(trailer_lines) + "\n"

    parsed = parse_rfc822_trailers(message)

    # Invariant 1: All generated keys are present in parsed mapping
    assert len(parsed) == len(trailers)

    # Invariant 2: Values match stripped expected values exactly without loss
    for k, v in trailers.items():
        assert k in parsed
        assert parsed[k] == v.strip()
