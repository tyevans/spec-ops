"""BDD step definitions for US-0079 / TASK-0107: External Issue Tracker Status and Commit Export Sync Bridge."""

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
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0107_external_issue_tracker_status_export_sync.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


class MockGitHubBridgeHandler(http.server.BaseHTTPRequestHandler):
    requests_log: list[dict[str, Any]] = []

    def do_PATCH(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        MockGitHubBridgeHandler.requests_log.append({
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
        MockGitHubBridgeHandler.requests_log.append({
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
def github_mock_server() -> Any:
    MockGitHubBridgeHandler.requests_log = []
    server = socketserver.TCPServer(("127.0.0.1", 0), MockGitHubBridgeHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def run_spec_ops(repo: Path, args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**CLI_ENV, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def sync_context(tmp_path: Path, github_mock_server: str) -> dict[str, Any]:
    repo = tmp_path / "sync_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="SyncRepo")

    backlog_dir = repo / "docs" / "project" / "backlog"
    complete_dir = backlog_dir / "complete"
    refined_dir = backlog_dir / "refined"
    complete_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)

    (complete_dir / "0001-setup-project.md").write_text(
        f"---\nid: '0001'\ntitle: Setup Project\nstatus: Complete\nexternal_ref: {github_mock_server}/repos/org/repo/issues/101\n---\n",
        encoding="utf-8",
    )
    (refined_dir / "0002-foundation-architecture.md").write_text(
        f"---\nid: '0002'\ntitle: Foundation Architecture\nstatus: Refined\nexternal_ref: {github_mock_server}/repos/org/repo/issues/102\n---\n",
        encoding="utf-8",
    )

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Implementation Priority Queue\n\n"
        "- **TASK-0001 (Complete)**: [`0001-setup-project`](complete/0001-setup-project.md)\n"
        "- **TASK-0002 (Refined)**: [`0002-foundation-architecture`](refined/0002-foundation-architecture.md)\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat(0001): initial setup\n\nSpecOps-Task: TASK-0001\nPR: #100"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return {
        "repo": repo,
        "server_url": github_mock_server,
        "cli_output": "",
        "returncode": 0,
    }


@given("active and completed tasks in the SpecOps repository")
def given_active_and_completed_tasks(sync_context: dict[str, Any]) -> None:
    assert (sync_context["repo"] / "docs" / "project" / "backlog" / "complete" / "0001-setup-project.md").exists()
    assert (sync_context["repo"] / "docs" / "project" / "backlog" / "refined" / "0002-foundation-architecture.md").exists()


@when('"spec-ops bridge export --target github --sync-status" is run')
def when_run_bridge_export_github(sync_context: dict[str, Any]) -> None:
    repo = sync_context["repo"]
    server_url = sync_context["server_url"]
    res = run_spec_ops(
        repo,
        ["bridge", "export", "--target", "github", "--sync-status"],
        extra_env={"GITHUB_API_BASE_URL": server_url},
    )
    assert res.returncode == 0, res.stderr
    sync_context["cli_output"] = res.stdout
    sync_context["returncode"] = res.returncode


@then("external GitHub issues are updated with corresponding status labels and commit references.")
def then_github_issues_updated(sync_context: dict[str, Any]) -> None:
    reqs = MockGitHubBridgeHandler.requests_log
    assert len(reqs) >= 2, f"Expected at least 2 requests to mock server, got: {reqs}"

    # Verify PATCH to issue 101 updated state to closed and added status label
    patch_101 = next((r for r in reqs if r["method"] == "PATCH" and "101" in r["path"]), None)
    assert patch_101 is not None
    assert patch_101["body"]["state"] == "closed"
    assert "status: completed" in patch_101["body"]["labels"]

    # Verify POST comment to issue 101 contains commit trailer reference and PR
    post_101 = next((r for r in reqs if r["method"] == "POST" and "101/comments" in r["path"]), None)
    assert post_101 is not None
    comment_body = post_101["body"]["body"]
    assert "SpecOps-Task: TASK-0001" in comment_body
    assert "#100" in comment_body


@given("the system is initialized and ready")
def given_system_initialized(sync_context: dict[str, Any]) -> None:
    assert sync_context["repo"].exists()


@when('the user executes the workflow for "External Issue Tracker Status and Commit Export Sync Bridge"')
def when_user_executes_workflow(sync_context: dict[str, Any]) -> None:
    repo = sync_context["repo"]
    server_url = sync_context["server_url"]
    res = run_spec_ops(
        repo,
        ["bridge", "export", "--target", "github", "--sync-status"],
        extra_env={"GITHUB_API_BASE_URL": server_url},
    )
    sync_context["cli_output"] = res.stdout
    sync_context["returncode"] = res.returncode


@then("Bi-directional Export of Backlog Status for Executive Roadmaps*")
def then_bidirectional_export_verified(sync_context: dict[str, Any]) -> None:
    out = sync_context["cli_output"]
    assert "External Issue Tracker Sync Export: Github" in out
    assert "TASK-0001: Setup Project" in out
    assert "TASK-0002: Foundation Architecture" in out


@then("observable outputs satisfy public contracts without backdoor tampering.")
def then_observable_outputs_satisfy_contracts(sync_context: dict[str, Any]) -> None:
    assert sync_context["returncode"] == 0
    assert len(sync_context["cli_output"]) > 50
