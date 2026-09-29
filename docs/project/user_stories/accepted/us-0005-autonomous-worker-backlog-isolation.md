---
id: '0005'
title: Autonomous Worker Execution with Git Worktree Backlog Isolation
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-WRK-01
governing_prd: PRD-0001
---

# US-0005 — Autonomous Worker Execution with Git Worktree Backlog Isolation

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** to execute tasks via `spec-ops worker` inside isolated git worktrees,  
**So that** my code modifications and preflight verification loops never cause git merge conflicts or corrupt shared backlog indices.

## Acceptance Criteria

### Scenario 1: Isolated Worktree Task Execution
```gherkin
Given a refined task "TASK-0009" in "docs/project/backlog/refined/"
When the worker runs "spec-ops worker --task TASK-0009 --worktree"
Then an isolated worktree is spawned on a new git branch "task/TASK-0009"
And the worker executes in isolation without touching main branch working directories
And preflight checks run cleanly before pull request creation.
```
