---
id: '0046'
title: Extensible Multi-Stage Preflight Validation Pipeline with Early Fast-Fail Gates
status: Refined
dependencies:
- TASK-0020
- TASK-0044
governing_adrs:
- ADR-0002
- ADR-0003
- ADR-0004
- ADR-0007
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0082
- US-0028
- US-0037
- US-0115
target_bc: worker
---

# TASK-0046: Extensible Multi-Stage Preflight Validation Pipeline with Early Fast-Fail Gates

## Summary
Build the extensible multi-stage preflight validation pipeline executing configured verification stages (`lockfile`, `health`, `tests`) in deterministic order with early fast-fail capability. Implement an in-worktree iterative self-healing feedback loop that captures exact failure logs and line locations into agent retry prompts, preserves worktrees upon retry exhaustion, and enforces local pre-commit hooks (`spec-ops-health`) for file-length invariants (<500 lines) and proactive warnings (>=400 lines).

## Problem Statement & Context
Monolithic preflight checks execute slow test suites even when fast static checks (lockfile drift, line length limits) have already failed, wasting compute and delaying feedback loops. Furthermore, when an autonomous worker encounters preflight failures, it needs structured feedback indicating the exact failing stage, line number, and error trace to self-heal. Finally, human developers require local pre-commit hooks that warn proactively at 400 lines and block at 500 lines before bad commits are pushed.

## User Stories & Scenarios Satisfied
- **US-0082: Multi-Stage Extensible Preflight Validation Pipeline with Early Fast-Fail**
  - *Scenario: Fast-Fail on Early Security and Lockfile Verification Stage*
  - *Scenario: Complete Pipeline Execution Across All Configured Gates*
- **US-0028: In-Worktree Pre-Flight Verification and Iterative Self-Healing Feedback Loop**
  - *Scenario: Autonomous Self-Healing on Preflight Health Check Violation*
  - *Scenario: Graceful Worktree Preservation on Exhausted Self-Healing Retries*
- **US-0037: Local Pre-Commit Invariant Gate and Proactive Anti-Rot Warnings**
  - *Scenario: Blocking staged file that exceeds hard invariant limit*
  - *Scenario: Proactive warning on files approaching limit without blocking commit*
  - *Scenario: Verifying PRIORITY.md and disk state synchronization*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Preflight stage runner in `src/spec_ops/worker/preflight.py` and hook evaluator in `src/spec_ops/worker/hooks.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomized stage configurations assert that any stage failure immediately aborts downstream stages and isolates the root failure cause with zero subsequent side effects.
- **Mutmut Mutation Scope**: Pipeline stage orchestration and exit code propagation in `src/spec_ops/worker/preflight.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Preflight pipeline executes stages sequentially (`lockfile` -> `health` -> `test`); failing stage 1 (`uv lock --check`) halts immediately without running stages 2 or 3.
2. In-worktree preflight failure appends the exact error traceback, violating file, and line number to `.task-prompt.md` and re-invokes the agent up to configured maximum retries (default: 3).
3. If retries are exhausted, the worktree is preserved intact at `.worktrees/<task-id>` with diagnostic failure logs, and the CLI outputs `spec-ops rescue <task-id>`.
4. The `spec-ops-health` pre-commit hook rejects commits containing files >=500 lines with an invariant error, emits a non-blocking warning for files >=400 lines, and verifies `PRIORITY.md` sync.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
