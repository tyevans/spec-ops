"""Unit tests for PRDLintEngine and line-level remediation models."""

from __future__ import annotations

from pathlib import Path

from spec_ops.prd.lint_engine import (
    RULE_EMPTY_OUTCOMES,
    RULE_FRONTMATTER_SYNTAX,
    RULE_MISSING_PERSONA,
    RULE_MISSING_SECTION,
    RULE_UNFALSIFIABLE_OUTCOME,
    PRDLintEngine,
)


def test_missing_frontmatter():
    engine = PRDLintEngine()
    report = engine.lint_content("# Bare Document\nNo frontmatter.\n")
    assert report.is_valid is False
    assert any(d.rule_id == RULE_FRONTMATTER_SYNTAX for d in report.diagnostics)


def test_missing_persona_suggestion():
    engine = PRDLintEngine()
    doc = """---
id: PRD-0001
title: Test Title
status: Idea
target_persona: unknown
component: core
---
## Problem Statement
Test
## What good looks like
Test
## What this does not do
Test
## Checkable Outcomes
- Observable test
"""
    report = engine.lint_content(doc)
    assert report.is_valid is False
    diag = next(d for d in report.diagnostics if d.rule_id == RULE_MISSING_PERSONA)
    assert diag.line == 5
    assert diag.suggestion is not None
    assert "target_persona:" in diag.suggestion.suggested_text


def test_unfalsifiable_outcome_suggestions():
    engine = PRDLintEngine()
    doc = """---
id: PRD-0001
title: Test Title
status: Idea
target_persona: Alex
component: core
---
## Problem Statement
Test
## What good looks like
Test
## What this does not do
Test
## Checkable Outcomes
- The web application is fast and modern
- It is simple and easy to configure
"""
    report = engine.lint_content(doc)
    assert report.is_valid is False
    unfalsifiable = [d for d in report.diagnostics if d.rule_id == RULE_UNFALSIFIABLE_OUTCOME]
    assert len(unfalsifiable) == 2
    for diag in unfalsifiable:
        assert diag.suggestion is not None
        assert len(diag.suggestion.suggested_text) > 0
        assert len(diag.suggestion.remediation_hint) > 0


def test_missing_required_sections():
    engine = PRDLintEngine()
    doc = """---
id: PRD-0001
title: Test Title
status: Idea
target_persona: Alex
component: core
---
## Checkable Outcomes
- Observable test
"""
    report = engine.lint_content(doc)
    assert report.is_valid is False
    section_diags = [d for d in report.diagnostics if d.rule_id == RULE_MISSING_SECTION]
    assert len(section_diags) >= 2


def test_empty_checkable_outcomes():
    engine = PRDLintEngine()
    doc = """---
id: PRD-0001
title: Test Title
status: Idea
target_persona: Alex
component: core
---
## Problem Statement
Test
## What good looks like
Test
## What this does not do
Test
## Checkable Outcomes
"""
    report = engine.lint_content(doc)
    assert report.is_valid is False
    assert any(d.rule_id == RULE_EMPTY_OUTCOMES for d in report.diagnostics)


def test_lint_file_on_disk(tmp_path: Path):
    engine = PRDLintEngine(root_dir=tmp_path)
    # Non-existent file
    rep_missing = engine.lint_file(tmp_path / "non_existent.md")
    assert rep_missing.is_valid is False
    assert "File not found" in rep_missing.diagnostics[0].message

    # Valid file on disk
    valid_file = tmp_path / "prd-0001.md"
    valid_file.write_text(
        """---
id: PRD-0001
title: Valid File
status: Idea
target_persona: Taylor
component: core
---
## Problem Statement
Problem
## What good looks like
Good
## What this does not do
Anti
## Checkable Outcomes
- Running spec-ops prd lint passes
""",
        encoding="utf-8",
    )
    rep_valid = engine.lint_file(valid_file)
    assert rep_valid.is_valid is True
    assert rep_valid.error_count == 0

    data = rep_valid.to_dict()
    assert data["is_valid"] is True
    assert data["error_count"] == 0
