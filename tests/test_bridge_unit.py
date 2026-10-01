"""Unit tests for external issue tracker ingestion bridge parsers and importer (TASK-0079, ADR-0003)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error

import pytest

from spec_ops.backlog.bridge.exporter import export_backlog_snapshot
from spec_ops.backlog.bridge.importer import IssueImporter
from spec_ops.backlog.bridge.models import ExternalIssue
from spec_ops.backlog.bridge.parsers import (
    detect_json_source,
    fetch_github_remote,
    parse_csv_content,
    parse_github_items,
    parse_jira_items,
    parse_linear_items,
)
from spec_ops.config.loader import load_config
from spec_ops.core.schema_validator import validate_document
from spec_ops.scaffold.init import init_project


def test_github_json_parser() -> None:
    payload = [
        {
            "number": 42,
            "title": "Fix token expiration bug",
            "body": "Token expires prematurely.\n\nbc: auth\nDepends on: #40",
            "html_url": "https://github.com/acme/repo/issues/42",
            "state": "open",
            "labels": [{"name": "bug"}, {"name": "backlog"}],
        },
        {
            "number": 43,
            "title": "PR to ignore",
            "body": "PR description",
            "pull_request": {"url": "https://..."},
        },
    ]
    issues = parse_github_items([p for p in payload if "pull_request" not in p])
    assert len(issues) == 1
    iss = issues[0]
    assert iss.key == "#42"
    assert iss.title == "Fix token expiration bug"
    assert iss.target_bc == "auth"
    assert iss.url == "https://github.com/acme/repo/issues/42"
    assert "#40" in iss.dependencies


def test_jira_json_parser() -> None:
    payload = {
        "issues": [
            {
                "key": "CORE-101",
                "fields": {
                    "summary": "Implement Redis Cache Seam",
                    "description": "Add caching layer.\nDepends on: CORE-100",
                    "status": {"name": "In Progress"},
                    "components": [{"name": "cache"}],
                    "labels": ["backend"],
                    "issuelinks": [
                        {
                            "type": {"name": "Blocks", "inward": "is blocked by"},
                            "inwardIssue": {"key": "CORE-99"},
                        }
                    ],
                },
            }
        ]
    }
    issues = parse_jira_items(payload)
    assert len(issues) == 1
    iss = issues[0]
    assert iss.key == "CORE-101"
    assert iss.title == "Implement Redis Cache Seam"
    assert iss.target_bc == "cache"
    assert "CORE-99" in iss.dependencies
    assert "CORE-100" in iss.dependencies


def test_linear_json_parser() -> None:
    payload = {
        "data": {
            "issues": [
                {
                    "identifier": "ENG-501",
                    "title": "Decompose monolithic visualizer",
                    "description": "Split radar script from bundle.",
                    "url": "https://linear.app/acme/issue/ENG-501",
                    "state": {"name": "Todo"},
                    "parent": {"identifier": "ENG-500"},
                    "relations": [
                        {
                            "type": "blocked_by",
                            "relatedIssue": {"identifier": "ENG-499"},
                        }
                    ],
                }
            ]
        }
    }
    issues = parse_linear_items(payload)
    assert len(issues) == 1
    iss = issues[0]
    assert iss.key == "ENG-501"
    assert iss.title == "Decompose monolithic visualizer"
    assert "ENG-500" in iss.dependencies
    assert "ENG-499" in iss.dependencies


def test_csv_parser_auto_detect() -> None:
    # Jira CSV
    jira_csv = "Issue key,Summary,Description,Status,Component\nPROJ-1,Title 1,Body 1,Open,worker\n"
    jira_issues = parse_csv_content(jira_csv, source="auto")
    assert len(jira_issues) == 1
    assert jira_issues[0].key == "PROJ-1"
    assert jira_issues[0].source == "jira"

    # Linear CSV
    linear_csv = "Identifier,Title,Description,Status,Blocked by\nLIN-1,Title 2,Body 2,Todo,LIN-0\n"
    linear_issues = parse_csv_content(linear_csv, source="auto")
    assert len(linear_issues) == 1
    assert linear_issues[0].key == "LIN-1"
    assert "LIN-0" in linear_issues[0].dependencies

    # GitHub CSV
    gh_csv = "Issue number,Title,Body,State,URL\n10,Title 3,Body 3,open,https://gh.com/10\n"
    gh_issues = parse_csv_content(gh_csv, source="auto")
    assert len(gh_issues) == 1
    assert gh_issues[0].key == "10"


def test_detect_json_source() -> None:
    assert detect_json_source({"data": {"issues": []}}) == "linear"
    assert detect_json_source({"issues": [{"fields": {}}]}) == "jira"
    assert detect_json_source([{"identifier": "X"}]) == "linear"
    assert detect_json_source([{"html_url": "https://..."}]) == "github"


def test_fetch_github_remote_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_BASE_URL", "http://127.0.0.1:9")
    with pytest.raises(RuntimeError, match="Failed to connect to GitHub API"):
        fetch_github_remote("nonexistent/repo")


def test_importer_dependency_mapping_and_priority_sync(tmp_path: Path) -> None:
    repo = tmp_path / "test_repo"
    repo.mkdir()
    init_project(repo, name="TestProject")
    backlog_dir = repo / "docs" / "project" / "backlog"

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Implementation Priority Queue\n\n- **TASK-0001 (Complete)**: [`0001-init`](complete/0001-init.md)\n",
        encoding="utf-8",
    )

    issues = [
        ExternalIssue(
            key="TICKET-A",
            title="First Imported Ticket",
            description="First ticket description",
            url="https://jira.corp/TICKET-A",
        ),
        ExternalIssue(
            key="TICKET-B",
            title="Second Ticket Depending on First",
            description="Second ticket description",
            dependencies=["TICKET-A"],
            url="https://jira.corp/TICKET-B",
        ),
    ]

    importer = IssueImporter(backlog_dir=backlog_dir)
    res = importer.ingest_issues(issues, default_bc="worker")

    assert res.imported_count == 2
    assert len(res.task_ids) == 2
    id1, id2 = res.task_ids

    # Verify non-colliding sequential IDs starting after 0001
    assert id1 == "TASK-0002"
    assert id2 == "TASK-0003"

    # Verify task 2 dependencies mapped TICKET-A to TASK-0002
    file2 = res.files[1]
    content2 = file2.read_text(encoding="utf-8")
    assert "dependencies:\n- TASK-0002" in content2
    assert "external_ref: https://jira.corp/TICKET-B" in content2

    # Verify schema validity
    errs = validate_document(content2, file_path=file2)
    assert len(errs) == 0, [str(e) for e in errs]

    # Verify PRIORITY.md preserved existing and appended new tasks
    priority_content = priority_file.read_text(encoding="utf-8")
    assert "- **TASK-0001 (Complete)**: [`0001-init`](complete/0001-init.md)" in priority_content
    assert "- **TASK-0002 (Proposed)**:" in priority_content
    assert "- **TASK-0003 (Proposed)**:" in priority_content


def test_export_backlog_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "snap_repo"
    repo.mkdir()
    init_project(repo, name="SnapTest")
    backlog_dir = repo / "docs" / "project" / "backlog"

    out_file = repo / "docs" / "reference" / "backlog-snapshot.md"
    content = export_backlog_snapshot(backlog_dir, output_path=out_file)

    assert out_file.exists()
    assert "Completion Burn-up" in content
    assert "Buffer Health" in content
    assert "Milestone Delivery Estimates" in content
