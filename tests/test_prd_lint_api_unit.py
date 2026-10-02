"""Unit tests for PRD Lint Public API and Request Dispatcher."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from spec_ops.prd.lint_api import dispatch_lint_api_request, lint_prd_api
from spec_ops.prd.lint_engine import PRDLintEngine
from spec_ops.visualizer.server import VisualizerHandler
from spec_ops.config import SpecOpsConfig


@pytest.fixture
def prd_env(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "project" / "product"
    idea_dir = docs_dir / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)

    prd_content = """---
id: PRD-0050
title: Sample Feature
status: Idea
target_persona: Alex
component: prd
---

# PRD-0050: Sample Feature

## Problem Statement
A sample problem.

## What good looks like
Fast and responsive UI.

## What this does not do
Does not introduce delay.

## Checkable Outcomes
- The response time is ultra fast
- Memory usage is kept low
"""
    (idea_dir / "prd-0050-sample-feature.md").write_text(prd_content, encoding="utf-8")
    return tmp_path


def test_lint_prd_api_all(prd_env: Path):
    res = lint_prd_api(repo_root=prd_env)
    assert res["success"] is True
    assert res["total_files"] == 1
    assert len(res["reports"]) == 1
    assert "prd-0050" in res["reports"][0]["file_path"].lower()


def test_lint_prd_api_single_valid(prd_env: Path):
    res = lint_prd_api("PRD-0050", repo_root=prd_env)
    assert res["success"] is True
    assert res["total_files"] == 1
    assert len(res["reports"]) == 1


def test_lint_prd_api_not_found(prd_env: Path):
    res = lint_prd_api("PRD-9999", repo_root=prd_env)
    assert res["success"] is False
    assert "not found" in res["error"]
    assert res["total_files"] == 0


def test_dispatch_get_lint_query_param(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    code, res = dispatch_lint_api_request(
        engine,
        "GET",
        "/api/prd/lint",
        query_params={"prd": ["PRD-0050"]},
    )
    assert code == 200
    assert res["success"] is True
    assert len(res["reports"]) == 1


def test_dispatch_get_lint_not_found(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    code, res = dispatch_lint_api_request(
        engine,
        "GET",
        "/api/prd/lint",
        query_params={"prd": ["PRD-NONEXISTENT"]},
    )
    assert code == 400
    assert res["success"] is False


def test_dispatch_get_unknown_route(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    code, res = dispatch_lint_api_request(engine, "GET", "/api/prd/unknown")
    assert code == 404
    assert res["success"] is False


def test_dispatch_post_lint_content(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    content = """---
id: PRD-0051
title: Direct
status: Idea
target_persona: Alex
---
# PRD-0051
## Problem Statement
P
## What good looks like
G
## What this does not do
N
## Checkable Outcomes
- Fast response
"""
    code, res = dispatch_lint_api_request(
        engine,
        "POST",
        "/api/prd/lint",
        payload={"content": content},
    )
    assert code == 200
    assert res["success"] is True
    assert "report" in res


def test_dispatch_post_lint_path(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    code, res = dispatch_lint_api_request(
        engine,
        "POST",
        "/api/prd/lint",
        payload={"prd_id": "PRD-0050"},
    )
    assert code == 200
    assert res["success"] is True


def test_dispatch_post_remediate(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    content = """---
id: PRD-0052
title: Needs Remediation
status: Idea
target_persona: Alex
---
# PRD-0052
## Problem Statement
P
## What good looks like
G
## What this does not do
N
## Checkable Outcomes
- Fast and seamless experience
"""
    code, res = dispatch_lint_api_request(
        engine,
        "POST",
        "/api/prd/lint/remediate",
        payload={"content": content},
    )
    assert code == 200
    assert res["success"] is True
    assert res["applied_count"] >= 1
    assert "fast" not in res["remediated_content"].lower()


def test_dispatch_post_remediate_empty(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    code, res = dispatch_lint_api_request(
        engine,
        "POST",
        "/api/prd/lint/remediate",
        payload={},
    )
    assert code == 400
    assert res["success"] is False


def test_dispatch_post_unknown_route(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    code, res = dispatch_lint_api_request(engine, "POST", "/api/prd/unknown", payload={})
    assert code == 404
    assert res["success"] is False


def test_dispatch_method_not_allowed(prd_env: Path):
    engine = PRDLintEngine(root_dir=prd_env)
    code, res = dispatch_lint_api_request(engine, "DELETE", "/api/prd/lint")
    assert code == 405
    assert res["success"] is False


def test_server_http_frontdoor(prd_env: Path):
    """Verifies public HTTP server frontdoor without mock backdoors."""
    config = SpecOpsConfig(root_dir=prd_env)
    handler = VisualizerHandler
    handler.config = config
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        conn = HTTPConnection(host, port, timeout=5)
        # 1. Test GET /api/prd/lint
        conn.request("GET", "/api/prd/lint")
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read().decode("utf-8"))
        assert body["success"] is True
        assert body["total_files"] == 1

        # 2. Test POST /api/prd/lint/remediate
        post_data = json.dumps({"content": "---\nid: PRD-0099\nstatus: Idea\ntarget_persona: Alex\n---\n# PRD-0099\n## Problem Statement\nP\n## What good looks like\nG\n## What this does not do\nN\n## Checkable Outcomes\n- Super fast loading\n"})
        conn.request("POST", "/api/prd/lint/remediate", body=post_data, headers={"Content-Type": "application/json"})
        resp2 = conn.getresponse()
        assert resp2.status == 200
        body2 = json.loads(resp2.read().decode("utf-8"))
        assert body2["success"] is True
        assert body2["applied_count"] >= 1
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
