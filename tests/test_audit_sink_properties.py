"""Generative property-based tests for structured audit sink exporter.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0010.
"""

from __future__ import annotations

import json
from pathlib import Path
from hypothesis import given, settings, strategies as st

from spec_ops.core.audit_models import (
    AuditEntry,
    AuditFilter,
    compute_sequence_hash,
    infer_event_category,
)
from spec_ops.core.audit_sink import (
    AuditSinkExporter,
    read_audit_sink,
    verify_audit_sink,
)

safe_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=30)
categories = st.sampled_from(["security", "worker", "backlog", "general"])
event_types = st.sampled_from(["TaskProposed", "TaskRefined", "SecretScanPassed", "WorkerHeartbeat", "CustomEvent"])
payload_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
    values=st.one_of(st.integers(min_value=-1000, max_value=1000), st.text(max_size=20), st.booleans()),
    max_size=5,
)


@st.composite
def sample_event_strategy(draw: st.DrawFn) -> dict:
    ev_type = draw(event_types)
    cat = draw(categories)
    payload = draw(payload_strategy)
    payload["category"] = cat
    return {
        "event_id": draw(st.uuids()).hex,
        "event_type": ev_type,
        "aggregate_id": draw(safe_text),
        "aggregate_type": "Task" if cat == "backlog" else ("Security" if cat == "security" else "Worker"),
        "payload": payload,
        "metadata": {"test": True},
        "timestamp": "2026-10-01T12:00:00+00:00",
    }


@settings(max_examples=30, deadline=None)
@given(events=st.lists(sample_event_strategy(), min_size=1, max_size=15), format_type=st.sampled_from(["jsonl", "sqlite"]))
def test_export_roundtrip_payload_fidelity(tmp_path_factory: pytest.TempPathFactory, events: list[dict], format_type: str) -> None:
    tmp_path = tmp_path_factory.mktemp("audit_prop")
    exporter = AuditSinkExporter(in_memory_events=events)
    ext = "sqlite" if format_type == "sqlite" else "jsonl"
    out_file = tmp_path / f"sink.{ext}"

    count, size, last_hash = exporter.export(out_file, format_type=format_type)
    assert count == len(events)
    assert size > 0

    reconstructed = read_audit_sink(out_file)
    assert len(reconstructed) == len(events)

    # Invariant 1: Payloads match identically in sequence
    for orig, rec in zip(events, reconstructed):
        assert rec.payload == orig["payload"]
        assert rec.event_type == orig["event_type"]

    # Invariant 2: Cryptographic sequence and hash chaining holds
    ok, msg = verify_audit_sink(reconstructed)
    assert ok is True, msg
    assert reconstructed[-1].sequence_hash == last_hash


@settings(max_examples=25, deadline=None)
@given(events=st.lists(sample_event_strategy(), min_size=1, max_size=20), target_category=categories)
def test_category_filter_invariance(tmp_path_factory: pytest.TempPathFactory, events: list[dict], target_category: str) -> None:
    tmp_path = tmp_path_factory.mktemp("filter_prop")
    exporter = AuditSinkExporter(in_memory_events=events)
    out_file = tmp_path / "filtered.jsonl"

    filter_spec = AuditFilter(category=target_category)
    count, size, _ = exporter.export_jsonl(out_file, filter_spec=filter_spec)

    reconstructed = read_audit_sink(out_file)
    assert len(reconstructed) == count
    # Every single reconstructed item must match the category filter
    for entry in reconstructed:
        assert entry.category.lower() == target_category.lower()

    # Integrity holds for filtered subset
    ok, msg = verify_audit_sink(reconstructed)
    assert ok is True, msg
