"""BDD step definitions for US-0119: PRD Lint Engine and Line-Level Remediation."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.prd.lint_engine import PRDLintEngine, PRDLintReport
from spec_ops.prd.studio import KNOWN_PERSONAS

scenarios("features/us_0119_prd_lint_engine.feature")


@pytest.fixture
def bdd_ctx() -> dict[str, Any]:
    return {"engine": PRDLintEngine()}


@given("a PRD document with missing target persona frontmatter")
def prd_missing_persona(bdd_ctx: dict[str, Any]):
    content = """---
id: PRD-0042
title: Unmapped Persona Demo
status: Idea
target_persona: unmapped
component: prd
---

# PRD-0042: Unmapped Persona Demo

## Problem Statement
Need a persona.

## What good looks like
Clear persona.

## What this does not do
Does not guess persona.

## Checkable Outcomes
- Running spec-ops prd lint flags unmapped persona
"""
    bdd_ctx["content"] = content


@when("the PRD lint engine analyzes the document")
def analyze_document_step(bdd_ctx: dict[str, Any]):
    engine: PRDLintEngine = bdd_ctx["engine"]
    content: str = bdd_ctx["content"]
    report: PRDLintReport = engine.lint_content(content, file_path="docs/project/product/idea/prd-0042.md")
    bdd_ctx["report"] = report


@then(parsers.parse('a diagnostic with rule "{rule_id}" is reported'))
def verify_rule_diagnostic(rule_id: str, bdd_ctx: dict[str, Any]):
    report: PRDLintReport = bdd_ctx["report"]
    matching = [d for d in report.diagnostics if d.rule_id == rule_id]
    assert len(matching) > 0


@then("a line-level suggestion provides an authorized persona replacement.")
def verify_persona_suggestion(bdd_ctx: dict[str, Any]):
    report: PRDLintReport = bdd_ctx["report"]
    matching = [d for d in report.diagnostics if d.rule_id == "PRD-LINT-001"]
    assert len(matching) == 1
    diag = matching[0]
    assert diag.suggestion is not None
    assert "target_persona:" in diag.suggestion.suggested_text
    assert any(p in diag.suggestion.remediation_hint for p in KNOWN_PERSONAS)


@given(parsers.parse('a PRD document containing subjective outcome "{outcome_text}"'))
def prd_with_subjective_outcome(outcome_text: str, bdd_ctx: dict[str, Any]):
    content = f"""---
id: PRD-0043
title: Subjective Outcome Demo
status: Idea
target_persona: Alex
component: prd
---

# PRD-0043: Subjective Outcome Demo

## Problem Statement
Users experience lag.

## What good looks like
Observable performance.

## What this does not do
Does not rely on gut feel.

## Checkable Outcomes
- {outcome_text}
"""
    bdd_ctx["content"] = content


@then(parsers.parse('a diagnostic with rule "{rule_id}" is reported on that line'))
def verify_diagnostic_on_line(rule_id: str, bdd_ctx: dict[str, Any]):
    report: PRDLintReport = bdd_ctx["report"]
    matching = [d for d in report.diagnostics if d.rule_id == rule_id]
    assert len(matching) > 0
    assert matching[0].line >= 20  # checkable outcomes line


@then("the suggested text replaces the subjective terms with measurable behavioral contracts.")
def verify_subjective_rewrite(bdd_ctx: dict[str, Any]):
    report: PRDLintReport = bdd_ctx["report"]
    matching = [d for d in report.diagnostics if d.rule_id == "PRD-LINT-002"]
    assert len(matching) > 0
    diag = matching[0]
    assert diag.suggestion is not None
    assert "fast" not in diag.suggestion.suggested_text.lower()
    assert "modern" not in diag.suggestion.suggested_text.lower()
    assert len(diag.suggestion.suggested_text) > 0


@given("a PRD document with valid frontmatter, persona, problem statement, and checkable outcomes")
def valid_prd_document(bdd_ctx: dict[str, Any]):
    content = """---
id: PRD-0044
title: Compliant Specification Demo
status: Accepted
target_persona: Jordan
component: core
---

# PRD-0044: Compliant Specification Demo

## Problem Statement
Engineering leads need verifiable gates.

## What good looks like
All linters pass cleanly.

## What this does not do
Does not bypass validation checks.

## Checkable Outcomes
- Running spec-ops prd lint flags 0 violations
- Execution completes within 200ms latency threshold
"""
    bdd_ctx["content"] = content


@then("the report marks the document as valid with zero error diagnostics.")
def verify_report_valid(bdd_ctx: dict[str, Any]):
    report: PRDLintReport = bdd_ctx["report"]
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.falsifiable_count == 2
    assert report.unfalsifiable_count == 0
