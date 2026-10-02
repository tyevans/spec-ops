"""Unit tests for PRD Lint UI, Component Stories, and Server endpoints."""

from __future__ import annotations

from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading

import pytest

from spec_ops.config import SpecOpsConfig
from spec_ops.prd.lint_ui import LINT_COMPONENT_STORIES, render_lint_html
from spec_ops.visualizer.server import VisualizerHandler


def test_lint_component_stories_structure():
    assert len(LINT_COMPONENT_STORIES) >= 5
    required_keys = ["PRDLintSummaryCard", "PRDDiagnosticItem", "LineLevelSuggestionCard", "RemediationDiffModal", "LintFilterToolbar"]
    for key in required_keys:
        assert key in LINT_COMPONENT_STORIES
        story = LINT_COMPONENT_STORIES[key]
        assert "title" in story
        assert "description" in story
        assert isinstance(story["props"], list)
        assert len(story["props"]) > 0
        assert isinstance(story["default_state"], dict)


def test_render_lint_html_default():
    html = render_lint_html()
    assert "<!DOCTYPE html>" in html
    assert "SpecOps PRD Quality & Lint Dashboard" in html
    assert "PRDLintSummaryCard" in html
    assert "switchView('audit')" in html


def test_render_lint_html_custom_data():
    sample_reports = [
        {
            "file_path": "docs/project/product/idea/prd-0010.md",
            "is_valid": True,
            "error_count": 0,
            "warning_count": 0,
            "falsifiable_count": 3,
            "unfalsifiable_count": 0,
            "diagnostics": [],
        }
    ]
    html = render_lint_html(reports=sample_reports, title="Custom Lint Suite")
    assert "Custom Lint Suite" in html
    assert "prd-0010.md" in html


def test_render_lint_html_custom_stories():
    custom_stories = {
        "TestCard": {
            "title": "Custom Test Card",
            "description": "Testing custom injection",
            "props": ["test_prop"],
            "default_state": {"test_prop": 123},
        }
    }
    html = render_lint_html(stories=custom_stories)
    assert "Custom Test Card" in html
    assert "TestCard" in html


def test_server_lint_ui_endpoints(tmp_path: Path):
    """Verifies blackbox frontdoor HTTP rendering for /prd-lint and /lint."""
    config = SpecOpsConfig(root_dir=tmp_path)
    handler = VisualizerHandler
    handler.config = config
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    host, port = server.server_address

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        conn = HTTPConnection(host, port, timeout=5)
        # Test 1: GET /prd-lint
        conn.request("GET", "/prd-lint")
        resp1 = conn.getresponse()
        assert resp1.status == 200
        assert "text/html" in resp1.getheader("Content-Type", "")
        content1 = resp1.read().decode("utf-8")
        assert "<!DOCTYPE html>" in content1
        assert "PRD Quality & Lint Dashboard" in content1

        # Test 2: GET /lint
        conn.request("GET", "/lint")
        resp2 = conn.getresponse()
        assert resp2.status == 200
        content2 = resp2.read().decode("utf-8")
        assert "<!DOCTYPE html>" in content2

        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
