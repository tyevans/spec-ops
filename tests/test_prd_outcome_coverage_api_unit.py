"""Unit tests for PRD outcome coverage public API and HTTP dispatcher."""

from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading

import pytest

from spec_ops.config import SpecOpsConfig
from spec_ops.prd.outcome_coverage import PRDOutcomeCoverageEngine
from spec_ops.prd.outcome_coverage_api import (
    audit_prd_outcome_coverage_api,
    dispatch_outcome_coverage_api_request,
)
from spec_ops.visualizer.server import VisualizerHandler


@pytest.fixture
def repo_env(tmp_path: Path):
    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0003.md").write_text(
        """---
id: PRD-0003
title: Product Discovery
status: Accepted
target_persona: Taylor
---
# PRD-0003
## Checkable Outcomes
- Live PRD Studio
- Living UAT Coverage
""",
        encoding="utf-8",
    )
    return tmp_path


def test_api_functional_single_valid(repo_env: Path):
    res = audit_prd_outcome_coverage_api("PRD-0003", repo_root=repo_env)
    assert res["success"] is True
    assert res["total_prds"] == 1
    assert len(res["reports"]) == 1
    assert res["reports"][0]["prd_id"] == "PRD-0003"


def test_api_functional_nonexistent(repo_env: Path):
    res = audit_prd_outcome_coverage_api("PRD-NONEXISTENT", repo_root=repo_env)
    assert res["success"] is False
    assert "not found" in res["error"].lower()


def test_api_functional_all(repo_env: Path):
    res = audit_prd_outcome_coverage_api(repo_root=repo_env)
    assert res["success"] is True
    assert res["total_prds"] == 1
    assert len(res["reports"]) == 1


def test_dispatch_get_valid(repo_env: Path):
    engine = PRDOutcomeCoverageEngine(repo_root=repo_env)
    code, res = dispatch_outcome_coverage_api_request(
        engine,
        "GET",
        "/api/prd/coverage/outcomes",
        query_params={"prd": ["PRD-0003"]},
    )
    assert code == 200
    assert res["success"] is True
    assert res["total_prds"] == 1


def test_dispatch_post_valid(repo_env: Path):
    engine = PRDOutcomeCoverageEngine(repo_root=repo_env)
    code, res = dispatch_outcome_coverage_api_request(
        engine,
        "POST",
        "/api/prd/coverage/outcomes",
        payload={"prd_id": "PRD-0003"},
    )
    assert code == 200
    assert res["success"] is True


def test_dispatch_not_found_route(repo_env: Path):
    engine = PRDOutcomeCoverageEngine(repo_root=repo_env)
    code, res = dispatch_outcome_coverage_api_request(
        engine,
        "GET",
        "/api/prd/unknown-route",
    )
    assert code == 404
    assert res["success"] is False


def test_dispatch_method_not_allowed(repo_env: Path):
    engine = PRDOutcomeCoverageEngine(repo_root=repo_env)
    code, res = dispatch_outcome_coverage_api_request(
        engine,
        "DELETE",
        "/api/prd/coverage/outcomes",
    )
    assert code == 405
    assert res["success"] is False


def test_server_http_frontdoor(repo_env: Path):
    """Verifies HTTP server frontdoor without mock backdoors."""
    config = SpecOpsConfig(root_dir=repo_env)
    handler = VisualizerHandler
    handler.config = config
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        conn = HTTPConnection(host, port, timeout=5)
        # Test GET /api/prd/coverage/outcomes?prd=PRD-0003
        conn.request("GET", "/api/prd/coverage/outcomes?prd=PRD-0003")
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read().decode("utf-8"))
        assert body["success"] is True
        assert body["total_prds"] == 1
        assert body["reports"][0]["prd_id"] == "PRD-0003"
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
