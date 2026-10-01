"""External issue tracker ingestion bridge and backlog synchronization module."""

from __future__ import annotations

from .exporter import export_backlog_snapshot, export_tracker_sync, map_status_to_external, normalize_spec_ops_status
from .importer import IssueImporter
from .models import ExportSyncResult, ExternalIssue, ExternalStatusMapping, IngestionResult, TaskExportItem
from .parsers import (
    detect_json_source,
    fetch_github_remote,
    parse_csv_content,
    parse_github_items,
    parse_jira_items,
    parse_linear_items,
)

__all__ = [
    "ExportSyncResult",
    "ExternalIssue",
    "ExternalStatusMapping",
    "IngestionResult",
    "IssueImporter",
    "TaskExportItem",
    "detect_json_source",
    "export_backlog_snapshot",
    "export_tracker_sync",
    "fetch_github_remote",
    "map_status_to_external",
    "normalize_spec_ops_status",
    "parse_csv_content",
    "parse_github_items",
    "parse_jira_items",
    "parse_linear_items",
]
