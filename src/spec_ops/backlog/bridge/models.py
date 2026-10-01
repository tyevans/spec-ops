"""Data models for external issue tracker ingestion and backlog synchronization bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExternalIssue:
    """Normalized external issue payload from GitHub, Jira, or Linear."""

    key: str
    title: str
    description: str = ""
    status: str = "open"
    url: str = ""
    target_bc: str = "core"
    dependencies: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    governing_prds: list[str] = field(default_factory=list)
    governing_adrs: list[str] = field(default_factory=list)
    governing_stories: list[str] = field(default_factory=list)
    source: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionResult:
    """Summary of batch issue ingestion into the SpecOps backlog."""

    imported_count: int
    ready_count: int
    dor_incomplete_count: int
    task_ids: list[str] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)
    key_mapping: dict[str, str] = field(default_factory=dict)

    @property
    def summary_message(self) -> str:
        return (
            f"Imported {self.imported_count} tasks "
            f"({self.ready_count} ready for refinement, {self.dor_incomplete_count} requiring DoR completion)"
        )
