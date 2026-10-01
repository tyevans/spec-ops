---
id: 0138
title: Proactive Worktree Disk Quota Monitor and Orphan Pruning Daemon
status: Refined
dependencies:
- TASK-0018
- TASK-0092
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0092
target_bc: rescue
---

# TASK-0138: Proactive Worktree Disk Quota Monitor and Orphan Pruning Daemon

## Summary
Implement the proactive worktree disk quota monitor and orphan worktree pruning engine (`spec-ops rescue prune --older-than <duration> [--dry-run] [--force] [--json]` and `spec-ops rescue quota`). Monitor aggregate disk consumption across `.worktrees/`, trigger proactive warnings when worktree storage exceeds thresholds (e.g. >5GB), and provide automated, safe pruning of merged or abandoned worktree directories with zero data loss.

## Problem Statement & Context
As multi-agent coding sessions scale, isolated git worktrees accumulate build artifacts (`.venv`, `node_modules`, `dist/`), git objects, and unpruned branches. Abandoned or completed worktrees consume tens of gigabytes of disk space and clutter developer workspaces. SpecOps requires an automated, safe pruning daemon that audits worktree states, identifies merged branches, and reclaims disk space cleanly.

## Key Requirements & Scope
1. **Worktree Disk Quota Monitor (`spec-ops rescue quota`)**:
   - Computes disk consumption across all worktrees in `.worktrees/`.
   - Displays per-worktree size, associated task status (`complete/`, `refined/`, `proposed/`, or orphan), and last-modified timestamps.
   - Emits proactive warnings when aggregate worktree size exceeds configured thresholds.
2. **Safe Orphan Worktree Pruning (`spec-ops rescue prune`)**:
   - `spec-ops rescue prune --older-than 7d` identifies abandoned worktrees older than the specified duration.
   - Verifies that task changes have either been merged to `main` or recorded into failure memory (`failure_history`) before deleting directories.
   - Supports `--dry-run` to preview reclaimable disk space safely.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Pruning module in `src/spec_ops/rescue/prune_daemon.py` must stay strictly under 400 lines (ADR-0002).
- **Data Loss Prevention Invariant**: Never delete worktrees with uncommitted, unmerged changes without explicit `--force` confirmation.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/rescue/prune_daemon.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Auditing disk consumption and candidate orphan worktrees
```gherkin
Given multiple git worktrees in ".worktrees/" with merged and unmerged tasks
When the engineer runs "spec-ops rescue quota"
Then a tabular summary displays directory sizes and associated task statuses
And flags candidates eligible for safe pruning
```

### Scenario 2: Safely pruning merged worktrees with disk reclamation
```gherkin
Given an abandoned worktree whose task was completed and merged into "main"
When the engineer executes "spec-ops rescue prune --older-than 1d"
Then the worktree directory and branch are deleted safely
And zero active unmerged worktrees are affected
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any set of worktrees with mixed task completion states, pruning strictly targets completed or force-flagged directories and never deletes active in-progress worktrees.
