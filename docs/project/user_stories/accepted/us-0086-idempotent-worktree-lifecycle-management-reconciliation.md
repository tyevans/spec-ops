---
id: '0086'
title: Idempotent Worktree Lifecycle Management and Stale Worktree Reconciliation
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-WORK-07
governing_prd: PRD-0004
---

# US-0086 — Idempotent Worktree Lifecycle Management and Stale Worktree Reconciliation

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** agentic systems architect,
  - **I want** the worker engine to manage the full lifecycle of git worktrees idempotently and automatically reconcile stale or orphaned worktree directories,
  - **So that** repeated worker runs, unexpected crashes, or branch collisions never result in git locking errors or orphaned worktree directories consuming disk space.

## Acceptance Criteria

```gherkin
Scenario: Idempotent Worktree Creation with Branch Collision Recovery
Given an orphaned worktree directory ".worktrees/task-0009" left from an aborted process
And a stale local git branch "feat/task-0009" already exists
When the worker engine prepares to execute "TASK-0009"
Then the engine inspects the existing worktree for uncommitted human rescue work
And if uncommitted changes do not exist, prunes stale git worktree administrative metadata via "git worktree prune"
And resets the branch to "main" before mounting the fresh worktree
And creates the worktree cleanly without throwing git branch conflict errors.
```
```gherkin
Scenario: Atomic Teardown and Resource Cleanup upon Task Finalization
Given an active worktree at ".worktrees/task-0016" with passing preflight
When the task is successfully squash-merged into "main"
Then the worker engine removes the worktree via "git worktree remove --force"
And deletes the transient branch "feat/task-0016"
And deletes temporary prompt files and ephemeral worktree caches
And verifies that ".worktrees/task-0016" no longer exists on disk.
-
```

## Rationale & Compelling Value
- *Adoption*: Solves the #1 operational frustration in git-worktree-based developer workflows (dangling lockfiles and existing branch collisions).
  - *Regular Usage*: Ensures unattended workers running 24/7 never wedge the local repository into an unrecoverable state.
  - *Compelling Value*: Guarantees rock-solid filesystem hygiene and seamless recovery from unexpected system reboots or killed processes.

---
