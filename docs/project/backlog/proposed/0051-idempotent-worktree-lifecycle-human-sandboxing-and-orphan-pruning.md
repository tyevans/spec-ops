---
id: '0051'
title: Idempotent Worktree Lifecycle Management, Human Sandboxing, and Zero-Pollution Pruning
status: Proposed
created: 2026-09-29
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
  - US-0092
  - US-0038
target_bc: rescue
---

# TASK-0051: Idempotent Worktree Lifecycle Management, Human Sandboxing, and Zero-Pollution Pruning

## Summary
Implement idempotent git worktree lifecycle management with automatic branch collision recovery and metadata pruning, provide human developer worktree sandboxing commands (`spec-ops worktree start <task-id>` and `spec-ops worktree finish`), and deliver zero-pollution worktree garbage collection via `spec-ops rescue prune [--dry-run]` to safely reclaim disk space while guarding active human workspaces.

## Problem Statement & Context
Repeated worker runs, interrupted agent sessions, and process crashes frequently leave dangling git worktree metadata, locked branches, and orphaned directories consuming gigabytes of disk space. When a new worker attempts to claim a task whose branch or worktree directory already exists, git throws fatal errors. Furthermore, human software engineers (Riley) lack a first-class command to spawn and finalize isolated feature worktrees, and running bulk cleanup tools risks deleting active human rescue work.

## User Stories & Scenarios Satisfied
- **US-0086: Idempotent Worktree Lifecycle Management and Stale Worktree Reconciliation**
  - *Scenario: Idempotent Worktree Creation with Branch Collision Recovery*
  - *Scenario: Atomic Teardown and Resource Cleanup upon Task Finalization*
- **US-0092: Zero-Pollution Worktree Garbage Collection and Orphan Pruning**
  - *Scenario: Detecting and safely pruning worktrees of completed tasks*
  - *Scenario: Guarding active and dirty human rescue worktrees from accidental deletion*
  - *Scenario: Dry-run preview of reclaimable disk space and dangling branches*
- **US-0038: Zero-Toil Human Worktree Sandboxing for Focused Feature Development**
  - *Scenario: Spawning a clean human development worktree*
  - *Scenario: Preflight verification and completion from within the worktree*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Worktree lifecycle manager in `src/spec_ops/rescue/lifecycle.py` and pruning garbage collector in `src/spec_ops/rescue/prune.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated combinations of clean, dirty, completed, and refined worktree states assert that `rescue prune` never selects or modifies a worktree containing uncommitted human modifications or assigned to an active uncompleted task.
- **Mutmut Mutation Scope**: Worktree reconciliation, dirty state detection, and pruning filter logic in `src/spec_ops/rescue/lifecycle.py` and `src/spec_ops/rescue/prune.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Creating a worktree for a task whose branch or directory already exists automatically inspects for uncommitted human changes; if none exist, prunes stale metadata via `git worktree prune`, resets the branch, and provisions cleanly without errors.
2. Executing `spec-ops worktree start <task-id>` creates an isolated worktree at `.worktrees/<task-id>`, checks out `feat/<task-id>`, sets up workspace environment links, and outputs navigation instructions.
3. Executing `spec-ops worktree finish` inside the worktree runs preflight verification, squash-merges into `main` under `MERGE_LOCK`, advances task status to `complete/`, and removes the worktree.
4. Executing `spec-ops rescue prune` detects orphaned worktrees of completed tasks, safely runs `git worktree remove --force`, deletes merged branches, and skips any worktrees with uncommitted changes with an explicit warning.
5. Executing `spec-ops rescue prune --dry-run` displays a table of candidate worktrees and reclaimable disk space without mutating filesystem state.
6. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
