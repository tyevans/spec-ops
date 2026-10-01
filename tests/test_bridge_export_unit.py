"""Unit tests for external issue tracker status and commit export sync bridge (TASK-0107, ADR-0003)."""

from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import socketserver
import subprocess
import sys
import threading
from typing import Any

import pytest

from spec_ops.backlog.bridge.exporter import (
    export_backlog_snapshot,
    export_tracker_sync,
    extract_task_external_ticket,
    format_sync_comment,
    harvest_task_commits_and_prs,
    map_status_to_external,
    normalize_spec_ops_status,
    parse_github_issue_ref,
    sync_external_issue,
)
from spec_ops.backlog.bridge.models import ExternalStatusMapping, TaskExportItem
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**CLI_ENV, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


class MockGitHubSyncHandler(http.server.BaseHTTPRequestHandler):
    recorded_requests: list[dict[str, Any]] = []

    def do_PATCH(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        MockGitHubSyncHandler.recorded_requests.append({
            "method": "PATCH",
            "path": self.path,
            "body": body,
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        MockGitHubSyncHandler.recorded_requests.append({
            "method": "POST",
            "path": self.path,
            "body": body,
        })
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "created"}')

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def mock_github_server() -> Any:
    MockGitHubSyncHandler.recorded_requests = []
    server = socketserver.TCPServer(("127.0.0.1", 0), MockGitHubSyncHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_normalize_spec_ops_status() -> None:
    assert normalize_spec_ops_status("Complete") == "Complete"
    assert normalize_spec_ops_status("COMPLETED") == "Complete"
    assert normalize_spec_ops_status("done") == "Complete"
    assert normalize_spec_ops_status("In-Progress") == "In-Progress"
    assert normalize_spec_ops_status("in_progress") == "In-Progress"
    assert normalize_spec_ops_status("active") == "In-Progress"
    assert normalize_spec_ops_status("Review") == "Review"
    assert normalize_spec_ops_status("in-review") == "Review"
    assert normalize_spec_ops_status("Blocked") == "Blocked"
    assert normalize_spec_ops_status("Refined") == "Refined"
    assert normalize_spec_ops_status("ready") == "Refined"
    assert normalize_spec_ops_status("Proposed") == "Proposed"
    assert normalize_spec_ops_status("unknown-state") == "Proposed"


def test_map_status_to_external_github() -> None:
    comp = map_status_to_external("Complete", "github")
    assert comp.target_state == "closed"
    assert comp.state_reason == "completed"
    assert "status: completed" in comp.labels

    prog = map_status_to_external("In-Progress", "github")
    assert prog.target_state == "open"
    assert "status: in-progress" in prog.labels


def test_map_status_to_external_jira() -> None:
    comp = map_status_to_external("Complete", "jira")
    assert comp.target_state == "Done"
    assert comp.resolution == "Done"

    prog = map_status_to_external("In-Progress", "jira")
    assert prog.target_state == "In Progress"

    ref = map_status_to_external("Refined", "jira")
    assert ref.target_state == "Selected for Development"


def test_map_status_to_external_linear() -> None:
    comp = map_status_to_external("Complete", "linear")
    assert comp.target_state == "Done"

    ref = map_status_to_external("Refined", "linear")
    assert ref.target_state == "Todo"


def test_parse_github_issue_ref() -> None:
    repo, num = parse_github_issue_ref("https://github.com/my-org/my-repo/issues/42")
    assert repo == "my-org/my-repo"
    assert num == "42"

    repo, num = parse_github_issue_ref("http://127.0.0.1:8080/repos/acme/proj/issues/99")
    assert repo == "acme/proj"
    assert num == "99"

    repo, num = parse_github_issue_ref("#105", default_repo="fallback/repo")
    assert repo == "fallback/repo"
    assert num == "105"


def test_extract_task_external_ticket() -> None:
    t1 = Task(id="0001", title="Task 1", external_ref="https://github.com/org/repo/issues/101")
    key, url = extract_task_external_ticket(t1, "github")
    assert key == "#101"
    assert url == "https://github.com/org/repo/issues/101"

    t2 = Task(id="0002", title="Task 2", external_ref="https://jira.corp/browse/PROJ-50")
    key, url = extract_task_external_ticket(t2, "jira")
    assert key == "PROJ-50"

    t3 = Task(id="0003", title="Task 3", external_ref="https://linear.app/team/issue/ENG-99")
    key, url = extract_task_external_ticket(t3, "linear")
    assert key == "ENG-99"

    # Fallback to canonical ID
    t4 = Task(id="0004", title="Task 4")
    key, url = extract_task_external_ticket(t4, "github")
    assert key == "#4"


def test_format_sync_comment() -> None:
    item = TaskExportItem(
        task_id="TASK-0001",
        task_title="Core Architecture",
        spec_ops_status="Complete",
        target="github",
        external_key="#101",
        commits=[{"short_hash": "a1b2c3d", "subject": "feat: architecture setup"}],
        pr_references=["#42"],
    )
    comment = format_sync_comment(item)
    assert "TASK-0001: Core Architecture" in comment
    assert "Status**: Complete" in comment
    assert "`a1b2c3d` feat: architecture setup" in comment
    assert "#42" in comment


def test_sync_external_issue_dry_run() -> None:
    item = TaskExportItem(
        task_id="TASK-0001",
        task_title="Test Task",
        spec_ops_status="Complete",
        target="github",
        external_key="#101",
    )
    sync_external_issue(item, dry_run=True)
    assert item.synced is False
    assert item.sync_action == "simulated"


def test_sync_external_issue_with_mock_github(mock_github_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_BASE_URL", mock_github_server)
    item = TaskExportItem(
        task_id="TASK-0001",
        task_title="Setup",
        spec_ops_status="Complete",
        target="github",
        external_key="101",
        external_url=f"{mock_github_server}/repos/org/repo/issues/101",
        status_mapping=map_status_to_external("Complete", "github"),
        comment_body="### SpecOps Status Synchronization\n- Task: TASK-0001",
    )
    sync_external_issue(item, dry_run=False)
    assert item.synced is True
    assert item.sync_action == "updated_and_commented"

    # Verify requests sent to mock server
    reqs = MockGitHubSyncHandler.recorded_requests
    assert len(reqs) == 2
    patch_req = next(r for r in reqs if r["method"] == "PATCH")
    assert patch_req["path"] == "/repos/org/repo/issues/101"
    assert patch_req["body"]["state"] == "closed"
    assert "status: completed" in patch_req["body"]["labels"]

    post_req = next(r for r in reqs if r["method"] == "POST")
    assert post_req["path"] == "/repos/org/repo/issues/101/comments"
    assert "SpecOps Status Synchronization" in post_req["body"]["body"]


def test_export_backlog_snapshot_with_target(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_project(repo, name="ExportTest")
    backlog_dir = repo / "docs" / "project" / "backlog"

    complete_dir = backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    (complete_dir / "0001-setup.md").write_text(
        "---\nid: '0001'\ntitle: Setup Project\nstatus: Complete\nexternal_ref: https://github.com/org/repo/issues/101\n---\n",
        encoding="utf-8",
    )

    out_json = repo / "export.json"
    content_json = export_backlog_snapshot(
        backlog_dir=backlog_dir,
        target="github",
        format="json",
        output_path=out_json,
    )
    assert out_json.exists()
    data = json.loads(content_json)
    assert data["target"] == "github"
    assert data["total_tasks"] == 1
    assert data["items"][0]["task_id"] == "TASK-0001"

    out_md = repo / "export.md"
    content_md = export_backlog_snapshot(
        backlog_dir=backlog_dir,
        target="jira",
        format="markdown",
        output_path=out_md,
    )
    assert out_md.exists()
    assert "External Issue Tracker Sync Export: Jira" in content_md
    assert "TASK-0001" in content_md


def test_cli_bridge_export_and_backlog_export(tmp_path: Path) -> None:
    repo = tmp_path / "cli_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@example.com"], cwd=repo, check=True, capture_output=True)
    init_project(repo, name="CLIRepo")

    backlog_dir = repo / "docs" / "project" / "backlog"
    complete_dir = backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    (complete_dir / "0001-init.md").write_text(
        "---\nid: '0001'\ntitle: Init System\nstatus: Complete\n---\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init\n\nSpecOps-Task: TASK-0001\nPR: #10"], cwd=repo, check=True, capture_output=True)

    # 1. Test bridge export --target github --dry-run
    res1 = run_spec_ops(repo, ["bridge", "export", "--target", "github", "--dry-run"])
    assert res1.returncode == 0, res1.stderr
    assert "External Issue Tracker Sync Export: Github" in res1.stdout
    assert "**Dry Run Mode**: True" in res1.stdout

    # 2. Test backlog export --target linear --format json
    res2 = run_spec_ops(repo, ["backlog", "export", "--target", "linear", "--format", "json"])
    assert res2.returncode == 0, res2.stderr
    parsed = json.loads(res2.stdout)
    assert parsed["target"] == "linear"
    assert parsed["items"][0]["task_id"] == "TASK-0001"
    assert parsed["items"][0]["pr_references"] == ["#10"]
