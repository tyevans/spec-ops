---
id: '0093'
title: Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RESC-07
governing_prd: PRD-0004
---

# US-0093 — Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer actively patching code inside a rescued worktree,
  - **I want** to run `spec-ops rescue test --step <step-name>` or `--only-failed` to rerun only the broken preflight check,
  - **So that** I can iterate with rapid sub-2-second feedback cycles without waiting for the full preflight verification suite until final integration into `main`.

## Acceptance Criteria

```gherkin
Scenario: Running isolated failed step with cached preflight results
Given a rescued worktree ".worktrees/task-0010" where "uv lock --check" and "spec-ops health" previously passed
And only the unit test suite "uv run pytest tests/test_visualizer.py" failed
When the engineer is inside ".worktrees/task-0010" and executes "spec-ops rescue test --only-failed"
Then only "uv run pytest tests/test_visualizer.py" is re-executed
And previously passed invariant checks and lockfile validations are skipped
And the check completes in under 3 seconds.
```
```gherkin
Scenario: Rapid feedback cycle during local rescue iteration
Given the engineer edits a file inside the rescued worktree
When the engineer runs "spec-ops rescue test --step lint"
Then only the linting and formatting check ("ruff check && ruff format --check") runs
And the terminal displays immediate pass/fail status without running integration tests.
```
```gherkin
Scenario: Enforcing mandatory full-suite revalidation upon rescue completion
Given the engineer has iterated using targeted step checks
When the engineer runs "spec-ops rescue TASK-0010 --complete"
Then the rescue manager bypasses all caches and executes the complete, un-truncated preflight pipeline:
| Step 1 | uv lock --check         |
| Step 2 | spec-ops health         |
| Step 3 | ruff check              |
| Step 4 | full pytest test suite  |
And integration into "main" proceeds only when all preflight stages pass unconditionally.
-
```

## Rationale & Compelling Value
- **Adoption**: Removes the agonizing friction of running a 5-minute preflight suite for every minor 1-line edit during a rescue.
  - **Regular Usage**: Used continuously during active rescue sessions to maintain developer flow state.
  - **Compelling Value**: Accelerates rescue resolution velocity by over 80% while preserving absolute invariant rigor on the final merge gate.

---
