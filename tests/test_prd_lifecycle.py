"""Unit tests for PRD lifecycle management, discovery, and registry synchronization."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.config.models import ArchitectureSettings, ProjectSettings, QualitySettings, SpecOpsConfig
from spec_ops.prd.discovery import interactive_new_prd, parse_available_personas
from spec_ops.prd.lifecycle import PRDLifecycleManager


@pytest.fixture
def lifecycle_config(tmp_path: Path) -> SpecOpsConfig:
    return SpecOpsConfig(
        root_dir=tmp_path,
        project=ProjectSettings(name="LifecycleApp"),
        architecture=ArchitectureSettings(),
        quality=QualitySettings(),
    )


def test_init_and_attributes(lifecycle_config: SpecOpsConfig):
    mgr = PRDLifecycleManager(lifecycle_config)
    assert mgr.config == lifecycle_config
    assert mgr.prd_dir == lifecycle_config.prd_dir
    assert mgr.registry_path == lifecycle_config.prd_dir / "REGISTRY.md"
    assert mgr.roadmap_path == lifecycle_config.backlog_dir / "ROADMAP.md"
    assert mgr.STAGES == ["idea", "shaped", "accepted", "shipped"]


def test_find_prd_file_variants(lifecycle_config: SpecOpsConfig):
    mgr = PRDLifecycleManager(lifecycle_config)
    assert mgr.find_prd_file("missing") is None

    idea_dir = lifecycle_config.prd_dir / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    reg_dummy = lifecycle_config.prd_dir / "REGISTRY.md"
    reg_dummy.write_text("# Reg\n", encoding="utf-8")

    p = idea_dir / "prd-0005-billing.md"
    p.write_text("""---
id: '0005'
title: Billing
---
# PRD-0005 — Billing
""", encoding="utf-8")

    assert mgr.find_prd_file(p) == p.resolve()
    assert mgr.find_prd_file("5") == p.resolve()
    assert mgr.find_prd_file("0005") == p.resolve()
    assert mgr.find_prd_file("PRD-0005") == p.resolve()
    assert mgr.find_prd_file("prd-0005") == p.resolve()
    assert mgr.find_prd_file("PRD5") == p.resolve()
    assert mgr.find_prd_file("PRD-5") == p.resolve()
    assert mgr.find_prd_file("PRD-ABC") is None
    assert mgr.find_prd_file("REGISTRY") is None

    arbitrary = idea_dir / "arbitrary-spec.md"
    arbitrary.write_text("""---
id: '0009'
title: Custom Spec
---
# PRD-0009
""", encoding="utf-8")
    assert mgr.find_prd_file("0009") == arbitrary.resolve()
    assert mgr.find_prd_file("PRD-0009") == arbitrary.resolve()


def test_update_registry_atomic(lifecycle_config: SpecOpsConfig):
    mgr = PRDLifecycleManager(lifecycle_config)
    mgr.update_registry("PRD-0001", "Core Engine", "Idea", "Alex", "core")
    reg_content = mgr.registry_path.read_text(encoding="utf-8")
    assert reg_content == (
        "# PRD Registry\n\n"
        "| ID | Title | Status | Target Persona | Component |\n"
        "|---|---|---|---|---|\n"
        "| `PRD-0001` | Core Engine | Idea | Alex | core |\n"
    )

    mgr.update_registry("PRD-0001", "", "Shaped", "", "")
    reg_content_updated = mgr.registry_path.read_text(encoding="utf-8")
    assert "| `PRD-0001` | Core Engine | Shaped | Alex | core |" in reg_content_updated
    assert "Idea" not in reg_content_updated
    assert reg_content_updated.count("PRD-0001") == 1

    mgr.update_registry("PRD-0002", "Security", "Accepted", "Sasha", "security")
    reg_content_two = mgr.registry_path.read_text(encoding="utf-8")
    assert "| `PRD-0002` | Security | Accepted | Sasha | security |" in reg_content_two
    assert reg_content_two.count("PRD-0001") == 1
    assert reg_content_two.count("PRD-0002") == 1


def test_update_roadmap_milestone(lifecycle_config: SpecOpsConfig):
    mgr = PRDLifecycleManager(lifecycle_config)
    mgr.update_roadmap("PRD-0001", "Engine")
    assert not mgr.roadmap_path.exists()

    mgr.roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    mgr.roadmap_path.write_text("# Roadmap\n\n## Milestone 1 (Active)\n", encoding="utf-8")
    mgr.update_roadmap("PRD-0001", "Engine")
    content = mgr.roadmap_path.read_text(encoding="utf-8")
    assert "Horizon closed for PRD-0001 — Engine" in content

    mgr.update_roadmap("PRD-0001", "Engine")
    assert content.count("Horizon closed for PRD-0001 — Engine") == 1

    mgr.roadmap_path.write_text("# Roadmap\n\nNo sections here\n", encoding="utf-8")
    mgr.update_roadmap("PRD-0002", "Feature")
    content_no_sec = mgr.roadmap_path.read_text(encoding="utf-8")
    assert "- Milestone completion date:" in content_no_sec
    assert "Horizon closed for PRD-0002 — Feature" in content_no_sec


def test_promote_stage_validations(lifecycle_config: SpecOpsConfig):
    mgr = PRDLifecycleManager(lifecycle_config)
    ok, msg = mgr.promote("PRD-0001", "invalid")
    assert not ok
    assert "Invalid target stage" in msg

    ok, msg = mgr.promote("PRD-9999", "shaped")
    assert not ok
    assert "PRD not found: PRD-9999" in msg


def test_promote_shaped_gate(lifecycle_config: SpecOpsConfig):
    idea_dir = lifecycle_config.prd_dir / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    p = idea_dir / "prd-0010-pain.md"
    p.write_text("""---
