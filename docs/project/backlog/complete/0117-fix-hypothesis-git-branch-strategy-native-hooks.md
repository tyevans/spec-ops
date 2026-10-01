---
id: '0117'
title: Constrain Hypothesis Git Branch Strategy in Native Hooks Property Tests
status: Complete
dependencies:
- TASK-0084
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0068
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T00:22:04.525759+00:00'
---

# TASK-0117: Constrain Hypothesis Git Branch Strategy in Native Hooks Property Tests

## Summary
Constrain the Hypothesis `BRANCH_STRATEGY` in `tests/test_native_hooks_properties.py` so that generated branch names conform to valid git reference naming rules. Prevent `subprocess.CalledProcessError` during property tests caused by git refusing invalid branch names such as `-` or paths with trailing `.lock`.

## Problem Statement & Context
During preflight verification of TASK-0084 (`.worktrees/task-0084`), `tests/test_native_hooks_properties.py` failed under Hypothesis property testing:
```
subprocess.CalledProcessError: Command '['git', 'checkout', '-b', '-']' returned non-zero exit status 128.
Failing test case: test_hypothesis_backlog_isolation_invariant(..., branch_name='-', staged_path='docs/project/backlog/PRIORITY.md')
```
Git interprets `-` as an argument shorthand for the previous branch or an invalid branch name, and rejects branches beginning or ending with hyphens, containing consecutive slashes, or ending with `.lock`. Because `BRANCH_STRATEGY` only filtered leading/trailing `/`, `//`, and `..`, Hypothesis generated single-hyphen strings (`'-'`), crashing `git checkout -b` during test setup.

Per the SpecOps Dogfooding / Orchestration Failure Invariant in `AGENTS.md`, any orchestration or test failure encountered during subagent execution must be captured as an actionable task in the backlog and resolved.

## User Stories & Scenarios Satisfied
- **US-0068: Native Git Hooks & Multi-Agent Worktree Enforcement**
  - *Scenario: Generative Property Testing for Backlog Isolation Invariant*
    - Given generated git branch names and staged file paths
    - When property-based tests exercise native hook abort logic
    - Then all generated branch names are syntactically valid in git
    - And tests verify backlog isolation invariants without crashing on git checkout.

## Architectural Invariants & Seams
- **Property-Based Testing (Hypothesis) & Mutation Testing (Mutmut)** (ADR-0009): Property test generators must generate valid domain inputs for blackbox test harnesses.
- **Blackbox Frontdoor Verification** (ADR-0003): Tests interact through genuine git commands (`git checkout -b`, `git commit`).
- **File Length Limit (<500 lines)**: `tests/test_native_hooks_properties.py` remains well under line limits (ADR-0002).

## Resolution & Definition of Done
1. Update `BRANCH_STRATEGY` in `tests/test_native_hooks_properties.py` to require valid alphanumeric boundaries and filter invalid git ref sequences:
   - Match `^[a-zA-Z0-9][a-zA-Z0-9_\-/]{0,28}[a-zA-Z0-9]$`
   - Exclude `//` and `..`
   - Exclude `.lock` endings
2. Verify `uv run pytest tests/test_native_hooks_properties.py` passes 100% of property iterations without shrinking failures.
