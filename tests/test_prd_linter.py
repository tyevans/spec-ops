"""Unit and property tests for PRD markdown linter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from spec_ops.prd.linter import (
    COMPOUND_PHRASES,
    SUBJECTIVE_WORDS,
    LintOutcomeCheck,
    LintResult,
    LintViolation,
    PRDLinter,
)


def test_subjective_heuristics_all_compound_phrases():
    linter = PRDLinter()
    assert linter.check_subjective_terms("The interface is clean and modern") == "clean and modern"
    assert linter.check_subjective_terms("THE INTERFACE IS CLEAN AND MODERN") == "clean and modern"
    assert linter.check_subjective_terms("The system is fast and responsive") == "fast and responsive"
    assert linter.check_subjective_terms("THE SYSTEM IS FAST AND RESPONSIVE") == "fast and responsive"
    assert linter.check_subjective_terms("A simple and intuitive tool") == "simple and intuitive"
    assert linter.check_subjective_terms("A SIMPLE AND INTUITIVE TOOL") == "simple and intuitive"
    assert linter.check_subjective_terms("An intuitive and easy flow") == "intuitive and easy"
    assert linter.check_subjective_terms("AN INTUITIVE AND EASY FLOW") == "intuitive and easy"
    assert linter.check_subjective_terms("Very easy to use for new users") == "easy to use"
    assert linter.check_subjective_terms("VERY EASY TO USE FOR NEW USERS") == "easy to use"


def test_subjective_heuristics_all_words():
    linter = PRDLinter()
    for word in SUBJECTIVE_WORDS:
        found = linter.check_subjective_terms(f"This is a {word} solution.")
        assert found == word.lower()
        found_upper = linter.check_subjective_terms(f"THIS IS A {word.upper()} SOLUTION.")
        assert found_upper == word.lower()
    assert linter.check_subjective_terms("Running 'spec-ops audit' exits with 0") is None


def test_lint_text_frontmatter_checks():
    linter = PRDLinter()
    res1 = linter.lint_text("# No Frontmatter\n## Who this is for\n")
    assert not res1.is_valid
    assert res1.file_path == "<string>"
    assert len(res1.violations) >= 1
    v0 = res1.violations[0]
    assert v0.file_path == "<string>"
    assert v0.line == 1
    assert v0.message == "Missing or invalid YAML frontmatter"
    assert v0.guidance == "Ensure document starts with '---' containing metadata"

    doc_missing_persona = """---
id: '0001'
title: Test
---
# Title
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. Returns 0
"""
    res2 = linter.lint_text(doc_missing_persona, file_path="custom.md")
    assert not res2.is_valid
    assert res2.file_path == "custom.md"
    vp = [v for v in res2.violations if v.message == "Target persona unmapped"][0]
    assert vp.file_path == "custom.md"
    assert vp.line == 1
    assert vp.message == "Target persona unmapped"
    assert vp.guidance == "Map a target persona from docs/project/user_stories/PERSONAS.md"

    doc_explicit_unmapped = """---
id: '0001'
title: Test
target_persona: unmapped
---
# Title
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. Returns 0
"""
    res3 = linter.lint_text(doc_explicit_unmapped)
    assert not res3.is_valid
    vp3 = [v for v in res3.violations if v.message == "Target persona unmapped"][0]
    assert vp3.line == 4
    assert vp3.guidance == "Map a target persona from docs/project/user_stories/PERSONAS.md"

    for unmapped_val in ("", "none", "unknown"):
        doc_un = f"---\nid: '0001'\ntitle: Test\ntarget_persona: {unmapped_val}\n---\n# Title\n## Who this is for\n- C\n## What good looks like\n1. G\n## What this does not do\n- A\n## Checkable Outcomes\n1. R0\n"
        res_un = linter.lint_text(doc_un)
        assert any(v.message == "Target persona unmapped" for v in res_un.violations)


def test_lint_text_section_checks():
    linter = PRDLinter()
    doc_no_sections = """---
