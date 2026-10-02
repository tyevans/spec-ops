"""Structured event audit sink exporter and historical stream compressor.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0010, and PRD-0001.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit_models import (
    GENESIS_HASH,
    AuditEntry,
    AuditFilter,
    compute_sequence_hash,
    infer_event_category,
    parse_timestamp,
)

__all__ = [
    "GENESIS_HASH",
    "AuditEntry",
    "AuditFilter",
    "AuditSinkExporter",
    "compute_sequence_hash",
    "infer_event_category",
    "parse_timestamp",
    "read_audit_sink",
    "verify_audit_sink",
]


class AuditSinkExporter:
    """Exports and compresses immutable event ledgers into structured audit sink archives."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        in_memory_events: list[Any] | None = None,
    ):
        self.db_path = Path(db_path) if db_path else None
        self.in_memory_events = list(in_memory_events) if in_memory_events is not None else None

    def _load_raw_events(self) -> list[dict[str, Any]]:
        raw_events: list[dict[str, Any]] = []

        if self.db_path and self.db_path.exists():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='event_stream';"
                )
                if cursor.fetchone():
                    cursor.execute(
                        """
                        SELECT global_position, event_type, aggregate_id, aggregate_type, payload, metadata, recorded_at
                        FROM event_stream
                        ORDER BY global_position ASC
                        """
                    )
                    for row in cursor.fetchall():
                        payload_data = row[4]
                        if isinstance(payload_data, str):
                            try:
                                payload = json.loads(payload_data)
                            except Exception:
                                payload = {"raw": payload_data}
                        else:
                            payload = payload_data or {}

                        meta_data = row[5]
                        if isinstance(meta_data, str):
                            try:
                                meta = json.loads(meta_data)
                            except Exception:
                                meta = {"raw": meta_data}
                        else:
                            meta = meta_data or {}

                        ev_id = str(payload.get("event_id") or meta.get("event_id") or uuid.uuid4())
                        raw_events.append(
                            {
                                "event_id": ev_id,
                                "event_type": str(row[1]),
                                "aggregate_id": str(row[2]),
                                "aggregate_type": str(row[3] or "Task"),
                                "payload": payload,
                                "metadata": meta,
                                "timestamp": str(row[6] or datetime.now(timezone.utc).isoformat()),
                            }
                        )

        if self.in_memory_events:
            for ev in self.in_memory_events:
                if isinstance(ev, AuditEntry):
                    raw_events.append(ev.to_dict())
                elif hasattr(ev, "to_dict"):
                    raw_events.append(ev.to_dict())
                elif hasattr(ev, "model_dump"):
                    dump = ev.model_dump(mode="json")
                    raw_events.append(
                        {
                            "event_id": str(dump.get("event_id") or uuid.uuid4()),
                            "event_type": getattr(ev, "event_type", type(ev).__name__),
                            "aggregate_id": str(dump.get("aggregate_id") or dump.get("task_id", "")),
                            "aggregate_type": str(dump.get("aggregate_type", "Task")),
                            "payload": dump,
                            "metadata": dict(getattr(ev, "metadata", {})),
                            "timestamp": str(dump.get("occurred_at") or dump.get("timestamp") or datetime.now(timezone.utc).isoformat()),
                        }
                    )
                elif isinstance(ev, dict):
                    raw_events.append(dict(ev))

        return raw_events

    def load_entries(self, filter_spec: AuditFilter | None = None) -> list[AuditEntry]:
        """Loads and formats raw events into sequentially numbered, chained AuditEntries."""
        raw_events = self._load_raw_events()
        entries: list[AuditEntry] = []
        prev_hash = GENESIS_HASH
        seq = 1

        for raw in raw_events:
            ev_id = str(raw.get("event_id") or uuid.uuid4())
            ev_type = str(raw.get("event_type", "UnknownEvent"))
            agg_id = str(raw.get("aggregate_id", ""))
            agg_type = str(raw.get("aggregate_type", "Task"))
            payload = dict(raw.get("payload", {}))
            metadata = dict(raw.get("metadata", {}))
            timestamp = str(raw.get("timestamp") or raw.get("recorded_at") or datetime.now(timezone.utc).isoformat())
            category = infer_event_category(ev_type, agg_type, payload, metadata)

            candidate = AuditEntry(
                sequence_number=seq,
                sequence_hash="",
                event_id=ev_id,
                event_type=ev_type,
                aggregate_id=agg_id,
                aggregate_type=agg_type,
                category=category,
                timestamp=timestamp,
                payload=payload,
                metadata=metadata,
            )

            if filter_spec is not None and not filter_spec.matches(candidate):
                continue

            payload_str = json.dumps(candidate.payload, sort_keys=True)
            candidate.sequence_hash = compute_sequence_hash(prev_hash, seq, ev_id, ev_type, payload_str)
            prev_hash = candidate.sequence_hash
            entries.append(candidate)
            seq += 1

        return entries

    def export_jsonl(
        self,
        output_path: Path | str,
        filter_spec: AuditFilter | None = None,
        compress: bool = False,
    ) -> tuple[int, int, str]:
        """Exports audit stream into JSONL format, optionally gzipped."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        entries = self.load_entries(filter_spec)
        is_gz = compress or out.name.endswith(".gz")
        last_hash = entries[-1].sequence_hash if entries else GENESIS_HASH

        if is_gz:
            with gzip.open(out, "wt", encoding="utf-8") as f:
                for entry in entries:
                    f.write(entry.to_json() + "\n")
        else:
            with open(out, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(entry.to_json() + "\n")

        return len(entries), out.stat().st_size, last_hash

    def export_sqlite(
        self,
        output_path: Path | str,
        filter_spec: AuditFilter | None = None,
    ) -> tuple[int, int, str]:
        """Exports audit stream into an independent, vacuumed SQLite snapshot database."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()

        entries = self.load_entries(filter_spec)
        last_hash = entries[-1].sequence_hash if entries else GENESIS_HASH

        with sqlite3.connect(out) as conn:
            conn.execute(
                """
                CREATE TABLE audit_sink (
                    sequence_number INTEGER PRIMARY KEY,
                    sequence_hash TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX idx_audit_category ON audit_sink(category);")
            conn.execute("CREATE INDEX idx_audit_event_type ON audit_sink(event_type);")
            conn.execute("CREATE INDEX idx_audit_timestamp ON audit_sink(timestamp);")

            conn.executemany(
                """
                INSERT INTO audit_sink (
                    sequence_number, sequence_hash, event_id, event_type, aggregate_id,
                    aggregate_type, category, timestamp, payload, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    (
                        e.sequence_number,
                        e.sequence_hash,
                        e.event_id,
                        e.event_type,
                        e.aggregate_id,
                        e.aggregate_type,
                        e.category,
                        e.timestamp,
                        json.dumps(e.payload, sort_keys=True),
                        json.dumps(e.metadata, sort_keys=True),
                    )
                    for e in entries
                ],
            )
            conn.commit()
            conn.execute("VACUUM;")

        return len(entries), out.stat().st_size, last_hash

    def export(
        self,
        output_path: Path | str,
        format_type: str = "jsonl",
        filter_spec: AuditFilter | None = None,
        compress: bool = False,
    ) -> tuple[int, int, str]:
        """Unified export router for jsonl and sqlite archive formats."""
        fmt = format_type.strip().lower()
        if fmt == "sqlite":
            return self.export_sqlite(output_path, filter_spec=filter_spec)
        return self.export_jsonl(output_path, filter_spec=filter_spec, compress=compress)


