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


@dataclass
class ExternalStatusMapping:
    """Mapping from canonical SpecOps status to target platform issue status."""

    target: str
    original_status: str
    target_state: str
    target_status_name: str
    labels: list[str] = field(default_factory=list)
    state_reason: str = ""
    resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "target": self.target,
            "original_status": self.original_status,
            "target_state": self.target_state,
            "target_status_name": self.target_status_name,
        }
        if self.labels:
            d["labels"] = list(self.labels)
        if self.state_reason:
            d["state_reason"] = self.state_reason
        if self.resolution:
            d["resolution"] = self.resolution
        return d


@dataclass
class TaskExportItem:
    """Structured export item for a single task synchronized to an external tracker."""

    task_id: str
    task_title: str
    spec_ops_status: str
    target: str
    external_key: str
    external_url: str = ""
    status_mapping: ExternalStatusMapping | None = None
    commit_hashes: list[str] = field(default_factory=list)
    commits: list[dict[str, Any]] = field(default_factory=list)
    pr_references: list[str] = field(default_factory=list)
    sync_action: str = "none"
    comment_body: str = ""
    synced: bool = False
    sync_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_title": self.task_title,
            "spec_ops_status": self.spec_ops_status,
            "target": self.target,
            "external_key": self.external_key,
            "external_url": self.external_url,
            "target_status": self.status_mapping.to_dict() if self.status_mapping else {},
            "commit_hashes": list(self.commit_hashes),
            "commits": list(self.commits),
            "pr_references": list(self.pr_references),
            "sync_action": self.sync_action,
            "comment_body": self.comment_body,
            "synced": self.synced,
            "sync_error": self.sync_error,
        }


@dataclass
class ExportSyncResult:
    """Summary and payload of an external tracker export and synchronization run."""

    target: str
    total_tasks: int
    synced_count: int
    dry_run: bool
    sync_status: bool
    items: list[TaskExportItem] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "total_tasks": self.total_tasks,
            "synced_count": self.synced_count,
            "dry_run": self.dry_run,
            "sync_status": self.sync_status,
            "generated_at": self.generated_at,
            "items": [item.to_dict() for item in self.items],
        }

    def to_json(self, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        target_name = self.target.capitalize()
        status_label = "Enabled" if self.sync_status else "Disabled"
        dry_run_label = "True" if self.dry_run else "False"

        rows: list[str] = [
            f"# External Issue Tracker Sync Export: {target_name}",
            "",
            f"Structured synchronization export reflecting SpecOps task statuses, git commit trailers, and pull requests to {target_name}.",
            "",
            "## Synchronization Summary",
            f"- **Target Platform**: {target_name}",
            f"- **Sync Status Execution**: {status_label}",
            f"- **Dry Run Mode**: {dry_run_label}",
            f"- **Total Tasks Exported**: {self.total_tasks}",
            f"- **Tasks Synchronized**: {self.synced_count}",
            "",
            "## Exported Work Items",
        ]

        if not self.items:
            rows.append("*No tasks available for export.*")
        else:
            rows.append("| SpecOps Task | External Ticket | SpecOps Status | Target State | Commits | Pull Requests | Sync Action | Synced |")
            rows.append("|---|---|---|---|---|---|---|---|")
            for item in self.items:
                ext_link = f"[{item.external_key}]({item.external_url})" if item.external_url else item.external_key
                target_state = item.status_mapping.target_state if item.status_mapping else "-"
                commits_str = ", ".join(f"`{h[:7]}`" for h in item.commit_hashes) if item.commit_hashes else "-"
                prs_str = ", ".join(item.pr_references) if item.pr_references else "-"
                synced_icon = "✅" if item.synced else ("⚠️ Simulated" if self.dry_run else "⏳ Pending")
                rows.append(
                    f"| {item.task_id}: {item.task_title} | {ext_link} | {item.spec_ops_status} | {target_state} | {commits_str} | {prs_str} | {item.sync_action} | {synced_icon} |"
                )

        return "\n".join(rows) + "\n"

