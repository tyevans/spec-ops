"""Domain models, filtering, and cryptographic hashing for audit sink entries.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0010.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

GENESIS_HASH = "0" * 64


def compute_sequence_hash(
    prev_hash: str,
    sequence_number: int,
    event_id: str,
    event_type: str,
    payload_str: str,
) -> str:
    """Computes a SHA-256 cryptographic sequence hash linking audit entries in an unbroken chain."""
    content = f"{prev_hash}:{sequence_number}:{event_id}:{event_type}:{payload_str}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_timestamp(val: str | datetime | None) -> datetime | None:
    """Parses timestamps into timezone-aware UTC datetime objects."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc) if val.tzinfo else val.replace(tzinfo=timezone.utc)
    val_clean = str(val).strip()
    try:
        dt = datetime.fromisoformat(val_clean)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            dt = datetime.strptime(val_clean[:10], "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None


def infer_event_category(
    event_type: str,
    aggregate_type: str = "",
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Infers the audit category (security, worker, backlog, general) from event properties."""
    p = payload or {}
    m = metadata or {}
    if "category" in p and str(p["category"]).strip():
        return str(p["category"]).strip().lower()
    if "category" in m and str(m["category"]).strip():
        return str(m["category"]).strip().lower()

    et = event_type.lower()
    at = aggregate_type.lower()
    if any(k in et for k in ("security", "secret", "lockfile", "cve", "vulnerability", "attestation")) or at == "security":
        return "security"
    if any(k in et for k in ("worker", "lease", "preflight", "heartbeat", "rescue")) or at == "worker":
        return "worker"
    if any(k in et for k in ("task", "backlog", "queue", "prd", "story")) or at == "task":
        return "backlog"
    return at if at else "general"


@dataclass
class AuditEntry:
    """Standardized structured audit entry with cryptographic sequence verification."""

    sequence_number: int
    sequence_hash: str
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    category: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_number": self.sequence_number,
            "sequence_hash": self.sequence_hash,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "category": self.category,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        return cls(
            sequence_number=int(data.get("sequence_number", 0)),
            sequence_hash=str(data.get("sequence_hash", "")),
            event_id=str(data.get("event_id", "")),
            event_type=str(data.get("event_type", "")),
            aggregate_id=str(data.get("aggregate_id", "")),
            aggregate_type=str(data.get("aggregate_type", "General")),
            category=str(data.get("category", "general")),
            timestamp=str(data.get("timestamp", "")),
            payload=dict(data.get("payload", {})),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_json(cls, json_str: str) -> AuditEntry:
        return cls.from_dict(json.loads(json_str))


@dataclass
class AuditFilter:
    """Filtering criteria for audit sink stream selection."""

    since: str | datetime | None = None
    until: str | datetime | None = None
    category: str | None = None
    aggregate_type: str | None = None
    event_type: str | None = None

    def matches(self, entry: AuditEntry) -> bool:
        if self.category and entry.category.lower() != self.category.lower():
            return False
        if self.aggregate_type and entry.aggregate_type.lower() != self.aggregate_type.lower():
            return False
        if self.event_type and entry.event_type.lower() != self.event_type.lower():
            return False
        if self.since:
            since_dt = parse_timestamp(self.since)
            entry_dt = parse_timestamp(entry.timestamp)
            if since_dt and entry_dt and entry_dt < since_dt:
                return False
        if self.until:
            until_dt = parse_timestamp(self.until)
            entry_dt = parse_timestamp(entry.timestamp)
            if until_dt and entry_dt and entry_dt > until_dt:
                return False
        return True
