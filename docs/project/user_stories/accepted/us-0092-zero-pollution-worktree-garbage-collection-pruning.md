---
id: '0092'
title: Zero-Pollution Worktree Garbage Collection and Orphan Pruning
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RESC-06
governing_prd: PRD-0004
---

# US-0092 — Zero-Pollution Worktree Garbage Collection and Orphan Pruning

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer working in a high-velocity hybrid repository,
  - **I want** to execute `spec-ops rescue prune` to detect and safely clean up orphaned git worktrees, dangling agent branches, and completed task leftovers,
  - **So that** I keep my local filesystem pristine, prevent disk bloat, and eliminate git branch collision without accidentally destroying active human salvage work.

## Acceptance Criteria

```gherkin
Scenario: Detecting and safely pruning worktrees of completed tasks
Given worktree directory ".worktrees/task-0005" exists on disk
And task "TASK-0005" is already marked "complete" in "docs/project/backlog/complete/"
When the engineer executes "spec-ops rescue prune"
Then the CLI identifies ".worktrees/task-0005" as an orphaned completed worktree
And safely runs "git worktree remove --force .worktrees/task-0005"
And deletes the merged local branch "feat/TASK-0005"
And executes "git worktree prune".
```
```gherkin
Scenario: Guarding active and dirty human rescue worktrees from accidental deletion
Given worktree directory ".worktrees/task-0016" has uncommitted local changes authored by the engineer
And task "TASK-0016" remains in "docs/project/backlog/refined/"
When the engineer executes "spec-ops rescue prune"
Then the CLI skips ".worktrees/task-0016"
And displays a protection warning:
"Skipping .worktrees/task-0016: Worktree is dirty with active human modifications. Run 'spec-ops rescue reset TASK-0016' to force discard."
```
```gherkin
Scenario: Dry-run preview of reclaimable disk space and dangling branches
Given 4 stale worktrees totaling 1.2 GB of disk space
When the engineer executes "spec-ops rescue prune --dry-run"
Then no filesystem modifications are made
And the CLI prints a table of candidates for pruning, their branch names, and estimated reclaimable space.
-
```

## Rationale & Compelling Value
- **Adoption**: Solves the common pain point where multiple agent runs clutter `.worktrees/` and confuse git branch tracking.
  - **Regular Usage**: Run weekly or after intensive multi-agent development bursts to restore repository hygiene.
  - **Compelling Value**: Reclaims gigabytes of disk space from duplicate `.venv` and virtual environments while preventing catastrophic git worktree locking conflicts.

---
