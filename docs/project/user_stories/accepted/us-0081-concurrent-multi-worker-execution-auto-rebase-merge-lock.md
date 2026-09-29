---
id: '0081'
title: Concurrent Multi-Worker Execution with Auto-Rebase under Merge Lock
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-WORK-02
governing_prd: PRD-0004
---

# US-0081 — Concurrent Multi-Worker Execution with Auto-Rebase under Merge Lock

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** engineering lead,
  - **I want** SpecOps to support concurrent worker execution across multiple tasks while serializing integration through `MERGE_LOCK` with automated branch rebasing,
  - **So that** parallel agent streams can implement independent backlog items simultaneously without merge races or stale base commits corrupting the `main` branch.

## Acceptance Criteria

```gherkin
Scenario: Serialized Squash-Merge with Auto-Rebase on Stale Task Branch
Given two autonomous workers running concurrently on tasks "TASK-0011" and "TASK-0012" in separate worktrees
And worker "TASK-0011" acquires "MERGE_LOCK", squash-merges into "main", and completes
When worker "TASK-0012" finishes code modifications and acquires "MERGE_LOCK"
Then the worker engine detects that "TASK-0012" branched from a commit behind current "main"
And the engine automatically rebases the "feat/task-0012" branch onto the latest "main"
And runs the preflight verification suite on the rebased code
And upon passing preflight, squash-merges "feat/task-0012" into "main" and marks "TASK-0012" complete.
```
```gherkin
Scenario: Preserving Rescuable Worktree upon Rebase Merge Conflict
Given a concurrent worker executing "TASK-0015" in ".worktrees/task-0015"
When "TASK-0015" acquires "MERGE_LOCK" and attempts to rebase onto updated "main"
And git encounters an unresolvable semantic merge conflict
Then the worker engine aborts the rebase without corrupting "main"
And releases "MERGE_LOCK" so other workers remain unblocked
And preserves the worktree at ".worktrees/task-0015" with status "Conflict"
And logs an actionable human rescue notification "spec-ops rescue TASK-0015".
-
```

## Rationale & Compelling Value
- *Adoption*: Unlocks team transition from single-agent experimentation to multi-agent swarm execution.
  - *Regular Usage*: Powers parallel execution in `spec-ops cycle --concurrency 3`, tripling backlog throughput.
  - *Compelling Value*: Eliminates the infamous "agent merge collision" problem where concurrent workers squash over each other's changes, maintaining a strictly linear and green `main` branch.

---
