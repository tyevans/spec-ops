"""Data models and formatting helpers for hybrid velocity and rescue analytics."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ContributorVelocity:
    """Velocity metrics for a contributor category."""

    contributor_class: str
    tasks_delivered: int = 0
    merged_commits: int = 0
    tasks_per_week: float = 0.0
    avg_cycle_time_minutes: float = 0.0
    avg_cycle_time_formatted: str = "0.0 minutes"
    preflight_pass_rate: float | None = 100.0
    self_healing_rate: float | None = None
    rescue_escalation_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureCluster:
    """Clustered failure telemetry from worker stalls and rescue interventions."""

    cluster: str
    incidents: int
    percentage: float
    top_invariants: list[str] = field(default_factory=list)
    sample_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RescueAnalytics:
    """Telemetry of autonomous worker rescues and failure clustering."""

    total_rescues: int = 0
    rescue_burden_ratio: float = 0.0
    mean_time_to_unblock_minutes: float = 0.0
    failure_clusters: list[FailureCluster] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rescues": self.total_rescues,
            "rescue_burden_ratio": self.rescue_burden_ratio,
            "mean_time_to_unblock_minutes": self.mean_time_to_unblock_minutes,
            "failure_clusters": [c.to_dict() for c in self.failure_clusters],
        }


@dataclass
class VelocityReport:
    """Comprehensive hybrid delivery velocity report."""

    window: str
    window_days: int
    generated_at: str
    agent_metrics: ContributorVelocity
    human_metrics: ContributorVelocity
    hybrid_total: ContributorVelocity
    rescues: RescueAnalytics | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "window_days": self.window_days,
            "generated_at": self.generated_at,
            "metrics": {
                "agent_workers": self.agent_metrics.to_dict(),
                "human_developers": self.human_metrics.to_dict(),
                "hybrid_total": self.hybrid_total.to_dict(),
            },
            "rescues": self.rescues.to_dict() if self.rescues else None,
        }


def parse_window_days(window: str | int = "14d") -> int:
    """Parses window string (e.g. '14d', '30d', '4w') into integer days."""
    if isinstance(window, int):
        return max(1, window)
    s = str(window).strip().lower()
    m = re.match(r"^(\d+)\s*([dwmy]?)$", s)
    if not m:
        return 14
    val = int(m.group(1))
    unit = m.group(2)
    if unit == "w":
        return max(1, val * 7)
    if unit == "m":
        return max(1, val * 30)
    if unit == "y":
        return max(1, val * 365)
    return max(1, val)


def format_cycle_time(minutes: float) -> str:
    """Formats cycle time in minutes into human-readable duration."""
    if minutes < 0.0:
        minutes = 0.0
    if minutes < 60.0:
        return f"{round(minutes, 1)} minutes"
    if minutes < 1440.0:
        return f"{round(minutes / 60.0, 1)} hours"
    return f"{round(minutes / 1440.0, 1)} days"
