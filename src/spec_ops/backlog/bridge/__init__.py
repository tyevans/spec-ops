"""External issue tracker ingestion bridge and backlog synchronization module."""

from __future__ import annotations

from .exporter import export_backlog_snapshot
from .importer import IssueImporter
from .models import ExternalIssue, IngestionResult
from .parsers import (
    detect_json_source,
    fetch_github_remote,
    parse_csv_content,
    parse_github_items,
    parse_jira_items,
    parse_linear_items,
)

__all__ = [
    "ExternalIssue",
    "IngestionResult",
    "IssueImporter",
    "export_backlog_snapshot",
    "detect_json_source",
    "fetch_github_remote",
    "parse_csv_content",
    "parse_github_items",
    "parse_jira_items",
    "parse_linear_items",
]
