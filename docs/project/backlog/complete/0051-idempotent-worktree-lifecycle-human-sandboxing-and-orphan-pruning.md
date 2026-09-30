---
id: '0051'
title: Idempotent Worktree Lifecycle Management and Collision Recovery
status: Complete
dependencies:
- TASK-0018
- TASK-0044
governing_adrs:
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0086
target_bc: rescue
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0051: Idempotent Worktree Lifecycle Management and Collision Recovery

## Summary
Implement idempotent git worktree lifecycle management with automatic branch collision recovery, stale metadata reconciliation, and atomic resource teardown upon task finalization.

## Problem Statement & Context
Repeated worker runs, interrupted agent sessions, and process crashes frequently leave dangling git worktree metadata, locked branches, and orphaned directories. When a new worker attempts to claim a task whose branch or worktree directory already exists, git throws fatal errors. SpecOps requires an idempotent worktree lifecycle engine that safely reclaims stale worktrees and recovers from branch collisions.

## User Stories & Scenarios Satisfied
- **US-0086: Idempotent Worktree Lifecycle Management and Stale Worktree Reconciliation**
  - *Scenario: Idempotent Worktree Creation with Branch Collision Recovery*
  - *Scenario: Atomic Teardown and Resource Cleanup upon Task Finalization*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Worktree lifecycle manager in `src/spec_ops/rescue/lifecycle.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated combinations of clean, dirty, completed, and refined worktree states assert that idempotent creation never overwrites uncommitted human modifications without explicit override flags.
- **Mutmut Mutation Scope**: Worktree reconciliation and branch collision recovery logic in `src/spec_ops/rescue/lifecycle.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Creating a worktree for a task whose branch or directory already exists automatically inspects for uncommitted human changes; if none exist, prunes stale metadata via `git worktree prune`, resets the branch, and provisions cleanly without errors.
2. Finalizing a task atomically cleans up worktree directories, removes tracked branches, and restores repository state.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
