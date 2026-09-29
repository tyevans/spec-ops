"""Executable BDD scenarios for US-0099 (PRD Discovery Guide & Linter)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0099_prd_linter.feature")


@pytest.fixture
def bdd_linter_context(tmp_path: Path) -> dict[str, Any]:
    """Shared state container for linter BDD scenarios."""
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "LinterApp",
            "--dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    return {"dir": tmp_path, "res": None, "file": None}


@when('Taylor executes "spec-ops prd new"')
def execute_prd_new_interactive(bdd_linter_context: dict[str, Any]):
    root = bdd_linter_context["dir"]
    answers = (
        "5\n"
        "Automated Billing Integration\n"
        "billing\n"
        "Users cannot issue invoices without external scripts\n"
        "One-click PDF generation via public CLI\n"
        "Does not handle cryptocurrency payments\n"
        "Running 'spec-ops billing invoice' returns code 0\n"
    )
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "prd",
            "new",
        ],
        cwd=str(root),
        input=answers,
        capture_output=True,
        text=True,
    )
    bdd_linter_context["res"] = res
    assert res.returncode == 0


@then("the CLI initiates an interactive discovery questionnaire prompting for:")
def verify_questionnaire_prompts(bdd_linter_context: dict[str, Any]):
    res = bdd_linter_context["res"]
    assert "Target Persona (selected from docs/project/user_stories/PERSONAS.md)" in res.stdout
    assert "What the person cannot do today (customer friction statement)" in res.stdout
    assert "What good looks like (core capabilities)" in res.stdout
    assert "What this does not do (scope boundaries and non-goals)" in res.stdout
    assert "Checkable Outcomes (at least one observable verification criterion)" in res.stdout


@then('upon completion scaffolds a clean Markdown PRD under "docs/project/product/idea/" with valid YAML frontmatter.')
def verify_scaffolded_prd(bdd_linter_context: dict[str, Any]):
    root = bdd_linter_context["dir"]
    idea_dir = root / "docs" / "project" / "product" / "idea"
    files = list(idea_dir.glob("*.md"))
    assert len(files) >= 1
    created_file = files[0]
    content = created_file.read_text(encoding="utf-8")
    assert "status: Idea" in content
    assert "## Who this is for" in content
    assert "## What the person cannot do today" in content
    assert "## What good looks like" in content
    assert "## What this does not do" in content
    assert "## Checkable Outcomes" in content


@given('a draft PRD "docs/project/product/idea/prd-0005-billing.md" that omits the "## What this does not do" section')
def draft_prd_missing_anti_goals(bdd_linter_context: dict[str, Any]):
    root = bdd_linter_context["dir"]
    idea_dir = root / "docs" / "project" / "product" / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    target = idea_dir / "prd-0005-billing.md"
    content = """---
id: '0005'
title: Billing Automation
status: Idea
target_persona: Taylor
component: billing
---

# PRD-0005 — Billing Automation

## Who this is for
- **Taylor**: Product manager.

## What good looks like
1. Automated invoices.

## Checkable Outcomes
1. Running 'spec-ops billing invoice' returns code 0
"""
    target.write_text(content, encoding="utf-8")
    bdd_linter_context["file"] = target


@when('Taylor executes "spec-ops prd lint docs/project/product/idea/prd-0005-billing.md"')
def lint_target_prd(bdd_linter_context: dict[str, Any]):
    root = bdd_linter_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "prd",
            "lint",
            "docs/project/product/idea/prd-0005-billing.md",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    bdd_linter_context["res"] = res


@then('the linter reports violation: "Missing required section: \'## What this does not do\'"')
def verify_violation_missing_anti_goals(bdd_linter_context: dict[str, Any]):
    res = bdd_linter_context["res"]
    assert "Missing required section: '## What this does not do'" in res.stdout


@then('reports guidance: "Define explicit anti-goals to prevent multi-agent scope creep"')
def verify_guidance_anti_goals(bdd_linter_context: dict[str, Any]):
    res = bdd_linter_context["res"]
    assert "Define explicit anti-goals to prevent multi-agent scope creep" in res.stdout


@then("exits with code 1.")
def verify_exit_code_1(bdd_linter_context: dict[str, Any]):
    res = bdd_linter_context["res"]
    assert res.returncode == 1


@given("a draft PRD containing checkable outcomes:")
def draft_prd_with_outcomes(bdd_linter_context: dict[str, Any]):
    root = bdd_linter_context["dir"]
    idea_dir = root / "docs" / "project" / "product" / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    target = idea_dir / "prd-0006-outcomes.md"
    content = """---
id: '0006'
title: Outcomes Test
status: Idea
target_persona: Taylor
component: prd
---

# PRD-0006 — Outcomes Test

## Who this is for
- **Taylor**: PM.

## What good looks like
1. Clean interface.

## What this does not do
- Anti goals.

## Checkable Outcomes
1. The UI looks clean and modern
2. Running 'spec-ops billing invoice' returns code 0
"""
    target.write_text(content, encoding="utf-8")
    bdd_linter_context["file"] = target


@when('Taylor executes "spec-ops prd lint" on the draft PRD')
def lint_draft_prd(bdd_linter_context: dict[str, Any]):
    root = bdd_linter_context["dir"]
    target = bdd_linter_context["file"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "prd",
            "lint",
            str(target),
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    bdd_linter_context["res"] = res


@then('the linter flags Outcome 1: "Subjective adjective \'clean and modern\' is unfalsifiable"')
def verify_flags_outcome_1(bdd_linter_context: dict[str, Any]):
    res = bdd_linter_context["res"]
    assert "Subjective adjective 'clean and modern' is unfalsifiable" in res.stdout


@then("passes Outcome 2 as a valid falsifiable frontdoor contract")
def verify_passes_outcome_2(bdd_linter_context: dict[str, Any]):
    res = bdd_linter_context["res"]
    assert "passes as a valid falsifiable frontdoor contract" in res.stdout


@then("returns a passing grade only when all outcomes are verifiable.")
def verify_fails_when_unfalsifiable(bdd_linter_context: dict[str, Any]):
    res = bdd_linter_context["res"]
    assert res.returncode == 1
