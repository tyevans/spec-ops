"""Hypothesis generative property tests for anti-loop failure memory schema (ADR-0009)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings, strategies as st

from spec_ops.rescue.memory import (
    FailureHistoryEntry,
    append_failure_record,
    benchmark_frontmatter_update,
    extract_failed_invariants,
    parse_task_memory,
    serialize_task_with_memory,
    synthesize_negative_constraints,
)

# Text strategies for valid PMaC markdown fields
safe_text_chars = st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), blacklist_characters=("\r", "\n", "\0"))
safe_text = st.text(alphabet=safe_text_chars, min_size=1, max_size=50).filter(lambda s: bool(s.strip()))
markdown_body_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r"),
    min_size=0,
    max_size=500,
)


@given(
    task_id=st.integers(min_value=1, max_value=9999).map(lambda n: f"{n:04d}"),
    title=safe_text,
    status=st.sampled_from(["Refined", "Proposed", "Complete", "Active", "In-Progress"]),
    dependencies=st.lists(st.integers(min_value=1, max_value=9999).map(lambda n: f"TASK-{n:04d}"), max_size=5),
    body=markdown_body_strategy,
)
def test_lossless_round_trip_property(
    task_id: str,
    title: str,
    status: str,
    dependencies: list[str],
    body: str,
):
    """Property: Frontmatter serialization and deserialization is perfectly round-trippable.

    Markdown body remains byte-identical.
    """
    initial_meta: dict[str, Any] = {
        "id": task_id,
        "title": title,
        "status": status,
        "dependencies": dependencies,
    }

    serialized = serialize_task_with_memory(initial_meta, body)
    parsed_meta, parsed_body, parsed_history = parse_task_memory(serialized)

    assert parsed_body == body, "Markdown body must remain 100% byte-identical"
    assert parsed_meta.get("id") == task_id or parsed_meta.get("id") == int(task_id)
    assert parsed_meta.get("title") == title
    assert parsed_meta.get("status") == status
    assert parsed_meta.get("dependencies", []) == dependencies
    assert parsed_history == []


@given(
    title=safe_text,
    initial_body=markdown_body_strategy,
    iterations=st.lists(
        st.fixed_dictionaries({
            "reason": safe_text,
            "invariants": st.lists(st.sampled_from(["ADR-0002", "ADR-0003", "ADR-0005", "ADR-0009"]), max_size=3),
            "date": st.sampled_from(["2026-09-28", "2026-09-29", "2026-09-30"]),
        }),
        min_size=1,
        max_size=6,
    ),
)
@settings(max_examples=40)
def test_monotonic_failure_history_append_property(
    tmp_path_factory: pytest.TempPathFactory,
    title: str,
    initial_body: str,
    iterations: list[dict[str, Any]],
):
    """Property: Across repeated reset iterations, failure_history appends monotonically

    without data corruption, and the markdown body remains byte-identical.
    """
    tmp_dir = tmp_path_factory.mktemp("prop_mem")
    task_file = tmp_dir / "0042-prop-task.md"

    initial_meta = {
        "id": "0042",
        "title": title,
        "status": "Refined",
        "dependencies": ["TASK-0001"],
    }
    task_file.write_text(serialize_task_with_memory(initial_meta, initial_body), encoding="utf-8")

    for idx, step in enumerate(iterations, start=1):
        append_failure_record(
            task_file,
            reason=step["reason"],
            failed_invariants=step["invariants"],
            attempt_date=step["date"],
        )

        content = task_file.read_text(encoding="utf-8")
        meta, body, history = parse_task_memory(content)

        assert body == initial_body, f"Body mutated on iteration {idx}"
        assert meta["title"] == title
        assert meta["dependencies"] == ["TASK-0001"]
        assert len(history) == idx, f"Expected {idx} history entries, found {len(history)}"

        # Validate entry integrity
        curr = history[-1]
        assert curr["reason"] == step["reason"].strip()
        assert curr["failed_invariants"] == step["invariants"]
        assert curr["attempt_date"] == step["date"]


@given(
    noise_prefix=safe_text,
    adrs=st.lists(st.integers(min_value=1, max_value=25).map(lambda n: f"ADR-{n:04d}"), min_size=1, max_size=4),
    noise_suffix=safe_text,
)
def test_invariant_extraction_property(noise_prefix: str, adrs: list[str], noise_suffix: str):
    """Property: Invariant extraction finds all ADR identifiers case-insensitively."""
    combined = f"{noise_prefix} " + " and ".join(adrs) + f" {noise_suffix}"
    extracted = extract_failed_invariants(combined)

    expected_unique = []
    seen = set()
    for a in adrs:
        if a.upper() not in seen:
            seen.add(a.upper())
            expected_unique.append(a.upper())

    assert extracted == expected_unique


@given(
    reasons=st.lists(safe_text, min_size=1, max_size=5),
)
def test_negative_prompt_synthesis_property(reasons: list[str]):
    """Property: Negative prompt synthesis always includes standard prohibitions section."""
    history = [
        {"attempt_date": "2026-09-30", "reason": r, "failed_invariants": ["ADR-0003"]}
        for r in reasons
    ]
    prompt_section = synthesize_negative_constraints(history)

    assert "## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)" in prompt_section
    assert prompt_section.count("- Previous failure:") == len(reasons)
    assert "Mandate:" in prompt_section


def test_benchmark_latency_under_15ms(tmp_path: Path):
    """Benchmark invariant: Frontmatter update latency executes strictly under 15ms."""
    task_file = tmp_path / "0099-bench.md"
    task_file.write_text(
        "---\nid: '0099'\ntitle: Bench\nstatus: Refined\n---\n# Body\nContent\n",
        encoding="utf-8",
    )
    avg_ms = benchmark_frontmatter_update(task_file, iterations=30)
    assert avg_ms < 15.0, f"Average execution latency {avg_ms:.2f}ms exceeds 15ms invariant"