id: '0001'
title: Test
target_persona: Taylor
---
# Title
"""
    res = linter.lint_text(doc_no_sections)
    assert not res.is_valid
    assert len(res.violations) == 4

    v_prob = [v for v in res.violations if "## Who this is for" in v.message][0]
    assert v_prob.line == 1
    assert v_prob.message == "Missing required section: '## Who this is for' or '## Problem Statement'"
    assert v_prob.guidance == "Define the user problem statement and target persona context"

    v_good = [v for v in res.violations if "## What good looks like" in v.message][0]
    assert v_good.line == 1
    assert v_good.message == "Missing required section: '## What good looks like'"
    assert v_good.guidance == "Define core capabilities describing what good looks like"

    v_anti = [v for v in res.violations if "## What this does not do" in v.message][0]
    assert v_anti.line == 1
    assert v_anti.message == "Missing required section: '## What this does not do'"
    assert v_anti.guidance == "Define explicit anti-goals to prevent multi-agent scope creep"

    v_out = [v for v in res.violations if "## Checkable Outcomes" in v.message][0]
    assert v_out.line == 1
    assert v_out.message == "Missing required section: '## Checkable Outcomes'"
    assert v_out.guidance == "Define at least one falsifiable outcome with observable verification criteria"

    doc_problem_statement = """---
id: '0001'
title: Test
target_persona: Taylor
---
# Title
## Problem Statement
Problem details here.
## What good looks like
1. Good
## What this does not do
- None
## Checkable Outcomes
1. Returns 0
"""
    res_ps = linter.lint_text(doc_problem_statement)
    assert res_ps.is_valid
    assert not any("Missing required section: '## Who this is for'" in v.message for v in res_ps.violations)


def test_lint_text_uppercase_headers():
    linter = PRDLinter()
    doc_upper = """---
id: '0001'
title: Test
target_persona: Taylor
---
# Title
## WHO THIS IS FOR
- Context
## WHAT GOOD LOOKS LIKE
1. Good
## WHAT THIS DOES NOT DO
- Anti
## CHECKABLE OUTCOMES
1. Returns 0
"""
    res = linter.lint_text(doc_upper, file_path="upper.md")
    assert res.is_valid
    assert len(res.violations) == 0
    assert len(res.outcome_checks) == 1
    assert res.outcome_checks[0].is_falsifiable


def test_lint_text_outcomes_parsing_and_heuristics():
    linter = PRDLinter()
    doc_empty = """---
id: '0001'
title: Test
target_persona: Taylor
---
# Title
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- None
## Checkable Outcomes
<!-- only comments -->
"""
    res_empty = linter.lint_text(doc_empty)
    assert not res_empty.is_valid
    v_empty = [v for v in res_empty.violations if v.message == "No checkable outcomes defined"][0]
    assert v_empty.line == 13
    assert v_empty.message == "No checkable outcomes defined"
    assert v_empty.guidance == "Provide at least one falsifiable, checkable outcome"

    doc_mixed = """---
id: '0001'
title: Test
target_persona: Taylor
---
# Title
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- None
## Checkable Outcomes
1. The UI looks clean and modern
- Running 'spec-ops prd' returns code 0
"""
    res_mixed = linter.lint_text(doc_mixed)
    assert not res_mixed.is_valid
    assert len(res_mixed.outcome_checks) == 2
    oc0 = res_mixed.outcome_checks[0]
    assert oc0.line == 14
    assert not oc0.is_falsifiable
    assert oc0.subjective_term == "clean and modern"
    assert oc0.text == "The UI looks clean and modern"

    oc1 = res_mixed.outcome_checks[1]
    assert oc1.line == 15
    assert oc1.is_falsifiable
    assert oc1.text == "Running 'spec-ops prd' returns code 0"

    v_subj = res_mixed.violations[0]
    assert v_subj.line == 14
    assert v_subj.message == "Subjective adjective 'clean and modern' is unfalsifiable"
    assert v_subj.guidance == "Replace subjective adjectives with measurable frontdoor criteria or observable CLI/API assertions"


def test_lint_file_and_lint_path(tmp_path: Path):
    linter_no_root = PRDLinter()
    assert linter_no_root.lint_path(None) == []

    linter = PRDLinter(root_dir=tmp_path)
    res_missing = linter.lint_file(tmp_path / "nonexistent.md")
    assert not res_missing.is_valid
    v_miss = res_missing.violations[0]
    assert v_miss.line == 1
    assert "File not found" in v_miss.message
    assert v_miss.guidance == "Ensure target PRD file exists on disk"

    dummy_file = tmp_path / "unreadable.md"
    dummy_file.write_text("sample", encoding="utf-8")
    with patch.object(Path, "read_text", side_effect=PermissionError("Permission denied")):
        res_err = linter.lint_file(dummy_file)
        assert not res_err.is_valid
        v_err = res_err.violations[0]
        assert v_err.line == 1
        assert "Error reading file: Permission denied" in v_err.message
        assert v_err.guidance == "Check file permissions and UTF-8 encoding"

    prd_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    reg = prd_dir.parent / "REGISTRY.md"
    reg.write_text("# Registry\n", encoding="utf-8")

    good_prd = prd_dir / "prd-0001.md"
    good_prd.write_text("""---
