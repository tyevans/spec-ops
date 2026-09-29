"""Executable BDD scenarios for US-0044 (PRD Lifecycle Stage Gate Progression)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0044_prd_lifecycle.feature")


@pytest.fixture
def bdd_prd_context(tmp_path: Path) -> dict[str, Any]:
    """Shared state container for PRD BDD scenarios."""
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "PRDApp",
            "--dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    return {"dir": tmp_path, "res": None, "file": None}


@given('a PRD "PRD-0002" residing in "docs/project/product/idea/" with defined user pain points')
def prd_idea_with_pain_points(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    idea_dir = root / "docs" / "project" / "product" / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    prd_file = idea_dir / "prd-0002-enterprise-security.md"
    content = """---
id: '0002'
title: Enterprise Security Engine
status: Idea
created: 2026-09-29
target_persona: Sasha
component: security
---

# PRD-0002 — Enterprise Security Engine

## Who this is for

- **Sasha**: Security officer needing tamper-evident audit logs.

## What the person cannot do today

- Cannot prevent unsandboxed agents from executing unauthorized commands.

## What good looks like

1. Hard sandboxing boundaries.

## What this does not do

- Does not replace network perimeter firewalls.

## Checkable Outcomes

1. Executing security scan returns code 0.
"""
    prd_file.write_text(content, encoding="utf-8")
    registry_file = root / "docs" / "project" / "product" / "REGISTRY.md"
    registry_file.write_text(
        "# PRD Registry\n\n"
        "| ID | Title | Status | Target Persona | Component |\n"
        "|---|---|---|---|---|\n"
        "| `PRD-0002` | Enterprise Security Engine | Idea | Sasha | security |\n",
        encoding="utf-8",
    )
    bdd_prd_context["file"] = prd_file


@when('Taylor runs "spec-ops prd promote PRD-0002 --stage shaped" or clicks "Promote to Shaped" in the visualizer')
def promote_prd_to_shaped(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "prd",
            "promote",
            "PRD-0002",
            "--stage",
            "shaped",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    bdd_prd_context["res"] = res
    assert res.returncode == 0


@then('the PRD file is moved to "docs/project/product/shaped/"')
def verify_prd_moved_to_shaped(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    old_file = root / "docs" / "project" / "product" / "idea" / "prd-0002-enterprise-security.md"
    new_file = root / "docs" / "project" / "product" / "shaped" / "prd-0002-enterprise-security.md"
    assert not old_file.exists()
    assert new_file.exists()


@then('the frontmatter status updates to "Shaped"')
def verify_frontmatter_status_shaped(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    target = root / "docs" / "project" / "product" / "shaped" / "prd-0002-enterprise-security.md"
    content = target.read_text(encoding="utf-8")
    assert "status: Shaped" in content


@then('"docs/project/product/REGISTRY.md" updates atomically to reflect the new stage.')
def verify_registry_updated(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    reg = root / "docs" / "project" / "product" / "REGISTRY.md"
    content = reg.read_text(encoding="utf-8")
    assert "Shaped" in content or "Shipped" in content


@given("a shaped PRD lacking linked user personas or falsifiable checkable outcomes")
def shaped_prd_failing_quality_gates(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    shaped_dir = root / "docs" / "project" / "product" / "shaped"
    shaped_dir.mkdir(parents=True, exist_ok=True)
    flawed_file = shaped_dir / "prd-0003-flawed.md"
    content = """---
id: '0003'
title: Flawed PRD
status: Shaped
target_persona: unmapped
component: prd
---

# PRD-0003 — Flawed PRD

## Who this is for

- Context without persona.

## What the person cannot do today

- Friction statement.

## What good looks like

1. Capability description.

## What this does not do

- Anti-goals.

## Checkable Outcomes
"""
    flawed_file.write_text(content, encoding="utf-8")
    bdd_prd_context["file"] = flawed_file


@when('Taylor attempts to promote the PRD to "accepted"')
def promote_prd_to_accepted(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "prd",
            "promote",
            "PRD-0003",
            "--stage",
            "accepted",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    bdd_prd_context["res"] = res


@then("the promotion command exits with a stage-gate violation error")
def verify_promotion_failed(bdd_prd_context: dict[str, Any]):
    res = bdd_prd_context["res"]
    assert res.returncode == 1
    assert "stage-gate violation error" in res.stdout.lower() or "stage-gate violation" in res.stdout.lower()


@then('the output lists missing prerequisites: "No checkable outcomes defined" and "Target persona unmapped"')
def verify_missing_prerequisites(bdd_prd_context: dict[str, Any]):
    res = bdd_prd_context["res"]
    assert "No checkable outcomes defined" in res.stdout
    assert "Target persona unmapped" in res.stdout


@then('the PRD remains in "docs/project/product/shaped/" without invalid decomposition.')
def verify_prd_remains_in_shaped(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    shaped_file = root / "docs" / "project" / "product" / "shaped" / "prd-0003-flawed.md"
    accepted_file = root / "docs" / "project" / "product" / "accepted" / "prd-0003-flawed.md"
    assert shaped_file.exists()
    assert not accepted_file.exists()


@given('an accepted PRD "PRD-0001" where all 23 implementing backlog tasks are marked "Complete"')
def accepted_prd_completed_tasks(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    accepted_dir = root / "docs" / "project" / "product" / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    prd_file = accepted_dir / "prd-0001-engine.md"
    prd_file.write_text(
        """---
id: '0001'
title: Engine Core
status: Accepted
target_persona: Alex
component: core
---

# PRD-0001 — Engine Core

## Who this is for
- **Alex**: Architect.

## What good looks like
1. Solid core.

## What this does not do
- Anti goals.

## Checkable Outcomes
1. Returns code 0.
""",
        encoding="utf-8",
    )
    bdd_prd_context["file"] = prd_file
    complete_dir = root / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 24):
        task_id = f"TASK-{i:04d}"
        t_file = complete_dir / f"{i:04d}-task-{i}.md"
        t_file.write_text(
            f"""---
id: '{i:04d}'
title: Task {i}
status: Complete
governing_prds:
  - PRD-0001
---
# {task_id}
""",
            encoding="utf-8",
        )


@given("all linked executable BDD user story scenarios pass with a 100% success rate")
def bdd_scenarios_pass(bdd_prd_context: dict[str, Any]):
    pass


@when('Taylor executes "spec-ops prd ship PRD-0001" or confirms shipping in the visualizer')
def execute_prd_ship(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "prd",
            "ship",
            "PRD-0001",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    bdd_prd_context["res"] = res
    assert res.returncode == 0


@then('the file is archived to "docs/project/product/shipped/"')
def verify_prd_shipped(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    old_file = root / "docs" / "project" / "product" / "accepted" / "prd-0001-engine.md"
    new_file = root / "docs" / "project" / "product" / "shipped" / "prd-0001-engine.md"
    assert not old_file.exists()
    assert new_file.exists()


@then('the status updates to "Shipped"')
def verify_status_shipped(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    new_file = root / "docs" / "project" / "product" / "shipped" / "prd-0001-engine.md"
    content = new_file.read_text(encoding="utf-8")
    assert "status: Shipped" in content


@then('"docs/project/backlog/ROADMAP.md" records the milestone completion date and marks the horizon closed.')
def verify_roadmap_updated(bdd_prd_context: dict[str, Any]):
    root = bdd_prd_context["dir"]
    roadmap = root / "docs" / "project" / "backlog" / "ROADMAP.md"
    content = roadmap.read_text(encoding="utf-8")
    assert "Milestone completion date:" in content
    assert "Horizon closed" in content
