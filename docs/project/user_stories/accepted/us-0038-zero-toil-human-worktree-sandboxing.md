---
id: '0038'
title: Zero-Toil Human Worktree Sandboxing for Focused Feature Development
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-SND-01
governing_prd: PRD-0004
---

# US-0038 — Zero-Toil Human Worktree Sandboxing for Focused Feature Development

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** human software engineer picking up an assigned backlog task,  
**I want** to execute `spec-ops worktree start <task-id>` to scaffold an isolated git worktree with branch tracking and UV workspace synchronization,  
**So that** I enjoy the same conflict-free branch isolation as autonomous agents without manual `git worktree` plumbing or local branch collision.

## Acceptance Criteria

```gherkin
Scenario: Spawning a clean human development worktree
Given a refined task "TASK-0021" in "docs/project/backlog/refined/"
When the engineer executes "spec-ops worktree start TASK-0021"
Then a new git worktree is created at ".worktrees/task-0021"
And a dedicated branch "feat/TASK-0021" is checked out
And local workspace environment symlinks and configs are initialized in the worktree
And the command outputs the command to enter the workspace: "cd .worktrees/task-0021".
```

```gherkin
Scenario: Preflight verification and completion from within the worktree
Given the engineer is inside ".worktrees/task-0021" and has implemented the task
When the engineer executes "spec-ops worktree finish"
Then local preflight verification runs across tests, invariants, and linting
And upon preflight success, changes are pushed or squash-merged into "main" under MERGE_LOCK
And task "TASK-0021" is advanced to "complete/"
And the working directory is safely returned to the repository root.
```

## Rationale & Compelling Value
Treats human developers as first-class citizens alongside agents. Zero toil in managing worktrees, zero branch pollution on `main`, and effortless multi-task context switching.