def read_audit_sink(input_path: Path | str) -> list[AuditEntry]:
    """Reads and parses an exported audit sink archive from JSONL, JSONL.GZ, or SQLite."""
    inp = Path(input_path)
    if not inp.exists():
        return []

    with open(inp, "rb") as check_f:
        header = check_f.read(16)

    if header.startswith(b"SQLite format 3\x00"):
        entries: list[AuditEntry] = []
        with sqlite3.connect(inp) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT sequence_number, sequence_hash, event_id, event_type, aggregate_id,
                       aggregate_type, category, timestamp, payload, metadata
                FROM audit_sink
                ORDER BY sequence_number ASC
                """
            )
            for row in cursor.fetchall():
                payload = json.loads(row[8]) if isinstance(row[8], str) else (row[8] or {})
                metadata = json.loads(row[9]) if isinstance(row[9], str) else (row[9] or {})
                entries.append(
                    AuditEntry(
                        sequence_number=int(row[0]),
                        sequence_hash=str(row[1]),
                        event_id=str(row[2]),
                        event_type=str(row[3]),
                        aggregate_id=str(row[4]),
                        aggregate_type=str(row[5]),
                        category=str(row[6]),
                        timestamp=str(row[7]),
                        payload=payload,
                        metadata=metadata,
                    )
                )
        return entries

    if header.startswith(b"\x1f\x8b") or inp.name.endswith(".gz"):
        with gzip.open(inp, "rt", encoding="utf-8") as gf:
            return [AuditEntry.from_json(line) for line in gf if line.strip()]

    with open(inp, "r", encoding="utf-8") as f:
        return [AuditEntry.from_json(line) for line in f if line.strip()]


def verify_audit_sink(entries: list[AuditEntry]) -> tuple[bool, str]:
    """Verifies monotonic sequence numbers and SHA-256 cryptographic hash chaining."""
    if not entries:
        return True, "Audit sink is empty."

    prev_hash = GENESIS_HASH
    for i, entry in enumerate(entries):
        expected_seq = i + 1
        if entry.sequence_number != expected_seq:
            return False, f"Broken sequence order at index {i}: expected {expected_seq}, found {entry.sequence_number}"

        payload_str = json.dumps(entry.payload, sort_keys=True)
        expected_hash = compute_sequence_hash(
            prev_hash,
            entry.sequence_number,
            entry.event_id,
            entry.event_type,
            payload_str,
        )
        if entry.sequence_hash != expected_hash:
            return False, f"Cryptographic sequence hash mismatch at sequence {entry.sequence_number}"
        prev_hash = entry.sequence_hash

    return True, "Audit sink cryptographic integrity verified."
