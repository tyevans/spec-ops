---
id: '0101'
title: Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation
status: Refined
created: 2026-09-30
dependencies:
  - TASK-0052
  - TASK-0046
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0007
  - ADR-0008
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0093
target_bc: rescue
---

# TASK-0101: Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation

## Summary
Implement a fast incremental in-worktree preflight test runner with step isolation and caching (`spec-ops rescue test --step <step> [--only-failed]`). Allow developers rescuing stalled worktrees to rapidly re-execute single failing test steps or preflight gates without executing the entire multi-minute pipeline, while guaranteeing that full verification executes before merge.

## Problem Statement & Context
When human developers rescue stalled autonomous worktrees, fixing a single syntax error or line-length warning currently requires rerunning the entire multi-minute preflight suite (`uv lock --check && uv run pytest && uv run spec-ops health`). This latency kills developer flow during iterative troubleshooting. SpecOps requires targeted preflight step caching and isolated re-execution.

## User Stories & Scenarios Satisfied
- **US-0093: Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation**
  - *Scenario: Running isolated failed step with cached preflight results*
    - Given a worktree where only the linter or a specific test file failed
    - When the developer runs `spec-ops rescue test --only-failed`
    - Then only the previously failed step is re-executed in under 3 seconds.
  - *Scenario: Rapid feedback cycle during local rescue iteration*
    - Given a developer making iterative fixes to a single module
    - When executing `spec-ops rescue test --step pytest`
    - Then cached steps are skipped and results are reported immediately.
  - *Scenario: Enforcing mandatory full-suite revalidation upon rescue completion*
    - Given an incremental fix verified in isolation
    - When the developer completes the rescue via `spec-ops rescue <task-id> --complete`
    - Then incremental caches are bypassed and the full suite must pass before merge.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Step test runner in `src/spec_ops/rescue/incremental_runner.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that any dirty file modifications outside the isolated step invalidate step caches deterministically.
- **Mutmut Mutation Scope**: Step caching and failure tracking in `src/spec_ops/rescue/incremental_runner.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Inside a rescued worktree, executing `spec-ops rescue test --only-failed` reruns only the previously failed preflight step in under 3 seconds.
2. Executing `spec-ops rescue test --step <name>` executes only the designated step (e.g. `health`, `lock`, `pytest`).
3. Final task completion (`spec-ops rescue <task-id> --complete`) forces a clean, cache-free full preflight run.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
