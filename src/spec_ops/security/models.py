"""Data models for zero-trust worker process sandboxing and security auditing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SecurityViolationEvent:
    """Structured security alert event emitted upon sandboxing violation."""

    command: str
    prohibited_binary: str
    parent_pid: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event: str = "SECURITY_ALERT_COMMAND_PROHIBITED"
    exit_code: int = 126
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityViolationEvent:
        return cls(
            command=data.get("command", ""),
            prohibited_binary=data.get("prohibited_binary", ""),
            parent_pid=data.get("parent_pid", 0),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            event=data.get("event", "SECURITY_ALERT_COMMAND_PROHIBITED"),
            exit_code=data.get("exit_code", 126),
            details=data.get("details", ""),
        )


@dataclass
class BenchmarkResult:
    """Comparative benchmark metrics for process isolation strategies."""

    paradigm: str
    avg_latency_ms: float
    p99_latency_ms: float
    security_guarantee: str
    requires_root: bool
    platform_supported: bool
    description: str


@dataclass
class BenchmarkReport:
    """Complete comparative benchmark report across isolation paradigms."""

    results: list[BenchmarkResult]
    meets_latency_invariant: bool
    summary: str
