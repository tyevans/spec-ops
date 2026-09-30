---
id: '0116'
title: Fix Git Worktree Merge Lock Resolution and FileExistsError
status: Proposed
dependencies:
  - TASK-0109
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0005
governing_prds:
  - PRD-0004
  - PRD-0006
governing_stories:
  - US-0117
target_bc: worker
---

# TASK-0116: Fix Git Worktree Merge Lock Resolution and FileExistsError

## Summary
Fix `MergeLockManager` in `src/spec_ops/worker/merge_lock.py` to properly resolve the git directory when running inside an isolated git worktree where `.git` is a pointer file rather than a directory. Prevent `FileExistsError: [Errno 17] File exists: .../.git` during `spec-ops queue complete` and autonomous worktree integration.

## Problem Statement & Context
During dogfooding of the inline SDLC orchestrator on this repository, executing `spec-ops queue complete TASK-0109` raised `FileExistsError` at `self.lock_file.parent.mkdir(parents=True, exist_ok=True)`. In git worktrees created via `git worktree add`, `.git` is a file containing `gitdir: <path>` rather than a directory. Attempting to create `.git` as a directory causes an immediate crash, stalling automated task completion. Per the SpecOps SDLC Orchestration Failure Protocol in `AGENTS.md`, this orchestration failure was documented as an actionable bug and remediated.

## User Stories & Scenarios Satisfied
- **US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination**
  - *Scenario: Actionable Orchestration Failure Protocol*
    - Given an orchestrator executing lifecycle tasks on the SpecOps repository
    - When an orchestration failure occurs during subagent coordination
    - Then the failure is captured as an actionable high-priority bug in the backlog
    - And the orchestrator dispatches remediation to prevent future stalls.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: `src/spec_ops/worker/merge_lock.py` remains under 150 lines (ADR-0002).
- **Worktree Concurrency (ADR-0005)**: Ensures locking works uniformly in parent repos and child worktrees without corrupting git state.

## Definition of Done (Blackbox Frontdoor TDD)
1. `MergeLockManager` dynamically resolves git directory from `.git` file pointer when in a worktree.
2. `spec-ops queue complete` operates cleanly inside git worktrees without `FileExistsError`.
3. Tested via unit tests with mock worktree `.git` file pointers.
