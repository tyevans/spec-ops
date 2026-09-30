"""Blackbox frontdoor tests for PRD Studio HTTP API endpoints and git synchronization."""

from __future__ import annotations

import json
import subprocess
import threading
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path

import pytest
from spec_ops.config.models import SpecOpsConfig
from spec_ops.visualizer.server import VisualizerHandler


@pytest.fixture
def running_server(tmp_path: Path):
    """Spins up a lightweight local test server on a free port."""
    # Initialize a dummy git repo in tmp_path to test real git commit writebacks
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@specops.local"], cwd=tmp_path, capture_output=True)

    config = SpecOpsConfig(
        root_dir=tmp_path,
    )

    class CustomHandler(VisualizerHandler):
        pass

    CustomHandler.config = config
    server = HTTPServer(("127.0.0.1", 0), CustomHandler)
    port = server.server_port

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    yield f"127.0.0.1:{port}", tmp_path

    server.shutdown()
    server.server_close()


def test_frontdoor_steps_endpoint(running_server):
    """Asserts GET /api/steps/frontdoor returns established frontdoor fixtures."""
    addr, _ = running_server
    host, port = addr.split(":")
    conn = HTTPConnection(host, int(port))

    conn.request("GET", "/api/steps/frontdoor")
    res = conn.getresponse()
    assert res.status == 200
    assert res.getheader("Content-Type") == "application/json"

    data = json.loads(res.read().decode("utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 3

    patterns = [s["pattern"] for s in data]
    assert "Given a project initialized with SpecOps" in patterns
    assert "Given the standalone visualizer is open in a browser" in patterns
    conn.close()


def test_frontdoor_steps_filter_query(running_server):
    """Asserts GET /api/steps/frontdoor?q=visualizer filters by query term."""
    addr, _ = running_server
    host, port = addr.split(":")
    conn = HTTPConnection(host, int(port))

    conn.request("GET", "/api/steps/frontdoor?q=visualizer")
    res = conn.getresponse()
    assert res.status == 200

    data = json.loads(res.read().decode("utf-8"))
    assert len(data) >= 1
    assert all("visualizer" in s["pattern"].lower() or "visualizer" in s.get("domain", "").lower() for s in data)
    conn.close()


def test_create_prd_draft_endpoint(running_server):
    """Asserts POST /api/prd/draft scaffolds a new PRD document in docs/project/product/idea/."""
    addr, root_dir = running_server
    host, port = addr.split(":")
    conn = HTTPConnection(host, int(port))

    payload = {
        "title": "Self-Service Customer Billing Portal",
        "persona": "Alex",
        "component": "billing",
        "problem_statement": "Customers cannot update payment methods self-serve",
        "outcomes": [
            "User updates credit card via web dashboard",
            "Stripe webhook confirms card update with 200 OK",
        ],
    }

    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", "/api/prd/draft", body=body, headers={"Content-Type": "application/json"})
    res = conn.getresponse()

    assert res.status == 201
    data = json.loads(res.read().decode("utf-8"))
    assert data["success"] is True
    assert "PRD-" in data["prd_id"]
    assert "docs/project/product/idea/" in data["file_path"]

    created_file = root_dir / data["file_path"]
    assert created_file.exists()
    content = created_file.read_text(encoding="utf-8")
    assert "status: Idea" in content
    assert "target_persona: Alex" in content
    assert "Self-Service Customer Billing Portal" in content
    assert "Stripe webhook confirms card update with 200 OK" in content
    conn.close()


def test_create_prd_draft_validation_failure(running_server):
    """Asserts POST /api/prd/draft rejects invalid schema citing ADR-0001."""
    addr, _ = running_server
    host, port = addr.split(":")
    conn = HTTPConnection(host, int(port))

    # Missing checkable outcomes
    bad_payload = {
        "title": "Bad PRD Without Outcomes",
        "persona": "Alex",
        "problem_statement": "Missing outcomes",
        "outcomes": [],
    }

    body = json.dumps(bad_payload).encode("utf-8")
    conn.request("POST", "/api/prd/draft", body=body, headers={"Content-Type": "application/json"})
    res = conn.getresponse()

    assert res.status == 400
    data = json.loads(res.read().decode("utf-8"))
    assert data["success"] is False
    assert "ADR-0001" in data.get("error", "") or any("ADR-0001" in v for v in data.get("violations", []))
    conn.close()


def test_commit_prd_specification_endpoint(running_server):
    """Asserts POST /api/prd/commit records specification edits directly to git."""
    addr, root_dir = running_server
    host, port = addr.split(":")
    conn = HTTPConnection(host, int(port))

    # First, create a draft
    draft_payload = {
        "title": "Git Commit Test PRD",
        "persona": "Taylor",
        "component": "studio",
        "problem_statement": "Initial problem statement",
        "outcomes": ["Outcome 1"],
    }
    body = json.dumps(draft_payload).encode("utf-8")
    conn.request("POST", "/api/prd/draft", body=body, headers={"Content-Type": "application/json"})
    res1 = conn.getresponse()
    assert res1.status == 201
    draft_data = json.loads(res1.read().decode("utf-8"))
    file_path = draft_data["file_path"]

    # Initial commit to create a git root commit
    subprocess.run(["git", "add", "."], cwd=root_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=root_dir, capture_output=True)

    # Now update and commit via API
    updated_content = draft_data["content"] + "\n## Extra Notes\nUpdated problem statement.\n"
    commit_payload = {
        "file_path": file_path,
        "content": updated_content,
        "commit_message": "spec(prd): update problem statement for Git Commit Test PRD",
        "author_name": "Taylor",
        "author_email": "taylor@specops.local",
    }

    conn.request("POST", "/api/prd/commit", body=json.dumps(commit_payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    res2 = conn.getresponse()

    assert res2.status == 200
    commit_data = json.loads(res2.read().decode("utf-8"))
    assert commit_data["success"] is True
    assert len(commit_data["commit_hash"]) > 0
    assert commit_data["latency_ms"] >= 0

    # Verify git log shows the commit
    log_res = subprocess.run(["git", "log", "-n", "1", "--format=%an <%ae> %s"], cwd=root_dir, capture_output=True, text=True)
    assert "Taylor <taylor@specops.local>" in log_res.stdout
    assert "update problem statement" in log_res.stdout
    conn.close()


def test_prd_studio_html_view(running_server):
    """Asserts GET /prd-studio serves zero-dependency standalone HTML."""
    addr, _ = running_server
    host, port = addr.split(":")
    conn = HTTPConnection(host, int(port))

    conn.request("GET", "/prd-studio")
    res = conn.getresponse()
    assert res.status == 200
    assert "text/html" in res.getheader("Content-Type")

    html = res.read().decode("utf-8")
    assert "<!DOCTYPE html>" in html
    assert "SpecOps PRD Studio" in html
    assert "parseMarkdown" in html
    assert "cdn.jsdelivr" not in html
    conn.close()