id: '0010'
title: No Pain
---
# PRD-0010
""", encoding="utf-8")

    mgr = PRDLifecycleManager(lifecycle_config)
    ok, msg = mgr.promote("PRD-0010", "shaped")
    assert not ok
    assert "Stage-gate violation error: PRD PRD-0010 must define user pain points before promotion to shaped." in msg

    p.write_text("""---
id: '0010'
title: With Pain
status: Idea
target_persona: Taylor
---
# PRD-0010
## Problem Statement
Users face significant friction.
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. Returns code 0
""", encoding="utf-8")

    ok, msg = mgr.promote("PRD-0010", "shaped")
    assert ok
    shaped_file = lifecycle_config.prd_dir / "shaped" / "prd-0010-pain.md"
    assert shaped_file.exists()
    assert not p.exists()
    assert "status: Shaped" in shaped_file.read_text(encoding="utf-8")


def test_promote_accepted_gate(lifecycle_config: SpecOpsConfig):
    shaped_dir = lifecycle_config.prd_dir / "shaped"
    shaped_dir.mkdir(parents=True, exist_ok=True)
    p = shaped_dir / "prd-0011-gate.md"
    p.write_text("""---
id: '0011'
title: Flawed
status: Shaped
target_persona: ''
---
# PRD-0011
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
""", encoding="utf-8")

    mgr = PRDLifecycleManager(lifecycle_config)
    ok, msg = mgr.promote("PRD-0011", "accepted")
    assert not ok
    assert "Stage-gate violation error: Promotion to 'accepted' blocked for PRD-0011:" in msg
    assert "Target persona unmapped" in msg
    assert "No checkable outcomes defined" in msg

    p.write_text("""---
id: '0011'
title: Unfalsifiable
status: Shaped
target_persona: Taylor
---
# PRD-0011
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. The app is clean and modern
""", encoding="utf-8")

    ok, msg = mgr.promote("PRD-0011", "accepted")
    assert not ok
    assert "Checkable outcomes contain unfalsifiable language" in msg

    p.write_text("""---
id: '0011'
title: Valid
status: Shaped
target_persona: Taylor
---
# PRD-0011
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. Running 'spec-ops' returns code 0
""", encoding="utf-8")

    ok, msg = mgr.promote("PRD-0011", "accepted")
    assert ok
    accepted_file = lifecycle_config.prd_dir / "accepted" / "prd-0011-gate.md"
    assert accepted_file.exists()
    assert not p.exists()
    assert "status: Accepted" in accepted_file.read_text(encoding="utf-8")


def test_promote_shipped_gate_and_incomplete_tasks(lifecycle_config: SpecOpsConfig):
    accepted_dir = lifecycle_config.prd_dir / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    p = accepted_dir / "prd-0012-tasks.md"
    p.write_text("""---
id: '0012'
title: Shipped Test
status: Accepted
target_persona: Taylor
---
# PRD-0012
## Who this is for
- Taylor
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. Code passes
""", encoding="utf-8")

    backlog_dir = lifecycle_config.backlog_dir / "refined"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    t = backlog_dir / "0099-incomplete.md"
    t.write_text("""---
id: '0099'
title: Incomplete Task
status: Refined
target_bc: prd
governing_prds:
  - PRD-0012
---
# TASK-0099
""", encoding="utf-8")

    mgr = PRDLifecycleManager(lifecycle_config)
    ok, msg = mgr.promote("PRD-0012", "shipped")
    assert not ok
    assert "Stage-gate violation error: Cannot ship PRD-0012: Implementing tasks are not complete" in msg

    complete_dir = lifecycle_config.backlog_dir / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    t.unlink()
    t_complete = complete_dir / "0099-complete.md"
    t_complete.write_text("""---
id: '0099'
title: Complete Task
status: Complete
target_bc: prd
governing_prds:
  - PRD-0012
---
# TASK-0099
""", encoding="utf-8")

    ok, msg = mgr.ship("PRD-0012")
    assert ok
    shipped_file = lifecycle_config.prd_dir / "shipped" / "prd-0012-tasks.md"
    assert shipped_file.exists()
    assert not p.exists()
    assert "status: Shipped" in shipped_file.read_text(encoding="utf-8")


def test_discovery_guide_non_interactive(lifecycle_config: SpecOpsConfig):
    personas = parse_available_personas(lifecycle_config.user_stories_dir / "PERSONAS.md")
    assert len(personas) >= 6

    personas_file = lifecycle_config.user_stories_dir / "PERSONAS.md"
    personas_file.parent.mkdir(parents=True, exist_ok=True)
    personas_file.write_text("""# Personas
## 1. Custom Persona
Details
""", encoding="utf-8")
    parsed = parse_available_personas(personas_file)
    assert parsed == ["Custom Persona"]

    personas_file.write_text("No headers\n", encoding="utf-8")
    fallback = parse_available_personas(personas_file)
    assert len(fallback) >= 6

    p = interactive_new_prd(
        lifecycle_config,
        title="Custom Capability",
        persona="Custom Persona",
        component="billing",
        friction="Cannot pay",
        good="Auto pay",
        anti_goals="No cash",
        outcomes="Returns 0",
        non_interactive=True,
    )
    assert p.exists()
    assert (lifecycle_config.prd_dir / "idea").exists()
    content = p.read_text(encoding="utf-8")
    assert "status: Idea" in content
    assert "target_persona: Custom Persona" in content
    assert "component: billing" in content
    assert "## Who this is for" in content
    assert "## What the person cannot do today" in content
    assert "## What good looks like" in content
    assert "## What this does not do" in content
    assert "## Checkable Outcomes" in content
