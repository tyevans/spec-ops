"""Executable benchmark and validation suite for SPIKE-0038.

Hypothesis: A zero-dependency vanilla JS/CSS web PRD studio embedded in Python's
http.server delivers <100ms interaction latency, real-time Diataxis markdown preview,
instant client-side YAML validation, and reliable git commit synchronization without
requiring Node.js/npm dependencies or external CDN resources.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from spec_ops.prd.step_assistant import detect_backdoors, extract_frontdoor_steps
from spec_ops.prd.studio import (
    create_prd_draft,
    parse_prd_document,
    serialize_prd_document,
    validate_prd_schema,
)
from spec_ops.visualizer.studio_view import render_studio_html

from spikes.spike_0038.harness import record_findings, run_benchmark


def test_hypothesis_benchmark(tmp_path: Path):
    """Asserts that local studio HTTP endpoints and git operations achieve <100ms p95 latency."""
    harness_dir = Path(__file__).parent
    results = run_benchmark(iterations=20, repo_root=Path.cwd())

    # Record findings to disk for ADR graduation
    findings_str = results["findings"]
    record_findings(harness_dir, findings_str)

    assert results["status"] == "completed"
    assert results["p95_latency_ms"] < 100.0, f"p95 latency was {results['p95_latency_ms']}ms, exceeding 100ms"
    assert results["avg_draft_ms"] < 50.0
    assert results["avg_frontdoor_ms"] < 50.0


def test_zero_external_npm_or_cdn_dependencies():
    """Asserts that PRD Studio operates with 0 npm dependencies and 0 external CDN requests."""
    html = render_studio_html()

    # Must not contain external http/https script or link tags
    assert "src=\"http" not in html
    assert "href=\"http" not in html
    assert "cdn.jsdelivr" not in html
    assert "cdnjs.cloudflare" not in html
    assert "unpkg.com" not in html

    # Confirm pure browser-native implementation
    assert "<script>" in html
    assert "<style>" in html
    assert "parseMarkdown" in html


def test_schema_quality_invariant_and_falsifiability():
    """Validates that drafts without checkable outcomes or unmapped personas are rejected citing ADR-0001."""
    # 1. Missing outcomes
    bad_payload_1 = {
        "title": "Unfalsifiable PRD",
        "persona": "Taylor",
        "problem_statement": "Some issue",
        "outcomes": [],
    }
    valid, violations = validate_prd_schema(bad_payload_1)
    assert not valid
    assert any("ADR-0001" in v or "outcome" in v.lower() for v in violations)

    # 2. Unmapped persona
    bad_payload_2 = {
        "title": "PRD with Unknown Persona",
        "persona": "UnregisteredUser",
        "problem_statement": "Some issue",
        "outcomes": ["Valid outcome"],
    }
    valid2, violations2 = validate_prd_schema(bad_payload_2)
    assert not valid2
    assert any("persona" in v.lower() for v in violations2)


def test_frontdoor_fixture_autocomplete_and_backdoor_detection():
    """Asserts that established fixtures are discoverable and private backdoors are flagged."""
    steps = extract_frontdoor_steps(Path.cwd())
    assert len(steps) >= 3

    patterns = [s["pattern"] for s in steps]
    assert "Given a project initialized with SpecOps" in patterns
    assert "Given the standalone visualizer is open in a browser" in patterns

    # Backdoor pattern detection
    is_bd, warn, alt = detect_backdoors("Given the database table users has record 'admin'")
    assert is_bd is True
    assert "Backdoor violation (ADR-0003)" in warn
    assert len(alt) > 0

    # Non-backdoor step
    is_bd2, warn2, _ = detect_backdoors("Given a project initialized with SpecOps")
    assert is_bd2 is False
    assert warn2 == ""
