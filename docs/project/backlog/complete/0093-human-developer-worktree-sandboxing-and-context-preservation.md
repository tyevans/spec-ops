---
id: '0093'
title: Zero-Toil Human Worktree Sandboxing for Focused Feature Development
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
- US-0038
target_bc: rescue
---

# TASK-0093: Zero-Toil Human Worktree Sandboxing for Focused Feature Development

## Summary
Provide zero-toil human development worktree sandboxing commands (`spec-ops worktree start <task-id>` and `spec-ops worktree finish`) to enable conflict-free branch isolation, automated UV workspace configuration, and atomic integration under MERGE_LOCK for human software engineers.

## Problem Statement & Context
Human developers working alongside autonomous agents need the same conflict-free branch isolation without manually running complex `git worktree` and `git checkout` commands. SpecOps requires dedicated developer commands to provision task worktrees, configure environment symlinks, run preflight, and safely integrate changes into `main`.

## User Stories & Scenarios Satisfied
- **US-0038: Zero-Toil Human Worktree Sandboxing for Focused Feature Development**
  - *Scenario: Spawning a clean human development worktree*
  - *Scenario: Preflight verification and completion from within the worktree*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Worktree management CLI handler in `src/spec_ops/cli/worktree_handler.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that spawned worktree paths and branch names are deterministic and idempotent across valid task identifiers.
- **Mutmut Mutation Scope**: Worktree provisioning and environment linking in `src/spec_ops/worker/worktree.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops worktree start TASK-XXXX` provisions `.worktrees/task-XXXX`, checks out a dedicated feature branch, and initializes environment configuration.
2. Executing `spec-ops worktree finish` from within the worktree runs preflight, integrates under MERGE_LOCK, advances the task to complete, and cleans up the worktree.
3. All scenarios verified via public frontdoors using `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
