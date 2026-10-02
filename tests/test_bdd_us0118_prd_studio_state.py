"""BDD step definitions for US-0118: PRD Studio Domain Model & State Handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.studio_state import PRDStudioSessionState, PRDStudioStateManager
from spec_ops.scaffold.init import init_project

scenarios("features/us_0118_prd_studio_state.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {}


@given("a fresh PRD Studio session")
def fresh_session(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="FreshStudioProject")
    manager = PRDStudioStateManager(repo_root=tmp_path)
    bdd_ctx["manager"] = manager
    bdd_ctx["tmp_path"] = tmp_path


@when(
    parsers.parse(
        'the user creates a new draft for persona "{persona}" titled "{title}"'
    )
)
def create_new_draft(persona: str, title: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    mgr.new_draft(
        title=title,
        persona=persona,
        problem_statement="Users currently face manual terminal friction.",
        component="prd",
    )


@when(parsers.parse('adds a checkable outcome "{outcome}"'))
def add_outcome_step(outcome: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    mgr.add_outcome(outcome)


@then("the session state is marked as dirty")
def verify_state_dirty(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert mgr.state.is_dirty is True


@then("the draft validation passes without schema violations.")
def verify_validation_passes(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert mgr.state.is_valid is True
    assert len(mgr.state.validation_errors) == 0


@given("a repository initialized with accepted and idea PRDs")
def repo_with_prds(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="PrdRepoProject")
    # Write a synthetic PRD-0003 in accepted/
    accepted_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    content = """---
id: PRD-0003
title: Product Discovery Web PRD Studio
status: Accepted
target_persona: Taylor
component: prd
---

# PRD-0003: Product Discovery Web PRD Studio

## Problem Statement
Need a web editor for non-technical PMs.

## Checkable Outcomes
- Running spec-ops prd studio launches web app
- Flags invalid schema instantly
"""
    (accepted_dir / "prd-0003-discovery.md").write_text(content, encoding="utf-8")
    bdd_ctx["manager"] = PRDStudioStateManager(repo_root=tmp_path)


@when(parsers.parse('the user loads PRD "{prd_id}" into the studio state manager'))
def load_prd_step(prd_id: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    success = mgr.load_prd(prd_id)
    assert success is True


@then(parsers.parse('the active PRD ID is set to "{prd_id}"'))
def verify_active_prd_id(prd_id: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert mgr.state.active_prd_id == prd_id


@then("the checkable outcomes and problem statement are populated")
def verify_outcomes_populated(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert len(mgr.state.outcomes) == 2
    assert "Need a web editor" in mgr.state.problem_statement


@then("the session state is marked as not dirty.")
def verify_state_not_dirty(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert mgr.state.is_dirty is False


@given("a PRD draft with 3 checkable outcomes")
def draft_with_three_outcomes(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="OutcomesRepo")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Sample Outcomes PRD",
        persona="Taylor",
        problem_statement="Test statement",
        outcomes=["Alpha outcome", "Beta outcome", "Gamma outcome"],
    )
    bdd_ctx["manager"] = mgr


@when("the user reorders the outcomes in reverse order")
def reorder_outcomes_reverse(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    mgr.reorder_outcomes([2, 1, 0])


@then("the outcomes array reflects the new sequence")
def verify_reordered_sequence(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert mgr.state.outcomes == ["Gamma outcome", "Beta outcome", "Alpha outcome"]


@then("when the user removes the first outcome")
def remove_first_outcome(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    mgr.remove_outcome(0)


@then("2 checkable outcomes remain in the draft.")
def verify_two_outcomes_remain(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert len(mgr.state.outcomes) == 2
    assert mgr.state.outcomes == ["Beta outcome", "Alpha outcome"]


@given("an idea PRD draft with valid fields and checkable outcomes")
def idea_draft_ready(tmp_path: Path, bdd_ctx: dict[str, Any]):
    init_project(tmp_path, name="PromotionRepo")
    mgr = PRDStudioStateManager(repo_root=tmp_path)
    mgr.new_draft(
        title="Notification Engine",
        persona="Taylor",
        component="prd",
        problem_statement="Users need notifications.",
        outcomes=["User receives instant alerts"],
    )
    bdd_ctx["manager"] = mgr
    bdd_ctx["tmp_path"] = tmp_path


@when("the studio state manager saves the draft to disk")
def save_draft_step(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    res = mgr.save_draft()
    assert res.get("success") is True


@then("a markdown file is created under docs/project/product/idea/")
def verify_idea_file_created(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert mgr.state.active_file_path is not None
    assert "docs/project/product/idea" in mgr.state.active_file_path
    disk_path = bdd_ctx["tmp_path"] / mgr.state.active_file_path
    assert disk_path.exists()


@then(parsers.parse('when the PRD is promoted to stage "{target_stage}"'))
def promote_stage_step(target_stage: str, bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    res = mgr.promote_stage(target_stage)
    assert res.get("success") is True


@then("the PRD file moves to the shaped directory and state reflects the new stage.")
def verify_shaped_file(bdd_ctx: dict[str, Any]):
    mgr: PRDStudioStateManager = bdd_ctx["manager"]
    assert mgr.state.stage == "shaped"
    assert "docs/project/product/shaped" in (mgr.state.active_file_path or "")
    disk_path = bdd_ctx["tmp_path"] / (mgr.state.active_file_path or "")
    assert disk_path.exists()
