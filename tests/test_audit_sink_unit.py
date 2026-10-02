"""Unit tests for structured event audit sink exporter and stream compressor.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0010, and PRD-0001.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import pytest

from spec_ops.config.models import ArchitectureSettings, SpecOpsConfig
from spec_ops.core.audit_models import (
    GENESIS_HASH,
    AuditEntry,
    AuditFilter,
    compute_sequence_hash,
    infer_event_category,
    parse_timestamp,
)
from spec_ops.core.audit_sink import (
    AuditSinkExporter,
    read_audit_sink,
    verify_audit_sink,
)
from spec_ops.cli.audit_sink_handler import handle_audit_sink_command


def _create_sample_sqlite_events(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_stream (
                global_position INTEGER PRIMARY KEY AUTOINCREMENT,
                stream_id TEXT NOT NULL,
                stream_version INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                aggregate_type TEXT NOT NULL DEFAULT 'Task',
                payload TEXT NOT NULL,
                metadata TEXT,
                recorded_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        events = [
            ("TASK-0001", 1, "TaskProposed", "TASK-0001", "Task", json.dumps({"title": "First Task", "category": "backlog"}), "{}", "2026-10-01T10:00:00+00:00"),
            ("TASK-0001", 2, "TaskRefined", "TASK-0001", "Task", json.dumps({"title": "First Task"}), "{}", "2026-10-01T10:05:00+00:00"),
            ("TASK-0001", 3, "SecretScanPassed", "TASK-0001", "Security", json.dumps({"scanner": "entropy", "violations": 0}), "{}", "2026-10-01T10:10:00+00:00"),
            ("WORKER-01", 1, "WorkerLeaseAcquired", "WORKER-01", "Worker", json.dumps({"lease_id": "L1"}), "{}", "2026-10-01T10:15:00+00:00"),
        ]
        conn.executemany(
            """
            INSERT INTO event_stream (
                stream_id, stream_version, event_type, aggregate_id, aggregate_type, payload, metadata, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            events,
        )
        conn.commit()


def test_category_inference() -> None:
    assert infer_event_category("SecretScanned", "Security") == "security"
    assert infer_event_category("CustomEvent", "Task", payload={"category": "audit"}) == "audit"
    assert infer_event_category("CustomEvent", "Worker", metadata={"category": "ops"}) == "ops"
    assert infer_event_category("WorkerHeartbeat", "Worker") == "worker"
    assert infer_event_category("TaskClaimed", "Task") == "backlog"
    assert infer_event_category("RandomEvent", "CustomAgg") == "customagg"


def test_timestamp_parsing() -> None:
    now = datetime.now(timezone.utc)
    assert parse_timestamp(now) == now
    assert parse_timestamp("2026-10-01T12:00:00+00:00") is not None
    assert parse_timestamp("2026-10-01") is not None
    assert parse_timestamp("not-a-date") is None
    assert parse_timestamp(None) is None


def test_audit_filter_matching() -> None:
    entry = AuditEntry(
        sequence_number=1,
        sequence_hash="abc",
        event_id="e1",
        event_type="TaskProposed",
        aggregate_id="TASK-01",
        aggregate_type="Task",
        category="backlog",
        timestamp="2026-10-01T10:00:00+00:00",
        payload={"task": 1},
    )

    f_cat = AuditFilter(category="backlog")
    assert f_cat.matches(entry) is True

    f_wrong_cat = AuditFilter(category="security")
    assert f_wrong_cat.matches(entry) is False

    f_agg = AuditFilter(aggregate_type="Task")
    assert f_agg.matches(entry) is True

    f_wrong_agg = AuditFilter(aggregate_type="Worker")
    assert f_wrong_agg.matches(entry) is False

    f_type = AuditFilter(event_type="TaskProposed")
    assert f_type.matches(entry) is True

    f_since = AuditFilter(since="2026-10-01T09:00:00+00:00")
    assert f_since.matches(entry) is True

    f_since_future = AuditFilter(since="2026-10-01T11:00:00+00:00")
    assert f_since_future.matches(entry) is False

    f_until = AuditFilter(until="2026-10-01T11:00:00+00:00")
    assert f_until.matches(entry) is True

    f_until_past = AuditFilter(until="2026-10-01T09:00:00+00:00")
    assert f_until_past.matches(entry) is False


def test_export_and_read_jsonl(tmp_path: Path) -> None:
    db_file = tmp_path / "events.db"
    _create_sample_sqlite_events(db_file)

    exporter = AuditSinkExporter(db_path=db_file)
    out_file = tmp_path / "export.jsonl"

    count, size, last_hash = exporter.export_jsonl(out_file)
    assert count == 4
    assert size > 0
    assert len(last_hash) == 64

    entries = read_audit_sink(out_file)
    assert len(entries) == 4
    assert entries[0].sequence_number == 1
    assert entries[3].sequence_number == 4

    ok, msg = verify_audit_sink(entries)
    assert ok is True
    assert msg == "Audit sink cryptographic integrity verified."


