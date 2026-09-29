---
id: '0018'
title: Git Worktree Rescue and Human Takeover Tooling
status: Complete
created: 2026-09-29
completed: 2026-09-29
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

## Definition of Done (Blackbox Frontdoor TDD)
1. Automated blackbox tests verifying `spec-ops worker` preserves `.worktrees/task-XXXX` on execution failure.
2. `spec-ops rescue` command verified through CLI tests.
3. Invariant check verifies all new source files remain strictly under 500 lines.

## Completion Summary
- Updated [`src/spec_ops/backlog/worker.py`](../../../src/spec_ops/backlog/worker.py) to preserve `.worktrees/task-XXXX` and avoid branch deletion when execution fails.
- Created [`WorktreeRescueManager`](../../../src/spec_ops/backlog/rescue.py) with worktree inspection, recovery, preflight validation, and squash-merge completion under `MERGE_LOCK`.
- Added `spec-ops rescue` CLI command with `--list`, `--complete`, and `--discard` flags in [`src/spec_ops/cli/main.py`](../../../src/spec_ops/cli/main.py).
- Added comprehensive unit and blackbox CLI tests in [`tests/test_rescue.py`](../../../tests/test_rescue.py) and [`tests/test_cli.py`](../../../tests/test_cli.py).
- All source files conform to Hard Invariant 6 (<500 lines).
