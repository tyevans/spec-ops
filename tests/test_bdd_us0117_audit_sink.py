"""Executable BDD scenarios for US-0117 / TASK-0160: Distributed Audit Sink Exporter.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009, ADR-0010; PRD-0001; US-0117.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any
import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.cli.audit_sink_handler import handle_audit_sink_command
from spec_ops.config.models import ArchitectureSettings, SpecOpsConfig
from spec_ops.core.audit_sink import read_audit_sink, verify_audit_sink

scenarios("features/us_0117_audit_sink.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    """Shared context for US-0117 / TASK-0160 BDD scenarios."""
    db_file = tmp_path / ".specops" / "events.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    config = SpecOpsConfig(
        root_dir=tmp_path,
        architecture=ArchitectureSettings(),
    )
    return {
        "root_dir": tmp_path,
        "db_path": db_file,
        "config": config,
        "exit_code": None,
        "output_file": None,
    }


def _seed_db(db_path: Path, events: list[tuple]) -> None:
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
        conn.executemany(
            """
            INSERT INTO event_stream (
                stream_id, stream_version, event_type, aggregate_id, aggregate_type, payload, metadata, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            events,
        )
        conn.commit()


# --- Scenario 1: Exporting decider events to structured JSONL audit sink ---


@given("an event store with recorded lifecycle transitions")
def event_store_with_transitions(bdd_context: dict[str, Any]) -> None:
    db_path: Path = bdd_context["db_path"]
    events = [
        ("TASK-0160", 1, "TaskProposed", "TASK-0160", "Task", json.dumps({"title": "Audit Sink"}), "{}", "2026-10-01T10:00:00+00:00"),
        ("TASK-0160", 2, "TaskRefined", "TASK-0160", "Task", json.dumps({"title": "Audit Sink"}), "{}", "2026-10-01T10:05:00+00:00"),
        ("TASK-0160", 3, "TaskClaimed", "TASK-0160", "Task", json.dumps({"worker": "agent-1"}), "{}", "2026-10-01T10:10:00+00:00"),
        ("TASK-0160", 4, "TaskCompleted", "TASK-0160", "Task", json.dumps({"status": "Complete"}), "{}", "2026-10-01T10:15:00+00:00"),
    ]
    _seed_db(db_path, events)
    bdd_context["seeded_count"] = len(events)


@when("the developer runs spec-ops audit sink with JSONL format")
def run_audit_sink_jsonl(bdd_context: dict[str, Any]) -> None:
    out_file = bdd_context["root_dir"] / "dist" / "audit" / "audit-sink.jsonl"
    bdd_context["output_file"] = out_file

    args = argparse.Namespace(
        format="jsonl",
        output=str(out_file),
        db=str(bdd_context["db_path"]),
        compress=False,
        category=None,
        since=None,
        until=None,
        aggregate_type=None,
        json=False,
    )
    code = handle_audit_sink_command(args, bdd_context["config"])
    bdd_context["exit_code"] = code


@then("all events are exported into structured lines with sequence numbers and timestamps")
def verify_exported_lines(bdd_context: dict[str, Any]) -> None:
    out_file: Path = bdd_context["output_file"]
    assert out_file.exists()

    entries = read_audit_sink(out_file)
    assert len(entries) == bdd_context["seeded_count"]

    for i, entry in enumerate(entries):
        assert entry.sequence_number == i + 1
        assert entry.timestamp is not None
        assert len(entry.timestamp) > 0
        assert len(entry.sequence_hash) == 64

    ok, msg = verify_audit_sink(entries)
    assert ok is True, msg


@then("the command terminates with exit code 0")
def verify_exit_code_zero(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0


# --- Scenario 2: Filtering exported events by category ---


@given("an event store containing worker, security, and backlog events")
def event_store_with_multiple_categories(bdd_context: dict[str, Any]) -> None:
    db_path: Path = bdd_context["db_path"]
    events = [
        ("TASK-0100", 1, "TaskProposed", "TASK-0100", "Task", json.dumps({"category": "backlog"}), "{}", "2026-10-01T09:00:00+00:00"),
        ("SEC-001", 1, "SecretScanPassed", "SEC-001", "Security", json.dumps({"category": "security"}), "{}", "2026-10-01T09:05:00+00:00"),
        ("SEC-002", 1, "LockfileAttested", "SEC-002", "Security", json.dumps({"category": "security"}), "{}", "2026-10-01T09:10:00+00:00"),
        ("WORKER-001", 1, "WorkerSpawned", "WORKER-001", "Worker", json.dumps({"category": "worker"}), "{}", "2026-10-01T09:15:00+00:00"),
    ]
    _seed_db(db_path, events)


@when("the developer exports events filtered to security events")
def export_filtered_security_events(bdd_context: dict[str, Any]) -> None:
    out_file = bdd_context["root_dir"] / "dist" / "audit" / "security-audit.jsonl"
    bdd_context["output_file"] = out_file

    args = argparse.Namespace(
        format="jsonl",
        output=str(out_file),
        db=str(bdd_context["db_path"]),
        compress=False,
        category="security",
        since=None,
        until=None,
        aggregate_type=None,
        json=False,
    )
    code = handle_audit_sink_command(args, bdd_context["config"])
    bdd_context["exit_code"] = code


@then("only matching security audit events are emitted to the output file")
def verify_only_security_emitted(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["exit_code"] == 0
    out_file: Path = bdd_context["output_file"]
    assert out_file.exists()

    entries = read_audit_sink(out_file)
    assert len(entries) == 2
    for entry in entries:
        assert entry.category == "security"

    ok, msg = verify_audit_sink(entries)
    assert ok is True, msg
