---
id: '0011'
title: Autonomous Git Worktree Worker Execution Engine
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0007
governing_adrs:
  - ADR-0004
  - ADR-0005
governing_prds:
  - PRD-0001
governing_stories:
  - US-0005
target_bc: backlog
---

# TASK-0011: Autonomous Git Worktree Worker Execution Engine

## Summary
Complete the autonomous worker execution engine in `spec-ops worker` to manage git worktree lifecycles, branch creation, preflight test execution, and safe pull request branch pushing.

## Definition of Done
1. Worker creates isolated git worktrees at `.worktrees/<task-id>` on branch `task/<task-id>`.
2. Worker executes configured agent command or shell command within the worktree context.
3. Automated preflight runs (`spec-ops health` + `pytest`); on failure, triggers self-healing retry loop.
4. On success, worker pushes branch to remote and cleans up worktree without polluting `main`.
