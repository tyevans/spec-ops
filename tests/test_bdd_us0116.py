"""Executable BDD scenarios for US-0116: Inference-Driven Backlog Refinement."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.inference_curator import InferenceCurator
from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task
from spec_ops.prd.decomposer import PRDDecomposer
from spec_ops.prd.manager import PRDManager
from spec_ops.scaffold.adapters import get_antigravity_slash_commands
from spec_ops.scaffold.init import init_project

scenarios("features/us_0116_inference_curation.feature")


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="InferenceCurationApp")
    config = load_config(root_dir=tmp_path)
    return {"root": tmp_path, "config": config, "res": None}


# ============================================================================
# Scenario: Detecting Architectural Drift and Reconciling Stale Task Specifications
# ============================================================================


@given('a proposed task "TASK-0062" authored against a legacy module that has since been refactored')
def setup_stale_task(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    # Create active refactored module
    active_mod = root / "src" / "spec_ops" / "backlog" / "active_queue.py"
    active_mod.parent.mkdir(parents=True, exist_ok=True)
    active_mod.write_text("# Active refactored queue module\nclass ActiveQueue: pass\n", encoding="utf-8")

    # Author candidate proposed task referencing legacy module and outdated BC
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0062-legacy-queue-refactor.md"

    task = Task(
        id="0062",
        title="Legacy Queue Refactor",
        status="Proposed",
        governing_adrs=["ADR-0003"],
        target_bc="queue",
        body="Implement refactoring targeting src/spec_ops/backlog/legacy_queue.py adhering to ADR-0003.",
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["task_0062_file"] = task_file


@given("the project ADR registry contains superseding decisions adopted since the task was drafted")
def setup_superseded_adr(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    adrs_dir = root / "docs" / "project" / "adrs"
    accepted_adrs = adrs_dir / "accepted"
    accepted_adrs.mkdir(parents=True, exist_ok=True)

    # ADR-0015 supersedes ADR-0003
    adr_15 = accepted_adrs / "adr-0015-enhanced-frontdoor-contracts.md"
    adr_15.write_text(
        "---\nid: '0015'\ntitle: Enhanced Frontdoor Contracts\nstatus: Accepted\n---\n\n"
        "# ADR-0015: Enhanced Frontdoor Contracts\n\n## Context\nSupersedes ADR-0003.\n",
        encoding="utf-8",
    )

    registry = adrs_dir / "REGISTRY.md"
    reg_content = """# ADR Registry

| ID | Title | Status | Date |
|---|---|---|---|
| ADR-0003 | Blackbox Frontdoor Verification | Superseded (by ADR-0015) | 2026-09-29 |
| ADR-0015 | Enhanced Frontdoor Contracts | Accepted | 2026-09-29 |
"""
    registry.write_text(reg_content, encoding="utf-8")


@when('the lead runs "spec-ops curate --infer"')
def run_curate_infer(bdd_ctx: dict[str, Any]):
    curator = InferenceCurator(bdd_ctx["config"])
    res = curator.curate(dry_run=False)
    bdd_ctx["res"] = res


@then("the curation engine analyzes current repository files, the relational knowledge graph, and recent ADRs")
def verify_analysis_ran(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res is not None


@then("updates the task frontmatter and specification text to align with active bounded contexts and module paths")
def verify_task_reconciled(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    queue = BacklogQueue(root / "docs" / "project" / "backlog")
    tasks = {t.canonical_id: t for t in queue.list_all_tasks()}

    task_62 = tasks.get("TASK-0062")
    assert task_62 is not None

    # ADR-0003 replaced with ADR-0015 in governing_adrs and body
    assert "ADR-0015" in task_62.governing_adrs
    assert "ADR-0003" not in task_62.governing_adrs
    assert "ADR-0015" in task_62.body

    # Stale path replaced
    assert "src/spec_ops/backlog/active_queue.py" in task_62.body
    assert "legacy_queue.py" not in task_62.body

    # Bounded context aligned
    assert task_62.target_bc in ("backlog", "core")


@then("notes reconciled architectural changes in the curation audit trail.")
def verify_audit_trail_recorded(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert any("TASK-0062" in a or "reconciled" in a.lower() for a in res.audit_trail)


# ============================================================================
# Scenario: Autonomously Slicing Oversized Monolithic Tasks into Thin Vertical Slices
# ============================================================================


@given("a proposed task whose specification touches multiple bounded contexts and is estimated to exceed the 500-line modular limit (ADR-0002)")
def setup_oversized_task(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0063-monolithic-subsystem.md"

    body = """# Monolithic Subsystem Implementation

## Summary
Implement end-to-end multi-context subsystem spanning worker execution, backlog persistence, and visualizer graph projection.

## Checkable Outcomes
1. Implement persistent transaction log and event store.
2. Build sandboxed worker executor interceptor.
3. Expose CLI visualization pipeline.
4. Verify end-to-end integration and health checks.

