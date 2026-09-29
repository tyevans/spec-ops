---
id: '0087'
title: Interactive Preserved Worktree Triage and Failure Diagnostic Breakdown
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RESC-01
governing_prd: PRD-0004
---

# US-0087 — Interactive Preserved Worktree Triage and Failure Diagnostic Breakdown

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer stepping in to rescue a task after an autonomous agent has exhausted its maximum retry attempts,
  - **I want** to execute `spec-ops rescue triage <task-id>` to interactively inspect agent modifications, review categorized failure root causes, and examine file-by-file AST and line-count diffs,
  - **So that** I can instantly pinpoint why the worker stalled—whether a broken test, an invariant violation, or a lockfile drift—without sifting through raw, unformatted preflight logs.

## Acceptance Criteria

```gherkin
Scenario: Categorizing preflight failure modes in a stalled worktree
Given an autonomous worker session for "TASK-0012" has exhausted its 3 self-healing attempts
And the worktree ".worktrees/task-0012" is preserved on branch "feat/TASK-0012"
When the engineer executes "spec-ops rescue triage TASK-0012"
Then the CLI displays a categorized diagnostic summary:
| Category               | Status | Details                                                     |
| File Length Invariant  | FAIL   | src/spec_ops/core/parser.py (514 lines > 500 limit)         |
| Test Suite             | FAIL   | tests/test_parser.py::test_parse_syntax (AssertionError)   |
| Lockfile Integrity     | PASS   | uv.lock synchronized                                        |
| Working Tree State     | DIRTY  | 3 modified files, 1 untracked file                          |
And the CLI presents an interactive triage menu with options: "[d]iff, [p]atch, [s]hell, [r]eset, [c]omplete, [q]uit".
```
```gherkin
Scenario: Inspecting AST and line count diffs per modified file
Given the engineer is in the interactive triage menu for "TASK-0012"
When the engineer selects "[d]iff" and chooses "src/spec_ops/core/parser.py"
Then the CLI renders a syntax-highlighted diff comparing the worktree file against "HEAD"
And displays the net line delta (+42 lines) and headroom to the 500-line invariant limit (-14 lines headroom, VIOLATION).
```
```gherkin
Scenario: Navigating directly to recommended rescue actions
Given the failure breakdown indicates only file-length invariant violations with all tests passing
When the triage analysis completes
Then the CLI outputs a targeted recommendation:
"Recommendation: Code passes tests but violates file limits. Run 'spec-ops rescue shell TASK-0012' to decompose parser.py, then 'spec-ops rescue TASK-0012 --complete'."
-
```

## Rationale & Compelling Value
- **Adoption**: Eliminates the intimidating "wall of terminal text" when an agent crashes. Gives junior and senior engineers a structured, interactive entry point.
  - **Regular Usage**: Used daily whenever an agent hits a complex edge case or exceeds modular file boundaries.
  - **Compelling Value**: Slashes triage time from 10–15 minutes down to 30 seconds by automatically classifying failure root causes.

---
