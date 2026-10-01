---
id: 0094
title: Zero-Pollution Worktree Garbage Collection and Orphan Pruning
status: Complete
dependencies:
- TASK-0051
governing_adrs:
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0092
target_bc: rescue
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0094: Zero-Pollution Worktree Garbage Collection and Orphan Pruning

## Summary
Implement zero-pollution worktree garbage collection via `spec-ops rescue prune [--dry-run]` to detect and safely clean up orphaned git worktrees, dangling agent branches, and completed task leftovers while strictly protecting dirty human workspaces.

## Problem Statement & Context
Multiple autonomous agent runs and interrupted workflows leave orphaned directories in `.worktrees/` that consume gigabytes of disk space and cause git worktree locking conflicts. SpecOps needs automated garbage collection that detects worktrees of completed tasks, protects dirty human worktrees from accidental deletion, and provides dry-run disk space reclamation previews.

## User Stories & Scenarios Satisfied
- **US-0092: Zero-Pollution Worktree Garbage Collection and Orphan Pruning**
  - *Scenario: Detecting and safely pruning worktrees of completed tasks*
  - *Scenario: Guarding active and dirty human rescue worktrees from accidental deletion*
  - *Scenario: Dry-run preview of reclaimable disk space and dangling branches*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Worktree pruning logic in `src/spec_ops/backlog/rescue.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that `spec-ops rescue prune` never removes any directory containing uncommitted changes or marked with active human IC claims.
- **Mutmut Mutation Scope**: Worktree inspection, dirty detection, and deletion safety filters in `src/spec_ops/backlog/rescue.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops rescue prune` identifies and removes worktrees associated with completed tasks, deleting merged branches and executing `git worktree prune`.
2. Executing `spec-ops rescue prune` skips dirty worktrees with active human modifications and prints protective warnings.
3. Executing `spec-ops rescue prune --dry-run` displays candidate worktrees and estimated reclaimable space without modifying the filesystem.
4. All scenarios verified via public frontdoors using `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
