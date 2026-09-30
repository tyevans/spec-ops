"""Hypothesis property-based tests for Conventional Commit and RFC-822 git trailer invariants."""

from __future__ import annotations

import re
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.worker.commits import (
    VALID_CONVENTIONAL_TYPES,
    build_commit_subject,
    build_commit_trailers,
    derive_conventional_type,
    format_task_commit_message,
    parse_commit_trailers,
)

CONVENTIONAL_SUBJECT_PATTERN = re.compile(
    r"^(feat|refactor|spike|fix|chore|docs|test|perf|style|ci)\([a-z0-9_-]+\):\s*.+$"
)

RFC822_TRAILER_LINE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*:\s*.+$"
)

valid_slice_strategy = st.sampled_from([
    "feat", "refactor", "spike", "fix", "chore", "docs", "test",
    "feature", "refactoring", "bug", "bugfix", "spike_task", "",
])

task_dict_strategy = st.fixed_dictionaries(
    {
        "id": st.text(alphabet="0123456789", min_size=1, max_size=6),
        "title": st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="\n\r\t"), min_size=1, max_size=80),
    },
    optional={
        "slice_type": valid_slice_strategy,
        "slice": valid_slice_strategy,
        "type": valid_slice_strategy,
        "governing_prds": st.lists(st.text(alphabet="0123456789", min_size=1, max_size=4).map(lambda s: f"PRD-{s}"), max_size=3),
        "governing_adrs": st.lists(st.text(alphabet="0123456789", min_size=1, max_size=4).map(lambda s: f"ADR-{s}"), max_size=3),
        "signed_off_by": st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=30),
    },
)


@given(task_dict=task_dict_strategy)
def test_property_conventional_commit_subject_conformance(task_dict: dict[str, Any]):
    """Invariant: Every generated commit subject strictly adheres to Conventional Commits 1.0 format."""
    subject = build_commit_subject(task_dict)
    assert bool(CONVENTIONAL_SUBJECT_PATTERN.match(subject)), f"Subject '{subject}' violates Conventional Commits 1.0 format"

    c_type = derive_conventional_type(task_dict)
    assert subject.startswith(f"{c_type}("), f"Subject '{subject}' does not start with derived type '{c_type}'"


@given(task_dict=task_dict_strategy, body=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=200))
def test_property_rfc822_trailer_formatting_and_parsing_roundtrip(task_dict: dict[str, Any], body: str):
    """Invariant: Generated commit bodies embed valid RFC-822 trailers that roundtrip cleanly through parser."""
    msg = format_task_commit_message(task_dict, body=body)
    trailers = parse_commit_trailers(msg)

    assert "SpecOps-Task" in trailers
    assert bool(re.match(r"^(TASK|SPIKE)-\d{4,}$", trailers["SpecOps-Task"])), f"Invalid SpecOps-Task: {trailers['SpecOps-Task']}"

    assert "SpecOps-Slice" in trailers
    assert trailers["SpecOps-Slice"] in VALID_CONVENTIONAL_TYPES

    assert "Provenance" in trailers
    assert trailers["Provenance"] == "spec-ops-worker (autonomous)"

    # Verify each trailer line conforms to RFC-822
    for line in msg.strip().splitlines():
        if ":" in line and not line.startswith("feat(") and not line.startswith("spike(") and not line.startswith("refactor(") and not line.startswith("fix("):
            if any(line.startswith(k) for k in ("SpecOps-", "Provenance:")):
                assert bool(RFC822_TRAILER_LINE_PATTERN.match(line)), f"Trailer line '{line}' violates RFC-822 syntax"
