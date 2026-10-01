"""BDD step definitions for US-0079: Brownfield Issue Ingestion and External Backlog Synchronization Bridge."""

from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import re
import socketserver
import subprocess
import sys
import threading
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
import yaml

from spec_ops.scaffold.init import init_project

scenarios("features/us_0079_brownfield_issue_ingestion_and_backlog_sync_bridge.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


class MockGitHubHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if "/repos/org/repo/issues" in self.path:
            issues = [
                {
                    "number": 101,
                    "title": "Enable distributed tracing seam",
                    "body": "Add open-telemetry collector hook.\n\nbc: telemetry\nDepends on: #100",
                    "html_url": "https://github.com/org/repo/issues/101",
                    "state": "open",
                    "labels": [{"name": "backlog"}],
                },
                {
                    "number": 102,
                    "title": "Configurable audit log rotation",
                    "body": "Rotate logs every 24h.\n\nbc: security",
                    "html_url": "https://github.com/org/repo/issues/102",
                    "state": "open",
                    "labels": [{"name": "backlog"}],
                },
            ]
            data = json.dumps(issues).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def github_server() -> Any:
    server = socketserver.TCPServer(("127.0.0.1", 0), MockGitHubHandler)
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
def bridge_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "bridge_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@example.com"], cwd=repo, check=True, capture_output=True)

    init_project(repo, name="BridgeRepo")

    backlog_dir = repo / "docs" / "project" / "backlog"
    complete_dir = backlog_dir / "complete"
    refined_dir = backlog_dir / "refined"
    complete_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)

    (complete_dir / "0001-setup-project.md").write_text(
        "---\nid: '0001'\ntitle: Setup Project\nstatus: Complete\n---\n", encoding="utf-8"
    )
    (refined_dir / "0002-foundation-architecture.md").write_text(
        "---\nid: '0002'\ntitle: Foundation Architecture\nstatus: Refined\n---\n", encoding="utf-8"
    )

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Implementation Priority Queue\n\n"
        "- **TASK-0001 (Complete)**: [`0001-setup-project`](complete/0001-setup-project.md)\n"
        "- **TASK-0002 (Refined)**: [`0002-foundation-architecture`](refined/0002-foundation-architecture.md)\n",
        encoding="utf-8",
    )

    # Scaffolding accepted ADR, PRD, and Story for DoR checks
    docs_dir = repo / "docs" / "project"
    (docs_dir / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)
    (docs_dir / "adrs" / "accepted" / "adr-0001-core.md").write_text(
        "---\nid: 'ADR-0001'\ntitle: Core ADR\nstatus: Accepted\n---\n", encoding="utf-8"
    )

    (docs_dir / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (docs_dir / "product" / "accepted" / "prd-0001-core.md").write_text(
        "---\nid: 'PRD-0001'\ntitle: Core PRD\nstatus: Accepted\n---\n", encoding="utf-8"
    )

    (docs_dir / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (docs_dir / "user_stories" / "accepted" / "us-0001-core.md").write_text(
        "---\nid: 'US-0001'\ntitle: Core Story\nstatus: Accepted\n---\n", encoding="utf-8"
    )

    (docs_dir / "user_stories" / "PERSONAS.md").write_text(
        "# Customer Personas\n\n## 1. Taylor — The Product Manager\n- **Pain Points**:\n  - Drift\n- **Goals**:\n  - Speed\n",
        encoding="utf-8",
    )

    return {"repo": repo, "cli_output": "", "github_base_url": ""}


@given('a GitHub repository with open issues labeled "backlog"')
def given_github_repo_with_issues(bridge_context: dict[str, Any], github_server: str) -> None:
    bridge_context["github_base_url"] = github_server


@when('the product manager runs "spec-ops backlog import --source github --repo org/repo --label backlog"')
def when_run_backlog_import_github(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    base_url = bridge_context["github_base_url"]
    res = run_spec_ops(
        repo,
        ["backlog", "import", "--source", "github", "--repo", "org/repo", "--label", "backlog"],
        extra_env={"GITHUB_API_BASE_URL": base_url},
    )
    assert res.returncode == 0, res.stderr
    bridge_context["cli_output"] = res.stdout


@then('SpecOps converts each open issue into a Markdown task file in "docs/project/backlog/proposed/"')
def then_converts_open_issues_to_proposed(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    files = list(proposed_dir.glob("*.md"))
    assert len(files) == 2


@then("synthesizes frontmatter containing sequential ID, title, target bounded context, and imported issue URL")
def then_synthesizes_frontmatter(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    files = sorted(proposed_dir.glob("*.md"))
    f1, f2 = files[0], files[1]

    m1 = yaml.safe_load(f1.read_text(encoding="utf-8").split("---", 2)[1])
    m2 = yaml.safe_load(f2.read_text(encoding="utf-8").split("---", 2)[1])

    # Starts sequentially after 0001 and 0002
    assert m1["id"] == "0003"
    assert m1["title"] == "Enable distributed tracing seam"
    assert m1["target_bc"] == "telemetry"
    assert m1["external_ref"] == "https://github.com/org/repo/issues/101"

    assert m2["id"] == "0004"
    assert m2["title"] == "Configurable audit log rotation"
    assert m2["target_bc"] == "security"
    assert m2["external_ref"] == "https://github.com/org/repo/issues/102"


@then('appends the new tasks to "PRIORITY.md" without altering existing completed or refined entries.')
def then_appends_to_priority(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    priority_file = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    content = priority_file.read_text(encoding="utf-8")

    assert "- **TASK-0001 (Complete)**: [`0001-setup-project`](complete/0001-setup-project.md)" in content
    assert "- **TASK-0002 (Refined)**: [`0002-foundation-architecture`](refined/0002-foundation-architecture.md)" in content
    assert "- **TASK-0003 (Proposed)**:" in content
    assert "- **TASK-0004 (Proposed)**:" in content


@given('an issue export file "tickets.json" containing issue key, summary, description, and dependency links')
def given_tickets_json_file(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    tickets: list[dict[str, Any]] = []

    # 8 complete tasks (satisfying Definition of Ready: ADR, PRD, Story, BDD Gherkin, target_bc, mutation_scope)
    for i in range(1, 9):
        desc = (
            f"Specification for feature {i}.\n"
            "Governing ADR: ADR-0001\n"
            "Governing PRD: PRD-0001\n"
            "Governing Story: US-0001\n"
            "Persona: Taylor\n"
            "Target BC: core\n"
            "Mutation scope: src/spec_ops/core/\n\n"
            "```gherkin\n"
            f"Scenario: Test Scenario {i}\n"
            "Given initial state\n"
            "When action happens\n"
            "Then outcome is observed\n"
            "```\n"
        )
        deps = [f"JIRA-{i-1}"] if i > 1 else []
        tickets.append({
            "key": f"JIRA-{i}",
            "fields": {
                "summary": f"Ready Feature Task {i}",
                "description": desc,
                "components": [{"name": "core"}],
                "dependencies": deps,
            },
        })

    # 4 incomplete tasks (missing DoR criteria, e.g. missing Gherkin scenarios or ADRs)
    for i in range(9, 13):
        tickets.append({
            "key": f"JIRA-{i}",
            "fields": {
                "summary": f"Incomplete Ticket {i}",
                "description": "Vague task description without any DoR criteria.",
                "components": [{"name": "core"}],
                "dependencies": [f"JIRA-{i-1}"],
            },
        })

    tickets_file = repo / "tickets.json"
    tickets_file.write_text(json.dumps({"issues": tickets}, indent=2), encoding="utf-8")


@when('the product manager runs "spec-ops backlog import --file tickets.json"')
def when_run_backlog_import_file(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    res = run_spec_ops(repo, ["backlog", "import", "--file", "tickets.json"])
    assert res.returncode == 0, res.stderr
    bridge_context["cli_output"] = res.stdout


@then("SpecOps parses issue dependencies, mapping external keys to SpecOps canonical task IDs")
def then_parses_dependencies_mapping(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    # Find JIRA-2 task file (which depends on JIRA-1)
    file_jira2 = next((f for f in proposed_dir.glob("*.md") if "ready-feature-task-2" in f.name), None)
    assert file_jira2 is not None

    content = file_jira2.read_text(encoding="utf-8")
    # JIRA-1 was assigned TASK-0003 (after existing 0001 and 0002)
    assert "dependencies:\n- TASK-0003" in content


@then("runs the Definition of Ready validator on all imported tasks, flagging incomplete specifications")
def then_runs_dor_validator(bridge_context: dict[str, Any]) -> None:
    out = bridge_context["cli_output"]
    assert "ready for refinement" in out
    assert "requiring DoR completion" in out


@then('outputs an ingestion summary: "Imported 12 tasks (8 ready for refinement, 4 requiring DoR completion)".')
def then_outputs_ingestion_summary(bridge_context: dict[str, Any]) -> None:
    out = bridge_context["cli_output"]
    assert "Imported 12 tasks (8 ready for refinement, 4 requiring DoR completion)" in out


@given("a refined backlog with milestone assignments and completion timestamps")
def given_refined_backlog_with_milestones(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    backlog_dir = repo / "docs" / "project" / "backlog"
    roadmap_file = backlog_dir / "ROADMAP.md"
    roadmap_file.write_text(
        "# Product Delivery Roadmap\n\n"
        "## M1: Core Foundation (Active)\n"
        "- Horizon: Q1 2026\n"
        "- Target Tasks: TASK-0001, TASK-0002\n\n"
        "## M2: Integration Bridge (Planned)\n"
        "- Horizon: Q2 2026\n"
        "- Target Tasks: TASK-0003\n",
        encoding="utf-8",
    )


@when('the product manager executes "spec-ops backlog export --format markdown --out docs/reference/backlog-snapshot.md"')
def when_execute_backlog_export(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    res = run_spec_ops(repo, ["backlog", "export", "--format", "markdown", "--out", "docs/reference/backlog-snapshot.md"])
    assert res.returncode == 0, res.stderr
    bridge_context["cli_output"] = res.stdout


@then("SpecOps generates a structured Diataxis reference document displaying completion burn-up, buffer health, and milestone delivery estimates")
def then_generates_diataxis_reference_document(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    doc_path = repo / "docs" / "reference" / "backlog-snapshot.md"
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")

    assert "Reference: Backlog Status & Delivery Snapshot" in content
    assert "Completion Burn-up" in content
    assert "Buffer Health" in content
    assert "Milestone Delivery Estimates" in content
    assert "M1: Core Foundation" in content


@then("the document is ready for inclusion in executive stakeholder reviews.")
def then_document_ready_for_reviews(bridge_context: dict[str, Any]) -> None:
    repo = bridge_context["repo"]
    doc_path = repo / "docs" / "reference" / "backlog-snapshot.md"
    assert doc_path.stat().st_size > 100