estimated_lines: 650
This task is estimated to exceed the 500-line modular limit (ADR-0002).
"""
    task = Task(
        id="0063",
        title="Monolithic Subsystem",
        status="Proposed",
        target_bc="backlog, worker, visualizer",
        governing_prds=["PRD-0001"],
        body=body,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["oversized_task"] = task


@when('"spec-ops curate --infer" audits the task for refinement')
def run_curate_audit_slicing(bdd_ctx: dict[str, Any]):
    curator = InferenceCurator(bdd_ctx["config"])
    res = curator.curate(dry_run=False)
    bdd_ctx["res"] = res


@then("the curation inference engine identifies the scope violation")
def verify_scope_violation_identified(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert "TASK-0063" in res.tasks_sliced or any("TASK-0063" in a for a in res.audit_trail)


@then("decomposes the task into discrete INVEST-compliant vertical slices and an initial architectural spike")
def verify_task_decomposed(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    queue = BacklogQueue(root / "docs" / "project" / "backlog")
    tasks = queue.list_all_tasks()
    spike_tasks = [t for t in tasks if "Architectural Spike:" in t.title and "Monolithic Subsystem" in t.title]
    slice_tasks = [t for t in tasks if "Monolithic Subsystem —" in t.title]

    assert len(spike_tasks) == 1
    assert len(slice_tasks) >= 2


@then('scaffolds sequential child tasks in "docs/project/backlog/proposed/" linked to the parent PRD')
def verify_child_tasks_scaffolded(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_files = list(proposed_dir.glob("*.md"))
    assert len(proposed_files) >= 2
    for p in proposed_files:
        content = p.read_text(encoding="utf-8")
        assert "PRD-0001" in content


@then('promotes only the initial thin slice or spike to "docs/project/backlog/refined/".')
def verify_initial_slice_promoted(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    refined_dir = root / "docs" / "project" / "backlog" / "refined"
    refined_files = list(refined_dir.glob("*.md"))
    assert len(refined_files) >= 1
    assert any("spike" in f.name.lower() or "monolithic" in f.name.lower() for f in refined_files)


# ============================================================================
# Scenario: Generative Definition of Ready (DoR) Synthesis instead of Dumb Rejection
# ============================================================================


@given("a proposed task lacking executable Gherkin scenarios or property-based testing invariants")
def setup_task_lacking_dor(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    # Decompose PRD-0001 to have valid governing PRD
    mgr = PRDManager(bdd_ctx["config"])
    mgr.create_prd(title="Inference Engine", persona="Architect", component="core")

    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / "0064-inference-adapter.md"

    body = """# Inference Adapter

## Summary
Provide unified adapter for cognitive curation and model execution.

## Problem Statement
Need clean abstraction without private mock backdoors.
"""
    task = Task(
        id="0064",
        title="Inference Adapter",
        status="Proposed",
        target_bc="core",
        governing_prds=["PRD-0001"],
        body=body,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_ctx["dor_task_file"] = task_file


@when('"spec-ops curate --infer" processes the task for buffer replenishment')
def run_curate_for_dor(bdd_ctx: dict[str, Any]):
    curator = InferenceCurator(bdd_ctx["config"])
    res = curator.curate(dry_run=False)
    bdd_ctx["res"] = res


@then("rather than aborting with a hard rejection error, the engine inspects the governing PRD checkable outcomes and public frontdoors")
def verify_no_hard_rejection(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res is not None


@then('synthesizes executable Gherkin scenarios ("Given ... When ... Then") and Hypothesis invariant specifications')
def verify_criteria_synthesized(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    refined_dir = root / "docs" / "project" / "backlog" / "refined"
    promoted_file = None
    for p in refined_dir.glob("*.md"):
        if "0064" in p.name:
            promoted_file = p
            break
    assert promoted_file is not None
    content = promoted_file.read_text(encoding="utf-8")
    assert "```gherkin" in content
    assert "Given " in content
    assert "When " in content
    assert "Then " in content
    assert "@given" in content or "Hypothesis" in content


@then('writes the complete DoR-compliant contract into the task markdown before promoting it to "docs/project/backlog/refined/".')
def verify_dor_contract_promoted(bdd_ctx: dict[str, Any]):
    root: Path = bdd_ctx["root"]
    refined_dir = root / "docs" / "project" / "backlog" / "refined"
    promoted_tasks = list(refined_dir.glob("*0064*.md"))
    assert len(promoted_tasks) == 1
    t = parse_task(promoted_tasks[0])
    assert t.status == "Refined"


# ============================================================================
# Scenario: Interactive AI-Native /curate Slash Command Skill
# ============================================================================


@given("an autonomous coding agent operating in Antigravity or Claude Code")
def agent_operating(bdd_ctx: dict[str, Any]):
    pass


@when('the developer or lead triggers "/curate"')
def trigger_curate_skill(bdd_ctx: dict[str, Any]):
    cmds = get_antigravity_slash_commands()
    bdd_ctx["curate_skill"] = cmds.get(".agents/skills/curate/SKILL.md", "")


@then('the agent executes an interactive cognitive refinement workflow: auditing the under-buffered queue, evaluating proposed tasks against repository reality, proposing vertical decompositions for oversized tasks, and presenting a human-in-the-loop review before moving tasks to "docs/project/backlog/refined/".')
def verify_interactive_workflow_steps(bdd_ctx: dict[str, Any]):
    skill_text = bdd_ctx["curate_skill"]
    assert skill_text
    assert "uv run spec-ops curate --infer --dry-run" in skill_text
    assert "uv run spec-ops curate --infer" in skill_text
    assert "Audit Under-Buffered Queue" in skill_text
    assert "Reconcile Architectural Drift" in skill_text
    assert "Decompose Oversized Monolithic Tasks" in skill_text
    assert "Synthesize Missing DoR Contracts" in skill_text
    assert "Human-in-the-Loop Review" in skill_text
