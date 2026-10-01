"""Hypothesis generative property-based tests for PRD discovery and shaping workflow (ADR-0009)."""

from __future__ import annotations

from pathlib import Path
from hypothesis import given, settings, strategies as st

from spec_ops.config.models import (
    ArchitectureSettings,
    ProjectSettings,
    QualitySettings,
    SpecOpsConfig,
)
from spec_ops.core.parser import extract_frontmatter
from spec_ops.prd.discovery import parse_available_personas
from spec_ops.prd.discovery_workflow import discover_prd, shape_prd
from spec_ops.prd.linter import SUBJECTIVE_WORDS

FALSIFIABLE_OUTCOMES_POOL = [
    "Running CLI command spec-ops telemetry returns exit code 0 and valid JSON.",
    "Worker fleet heartbeats update in memory every 10 seconds without latency spikes.",
    "Preflight scanner flags prohibited credentials before git commit creation.",
    "Verification test suite achieves 100% blackbox assertion pass rate.",
    "Relational knowledge graph compiles Tarjan SCC cycles in under 250ms.",
    "Tamper-evident Merkle compliance tree verifies root hash against local head.",
    "Audit export writes cryptographically signed manifest to docs/project/audit.",
    "Subagent worktree sandboxing enforces write isolation across git worktrees.",
]

PERSONAS = [
    "Alex (The Agentic Systems Architect)",
    "Jordan (The AI-Native Engineering Lead)",
    "Morgan (The Autonomous Coding Agent)",
    "Riley (The Human IC Developer)",
    "Taylor (The Product Manager)",
    "Sasha (The Trust & Security Officer)",
]


@settings(max_examples=25, deadline=15000)
@given(
    title=st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ", min_size=5, max_size=35),
    persona=st.sampled_from(PERSONAS),
    bc=st.sampled_from(["core", "backlog", "prd", "security", "telemetry", "visualizer"]),
    summary=st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,", min_size=10, max_size=60),
)
def test_property_discover_prd_state_consistency(
    tmp_path_factory,
    title: str,
    persona: str,
    bc: str,
    summary: str,
):
    """Property invariant: discover_prd unconditionally produces a valid PRD draft,

    monotonically assigned PRD ID, and atomic registration in REGISTRY.md.
    """
    tmp_path = tmp_path_factory.mktemp("disc_prop")
    config = SpecOpsConfig(
        root_dir=tmp_path,
        project=ProjectSettings(name="PropApp"),
        architecture=ArchitectureSettings(),
        quality=QualitySettings(),
    )

    clean_title = title.strip() or "Standard Capability"
    clean_summary = summary.strip() or "Standard problem statement"

    prd_path = discover_prd(
        config,
        title=clean_title,
        persona=persona,
        bc=bc,
        summary=clean_summary,
        non_interactive=True,
    )

    assert prd_path.exists()
    assert prd_path.parent == config.prd_dir / "idea"
    assert prd_path.name.startswith("prd-0001-")

    content = prd_path.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)
    assert meta["id"] == "0001"
    assert meta["status"] == "Idea"
    assert meta["target_persona"] == persona
    assert meta["component"] == bc

    reg_content = (config.prd_dir / "REGISTRY.md").read_text(encoding="utf-8")
    assert "| `PRD-0001` |" in reg_content
    assert "| Idea |" in reg_content
    assert persona in reg_content


@settings(max_examples=20, deadline=15000)
@given(
    outcome_indices=st.lists(
        st.integers(min_value=0, max_value=len(FALSIFIABLE_OUTCOMES_POOL) - 1),
        min_size=3,
        max_size=6,
        unique=True,
    ),
    stage=st.sampled_from(["shaped", "accepted"]),
)
def test_property_shape_prd_falsifiable_outcomes_invariant(
    tmp_path_factory,
    outcome_indices: list[int],
    stage: str,
):
    """Property invariant: shaping with arbitrary combinations of >= 3 falsifiable outcomes

    preserves all checkable outcomes, updates status, and transitions the PRD cleanly.
    """
    tmp_path = tmp_path_factory.mktemp("shape_prop")
    config = SpecOpsConfig(
        root_dir=tmp_path,
        project=ProjectSettings(name="ShapePropApp"),
        architecture=ArchitectureSettings(),
        quality=QualitySettings(),
    )

    discover_prd(
        config,
        title="Predictive Diagnostics",
        persona="Jordan (The AI-Native Engineering Lead)",
        bc="telemetry",
        summary="Engineers lack early fault warnings.",
        non_interactive=True,
    )

    chosen_outcomes = [FALSIFIABLE_OUTCOMES_POOL[i] for i in outcome_indices]
    accept_flag = (stage == "accepted")

    ok, msg = shape_prd(
        config,
        "PRD-0001",
        outcomes=chosen_outcomes,
        anti_goals="No backdoor access, No unvalidated migrations",
        target_stage=stage,
        accept=accept_flag,
    )

    assert ok, f"Expected shape_prd to succeed but got: {msg}"
    target_file = config.prd_dir / stage / "prd-0001-predictive-diagnostics.md"
    assert target_file.exists()

    content = target_file.read_text(encoding="utf-8")
    assert f"status: {stage.capitalize()}" in content
    for oc in chosen_outcomes:
        assert oc in content

    reg_content = (config.prd_dir / "REGISTRY.md").read_text(encoding="utf-8")
    assert f"| `PRD-0001` | Predictive Diagnostics | {stage.capitalize()} |" in reg_content


@settings(max_examples=25, deadline=15000)
@given(
    subjective_term=st.sampled_from(SUBJECTIVE_WORDS),
    base_idx=st.integers(min_value=0, max_value=len(FALSIFIABLE_OUTCOMES_POOL) - 1),
)
def test_property_shape_prd_rejects_subjective_terms(
    tmp_path_factory,
    subjective_term: str,
    base_idx: int,
):
    """Property invariant: injecting any subjective/unfalsifiable adjective unconditionally

    causes shape_prd to fail the quality gate and prevents stage promotion.
    """
    tmp_path = tmp_path_factory.mktemp("subj_prop")
    config = SpecOpsConfig(
        root_dir=tmp_path,
        project=ProjectSettings(name="SubjPropApp"),
        architecture=ArchitectureSettings(),
        quality=QualitySettings(),
    )

    discover_prd(
        config,
        title="Clean Architecture",
        persona="Alex (The Agentic Systems Architect)",
        bc="core",
        summary="System needs architectural bounds.",
        non_interactive=True,
    )

    corrupted_outcome = f"The user experiences a {subjective_term} interface when navigating pages."
    outcomes = [
        corrupted_outcome,
        FALSIFIABLE_OUTCOMES_POOL[base_idx],
        FALSIFIABLE_OUTCOMES_POOL[(base_idx + 1) % len(FALSIFIABLE_OUTCOMES_POOL)],
    ]

    ok, msg = shape_prd(
        config,
        "PRD-0001",
        outcomes=outcomes,
        accept=True,
    )

    assert not ok
    assert "unfalsifiable" in msg.lower() or "blocked" in msg.lower()

    # Original idea file must remain in idea/
    idea_file = config.prd_dir / "idea" / "prd-0001-clean-architecture.md"
    assert idea_file.exists()
    assert not (config.prd_dir / "accepted" / "prd-0001-clean-architecture.md").exists()