id: '0001'
title: Valid PRD
target_persona: Taylor
---
# PRD-0001
## Who this is for
- Taylor
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. Running 'spec-ops' returns code 0
""")

    results_file = linter.lint_path(good_prd)
    assert len(results_file) == 1
    assert results_file[0].is_valid

    results_dir = linter.lint_path(tmp_path / "docs" / "project" / "product")
    assert len(results_dir) == 1
    assert results_dir[0].is_valid

    results_auto = linter.lint_path(None)
    assert len(results_auto) == 1
    assert results_auto[0].is_valid


def test_format_report_outputs():
    linter = PRDLinter()
    valid_res = LintResult(
        file_path="valid.md",
        is_valid=True,
        violations=[],
        outcome_checks=[LintOutcomeCheck(line=10, text="Run cmd", is_falsifiable=True)],
    )
    rep_valid = linter.format_report([valid_res])
    assert "=== PRD Markdown Lint: valid.md ===" in rep_valid
    assert "[Outcome 1] passes as a valid falsifiable frontdoor contract" in rep_valid
    assert "All structural sections and falsifiability heuristics passed." in rep_valid
    assert "All PRDs passed falsifiable markdown linting." in rep_valid

    invalid_res = LintResult(
        file_path="invalid.md",
        is_valid=False,
        violations=[
            LintViolation(
                file_path="invalid.md",
                line=5,
                message="Subjective adjective 'fast' is unfalsifiable",
                guidance="Use frontdoor contract",
            )
        ],
        outcome_checks=[
            LintOutcomeCheck(
                line=5,
                text="Is fast",
                is_falsifiable=False,
                subjective_term="fast",
            )
        ],
    )
    rep_invalid = linter.format_report([invalid_res])
    assert "=== PRD Markdown Lint: invalid.md ===" in rep_invalid
    assert "[Outcome 1] flags Outcome 1: Subjective adjective 'fast' is unfalsifiable" in rep_invalid
    assert 'Line 5 violation: "Subjective adjective \'fast\' is unfalsifiable"' in rep_invalid
    assert 'guidance: "Use frontdoor contract"' in rep_invalid
    assert "Lint failed with 1 violation(s)." in rep_invalid


@given(st.text(max_size=300))
def test_hypothesis_linter_never_crashes(content: str):
    linter = PRDLinter()
    res = linter.lint_text(content)
    assert isinstance(res.is_valid, bool)
    assert isinstance(res.violations, list)


@given(has_anti_goals=st.booleans(), has_outcomes=st.booleans())
def test_hypothesis_required_headers(has_anti_goals: bool, has_outcomes: bool):
    linter = PRDLinter()
    parts = [
        "---",
        "id: '0001'",
        "title: Prop",
        "target_persona: Taylor",
        "---",
        "# PRD-0001",
        "## Who this is for",
        "- Context",
        "## What good looks like",
        "1. Good",
    ]
    if has_anti_goals:
        parts.extend(["## What this does not do", "- Anti"])
    if has_outcomes:
        parts.extend(["## Checkable Outcomes", "1. Returns 0"])
    res = linter.lint_text("\n".join(parts))
    msgs = [v.message for v in res.violations]
    assert ("Missing required section: '## What this does not do'" in msgs) == (not has_anti_goals)
    assert ("Missing required section: '## Checkable Outcomes'" in msgs) == (not has_outcomes)


@given(adj=st.sampled_from(["clean", "intuitive", "modern", "fast"]))
def test_hypothesis_subjective_adjectives(adj: str):
    linter = PRDLinter()
    doc = f"""---
id: '0001'
title: Prop
target_persona: Taylor
---
# PRD-0001
## Who this is for
- Context
## What good looks like
1. Good
## What this does not do
- Anti
## Checkable Outcomes
1. System is {adj} for users
"""
    res = linter.lint_text(doc)
    assert not res.is_valid
    assert any(f"Subjective adjective '{adj}' is unfalsifiable" in v.message for v in res.violations)
