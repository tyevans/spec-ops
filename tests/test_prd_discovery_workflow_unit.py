"""Unit tests for continuous product discovery and living PRD synthesis workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
import pytest

from spec_ops.cli.main import build_parser
from spec_ops.cli.prd_handler import handle_prd_command
from spec_ops.config.models import (
    ArchitectureSettings,
    ProjectSettings,
    QualitySettings,
    SpecOpsConfig,
)
from spec_ops.core.parser import extract_frontmatter
from spec_ops.prd.discovery_workflow import (
    discover_prd,
    parse_outcomes_input,
    shape_prd,
)
from spec_ops.prd.lifecycle import PRDLifecycleManager


@pytest.fixture
def workflow_config(tmp_path: Path) -> SpecOpsConfig:
    """Fixture providing clean temporary configuration for discovery tests."""
    return SpecOpsConfig(
        root_dir=tmp_path,
        project=ProjectSettings(name="DiscoveryApp"),
        architecture=ArchitectureSettings(),
        quality=QualitySettings(),
    )


def test_parse_outcomes_input_variants(tmp_path: Path):
    """Test outcome parsing from strings, lists, and files."""
    # 1. Comma-separated string
    res = parse_outcomes_input("1. First outcome, 2. Second outcome, - Third outcome")
    assert res == ["First outcome", "Second outcome", "Third outcome"]

    # 2. Newline-separated string
    res2 = parse_outcomes_input("1. Alpha\n2. Beta\n* Gamma")
    assert res2 == ["Alpha", "Beta", "Gamma"]

    # 3. Semicolon-separated string
    res3 = parse_outcomes_input("Alpha; Beta; Gamma")
    assert res3 == ["Alpha", "Beta", "Gamma"]

    # 4. List of strings
    res4 = parse_outcomes_input(["1. One", "Two", "- Three"])
    assert res4 == ["One", "Two", "Three"]

    # 5. File path
    f = tmp_path / "outcomes.txt"
    f.write_text("1. File outcome A\n2. File outcome B\n3. File outcome C\n", encoding="utf-8")
    res5 = parse_outcomes_input(f)
    assert res5 == ["File outcome A", "File outcome B", "File outcome C"]

    # 6. Empty / comments
    res6 = parse_outcomes_input("<!-- comment -->\n\n1. Valid")
    assert res6 == ["Valid"]


def test_discover_prd_defaults(workflow_config: SpecOpsConfig):
    """Test discovering and scaffolding a PRD with default values."""
    prd_path = discover_prd(workflow_config, non_interactive=True)
    assert prd_path.exists()
    assert prd_path.parent == workflow_config.prd_dir / "idea"
    assert prd_path.name.startswith("prd-0001-")

    content = prd_path.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)
    assert meta["id"] == "0001"
    assert meta["status"] == "Idea"
    assert meta["target_persona"] == "Alex (The Agentic Systems Architect)" or "Taylor" in meta["target_persona"]
    assert meta["component"] == "core"

    # Verify registration in REGISTRY.md
    registry = workflow_config.prd_dir / "REGISTRY.md"
    assert registry.exists()
    reg_text = registry.read_text(encoding="utf-8")
    assert "`PRD-0001`" in reg_text
    assert "Idea" in reg_text


def test_discover_prd_explicit_and_monotonic(workflow_config: SpecOpsConfig):
    """Test discover_prd with explicit flags and monotonic ID allocation."""
    # First discovery
    p1 = discover_prd(
        workflow_config,
        title="Automated Telemetry",
        persona="Jordan (The AI-Native Engineering Lead)",
        bc="telemetry",
        summary="Engineers lack real-time fleet observability.",
        non_interactive=True,
    )
    assert p1.name == "prd-0001-automated-telemetry.md"

    # Second discovery should auto-increment to PRD-0002
    p2 = discover_prd(
        workflow_config,
        title="Zero Trust Gateway",
        persona="Sasha (The Trust & Security Officer)",
        bc="security",
        summary="Worktrees lack secure proxy verification.",
        non_interactive=True,
    )
    assert p2.name == "prd-0002-zero-trust-gateway.md"

    meta2, _ = extract_frontmatter(p2.read_text(encoding="utf-8"))
    assert meta2["id"] == "0002"
    assert meta2["target_persona"] == "Sasha (The Trust & Security Officer)"
    assert meta2["component"] == "security"

    registry = (workflow_config.prd_dir / "REGISTRY.md").read_text(encoding="utf-8")
    assert "`PRD-0001`" in registry
    assert "`PRD-0002`" in registry


def test_shape_prd_missing_file(workflow_config: SpecOpsConfig):
    """Test shaping a non-existent PRD fails gracefully."""
    ok, msg = shape_prd(workflow_config, "PRD-9999")
    assert not ok
    assert "PRD not found" in msg


def test_shape_prd_unmapped_persona(workflow_config: SpecOpsConfig):
    """Test shaping a PRD with unmapped persona is blocked."""
    idea_dir = workflow_config.prd_dir / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    f = idea_dir / "prd-0001-flawed.md"
    f.write_text(
        "---\n"
        "id: '0001'\n"
        "title: Flawed Spec\n"
        "status: Idea\n"
        "target_persona: 'unmapped'\n"
        "component: core\n"
        "---\n"
        "# PRD-0001\n"
        "## Who this is for\n- Context\n"
        "## What good looks like\n1. Core\n"
        "## What this does not do\n- None\n"
        "## Checkable Outcomes\n1. Outcome 1\n",
        encoding="utf-8",
    )
    ok, msg = shape_prd(workflow_config, "PRD-0001")
    assert not ok
    assert "target persona is unmapped" in msg


def test_shape_prd_missing_pain_points(workflow_config: SpecOpsConfig):
    """Test shaping a PRD missing user pain points is blocked."""
    idea_dir = workflow_config.prd_dir / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    f = idea_dir / "prd-0001-nopain.md"
    f.write_text(
        "---\n"
        "id: '0001'\n"
        "title: No Pain Spec\n"
        "status: Idea\n"
        "target_persona: Taylor (The Product Manager)\n"
        "component: core\n"
        "---\n"
        "# PRD-0001\n"
        "## What good looks like\n1. Core\n"
        "## What this does not do\n- None\n"
        "## Checkable Outcomes\n1. Outcome 1\n",
        encoding="utf-8",
    )
    ok, msg = shape_prd(workflow_config, "PRD-0001")
    assert not ok
    assert "must define user pain points" in msg


def test_shape_prd_insufficient_outcomes_error(workflow_config: SpecOpsConfig):
    """Test shaping with fewer than 3 outcomes is blocked."""
    discover_prd(workflow_config, title="Telemetry", non_interactive=True)
    ok, msg = shape_prd(
        workflow_config,
        "PRD-0001",
        outcomes="1. Only one single outcome",
    )
    assert not ok
    assert "requires at least 3 checkable outcomes (found 1)" in msg


def test_shape_prd_unfalsifiable_outcomes_error(workflow_config: SpecOpsConfig):
    """Test shaping with unfalsifiable outcomes is blocked by the falsifiability gate."""
    discover_prd(workflow_config, title="Telemetry", non_interactive=True)
    ok, msg = shape_prd(
        workflow_config,
        "PRD-0001",
        outcomes="The app has a clean and modern design, The UI is noticeably faster, Seamless workflow",
    )
    assert not ok
    assert "unfalsifiable" in msg.lower() or "blocked" in msg.lower()


def test_shape_prd_synthesizes_default_outcomes_and_promotes_shaped(workflow_config: SpecOpsConfig):
    """Test shaping an idea without explicit outcomes generates defaults and promotes to shaped."""
    discover_prd(workflow_config, title="Telemetry", non_interactive=True)
    ok, msg = shape_prd(workflow_config, "PRD-0001")
    assert ok
    assert "Successfully promoted PRD-0001 to 'shaped'" in msg

    shaped_file = workflow_config.prd_dir / "shaped" / "prd-0001-telemetry.md"
    assert shaped_file.exists()
    assert not (workflow_config.prd_dir / "idea" / "prd-0001-telemetry.md").exists()

    content = shaped_file.read_text(encoding="utf-8")
    assert "status: Shaped" in content
    # Should have synthesized at least 3 checkable outcomes
    assert "1. " in content and "2. " in content and "3. " in content

    # Registry must reflect Shaped
    reg = (workflow_config.prd_dir / "REGISTRY.md").read_text(encoding="utf-8")
    assert "| `PRD-0001` | Telemetry | Shaped |" in reg


def test_shape_prd_accept_promotion(workflow_config: SpecOpsConfig):
    """Test shaping with --accept promotes directly to accepted stage."""
    discover_prd(workflow_config, title="Telemetry", non_interactive=True)
    outcomes = [
        "Running 'spec-ops telemetry --json' returns exit code 0 and valid telemetry payload.",
        "Verification suite passes with 100% frontdoor contract assertions.",
        "Fleet console reflects worker state transitions in component telemetry.",
    ]
    ok, msg = shape_prd(
        workflow_config,
        "PRD-0001",
        outcomes=outcomes,
        anti_goals="Does not bypass CLI frontdoors, Does not modify database schema directly",
        accept=True,
    )
    assert ok
    assert "Successfully promoted PRD-0001 to 'accepted'" in msg

    accepted_file = workflow_config.prd_dir / "accepted" / "prd-0001-telemetry.md"
    assert accepted_file.exists()
    content = accepted_file.read_text(encoding="utf-8")
    assert "status: Accepted" in content
    assert "Does not bypass CLI frontdoors" in content
    assert "Fleet console reflects worker state transitions" in content

    reg = (workflow_config.prd_dir / "REGISTRY.md").read_text(encoding="utf-8")
    assert "| `PRD-0001` | Telemetry | Accepted |" in reg


def test_shape_prd_sequential_lifecycle(workflow_config: SpecOpsConfig):
    """Test moving PRD idea -> shaped -> accepted across subsequent shape calls."""
    discover_prd(workflow_config, title="Artifact Engine", non_interactive=True)

    # 1. From idea -> shaped
    ok1, msg1 = shape_prd(workflow_config, "PRD-0001")
    assert ok1
    assert "shaped" in msg1

    # 2. From shaped -> accepted (default when already in shaped)
    ok2, msg2 = shape_prd(workflow_config, "PRD-0001")
    assert ok2
    assert "accepted" in msg2

    accepted_file = workflow_config.prd_dir / "accepted" / "prd-0001-artifact-engine.md"
    assert accepted_file.exists()


def test_cli_prd_discover_and_shape_frontdoors(workflow_config: SpecOpsConfig, monkeypatch: pytest.MonkeyPatch):
    """Test full CLI dispatching for discover and shape subcommands."""
    parser = build_parser()

    # 1. CLI discover
    args_disc = parser.parse_args([
        "prd", "discover",
        "--title", "Audit Pipeline",
        "--persona", "Sasha (The Trust & Security Officer)",
        "--bc", "audit",
        "--summary", "Auditors lack verifiable Merkle compliance trees.",
        "--non-interactive",
    ])
    code = handle_prd_command(args_disc, workflow_config, parser)
    assert code == 0

    idea_file = workflow_config.prd_dir / "idea" / "prd-0001-audit-pipeline.md"
    assert idea_file.exists()

    # 2. CLI shape with --accept
    args_shape = parser.parse_args([
        "prd", "shape",
        "--id", "PRD-0001",
        "--outcomes", "Audit CLI emits JSON report, Cryptographic tree verifies root hash, Invariant gate enforces zero drift",
        "--anti-goals", "No secret backdoor access",
        "--accept",
    ])
    code_shape = handle_prd_command(args_shape, workflow_config, parser)
    assert code_shape == 0

    accepted_file = workflow_config.prd_dir / "accepted" / "prd-0001-audit-pipeline.md"
    assert accepted_file.exists()

    # 3. CLI shape missing ID
    args_bad = parser.parse_args(["prd", "shape"])
    code_bad = handle_prd_command(args_bad, workflow_config, parser)
    assert code_bad == 1
