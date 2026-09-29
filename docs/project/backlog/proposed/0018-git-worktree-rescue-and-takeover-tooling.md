---
id: '0018'
title: Git Worktree Rescue and Human Takeover Tooling
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0011
governing_adrs:
  - ADR-0004
  - ADR-0005
governing_prds:
  - PRD-0001
governing_stories:
  - US-0005
target_bc: backlog
---

# TASK-0018: Git Worktree Rescue and Human Takeover Tooling

## Summary
Implement worktree preservation and human takeover capabilities in `spec-ops worker` and add a new CLI command `spec-ops rescue` to empower human developers (Riley) to inspect and recover failed or stalled autonomous tasks.

## Problem Statement
Currently, when an autonomous agent exhausts its self-healing retries, `BacklogWorkerEngine` forcefully tears down and prunes the worktree in its `finally` block, destroying diagnostic context and uncommitted or unmerged progress. Human developers have no ergonomic CLI interface to inspect active worktrees or resume a failed task stream.

## Detailed Objectives
1. **Worktree Preservation on Failure**:
   - When agent attempts fail or preflight errors exhaust retries, do NOT delete the worktree or branch.
   - Leave `.worktrees/task-<id>/` intact and output an actionable failure diagnostic pointing to `.task-prompt.md`.
2. **`spec-ops rescue` CLI Command**:
   - Provide `spec-ops rescue <task-id>`:
     - Checks if `.worktrees/task-<id>` exists.
     - Displays latest failure logs, test error traces, and git status.
     - Optionally opens the directory in the developer's configured IDE (`$EDITOR` or `--open`).
     - Offers flags `--retry` to re-run preflight and `--complete` to squash-merge and finish the task.
3. **Safe Worktree Audit & Cleanup**:
   - Provide `spec-ops worktree list` and `spec-ops worktree clean` to safely prune merged or obsolete worktrees without terminating active processes.

## Definition of Done (Blackbox Frontdoor TDD)
1. Automated blackbox tests verifying `spec-ops worker` preserves `.worktrees/task-XXXX` on execution failure.
2. `spec-ops rescue` command verified through CLI tests.
3. Invariant check verifies all new source files remain strictly under 500 lines.