def test_export_and_read_gzip_jsonl(tmp_path: Path) -> None:
    db_file = tmp_path / "events.db"
    _create_sample_sqlite_events(db_file)

    exporter = AuditSinkExporter(db_path=db_file)
    out_file = tmp_path / "export.jsonl.gz"

    count, size, last_hash = exporter.export_jsonl(out_file, compress=True)
    assert count == 4
    assert out_file.exists()

    entries = read_audit_sink(out_file)
    assert len(entries) == 4
    ok, _ = verify_audit_sink(entries)
    assert ok is True


def test_export_and_read_sqlite(tmp_path: Path) -> None:
    db_file = tmp_path / "events.db"
    _create_sample_sqlite_events(db_file)

    exporter = AuditSinkExporter(db_path=db_file)
    out_file = tmp_path / "export.sqlite"

    count, size, last_hash = exporter.export_sqlite(out_file)
    assert count == 4
    assert out_file.exists()

    entries = read_audit_sink(out_file)
    assert len(entries) == 4
    assert entries[2].event_type == "SecretScanPassed"
    assert entries[2].category == "security"

    ok, _ = verify_audit_sink(entries)
    assert ok is True


def test_filter_by_category_export(tmp_path: Path) -> None:
    db_file = tmp_path / "events.db"
    _create_sample_sqlite_events(db_file)

    exporter = AuditSinkExporter(db_path=db_file)
    out_file = tmp_path / "security.jsonl"

    filter_spec = AuditFilter(category="security")
    count, size, last_hash = exporter.export(out_file, format_type="jsonl", filter_spec=filter_spec)
    assert count == 1

    entries = read_audit_sink(out_file)
    assert len(entries) == 1
    assert entries[0].event_type == "SecretScanPassed"
    assert entries[0].category == "security"
    assert entries[0].sequence_number == 1
    ok, _ = verify_audit_sink(entries)
    assert ok is True


def test_verify_audit_sink_tamper_detection() -> None:
    entry1 = AuditEntry(
        sequence_number=1,
        sequence_hash=compute_sequence_hash(GENESIS_HASH, 1, "e1", "Evt", json.dumps({"a": 1}, sort_keys=True)),
        event_id="e1",
        event_type="Evt",
        aggregate_id="agg1",
        aggregate_type="Task",
        category="backlog",
        timestamp="2026-10-01T10:00:00+00:00",
        payload={"a": 1},
    )

    entry2 = AuditEntry(
        sequence_number=2,
        sequence_hash=compute_sequence_hash(entry1.sequence_hash, 2, "e2", "Evt", json.dumps({"b": 2}, sort_keys=True)),
        event_id="e2",
        event_type="Evt",
        aggregate_id="agg1",
        aggregate_type="Task",
        category="backlog",
        timestamp="2026-10-01T10:05:00+00:00",
        payload={"b": 2},
    )

    ok, _ = verify_audit_sink([entry1, entry2])
    assert ok is True

    # Broken sequence number
    entry2_bad_seq = AuditEntry(
        sequence_number=5,
        sequence_hash=entry2.sequence_hash,
        event_id="e2",
        event_type="Evt",
        aggregate_id="agg1",
        aggregate_type="Task",
        category="backlog",
        timestamp=entry2.timestamp,
        payload={"b": 2},
    )
    ok_seq, msg_seq = verify_audit_sink([entry1, entry2_bad_seq])
    assert ok_seq is False
    assert "Broken sequence order" in msg_seq

    # Tampered payload
    entry2_tampered = AuditEntry(
        sequence_number=2,
        sequence_hash=entry2.sequence_hash,
        event_id="e2",
        event_type="Evt",
        aggregate_id="agg1",
        aggregate_type="Task",
        category="backlog",
        timestamp=entry2.timestamp,
        payload={"b": 999},  # tampered
    )
    ok_hash, msg_hash = verify_audit_sink([entry1, entry2_tampered])
    assert ok_hash is False
    assert "Cryptographic sequence hash mismatch" in msg_hash


def test_cli_audit_sink_jsonl_and_sqlite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_file = tmp_path / "events.db"
    _create_sample_sqlite_events(db_file)

    config = SpecOpsConfig(
        root_dir=tmp_path,
        architecture=ArchitectureSettings(),
    )

    out_jsonl = tmp_path / "audit_out.jsonl"
    args_jsonl = argparse.Namespace(
        format="jsonl",
        output=str(out_jsonl),
        db=str(db_file),
        compress=False,
        category=None,
        since=None,
        until=None,
        aggregate_type=None,
        json=False,
    )
    ret = handle_audit_sink_command(args_jsonl, config)
    assert ret == 0
    captured = capsys.readouterr()
    assert "Exported 4 structured audit events" in captured.out
    assert out_jsonl.exists()

    # Test with --json output flag
    out_sqlite = tmp_path / "audit_out.sqlite"
    args_sqlite = argparse.Namespace(
        format="sqlite",
        output=str(out_sqlite),
        db=str(db_file),
        compress=False,
        category="security",
        since=None,
        until=None,
        aggregate_type=None,
        json=True,
    )
    ret2 = handle_audit_sink_command(args_sqlite, config)
    assert ret2 == 0
    captured2 = capsys.readouterr()
    summary = json.loads(captured2.out)
    assert summary["status"] == "success"
    assert summary["exported_records"] == 1
    assert summary["format"] == "sqlite"
    assert out_sqlite.exists()
