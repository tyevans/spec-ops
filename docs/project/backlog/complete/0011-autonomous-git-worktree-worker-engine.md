---
id: '0011'
title: Autonomous Git Worktree Worker Execution Engine
status: Complete
created: 2026-09-29
completed: 2026-09-29
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
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0011: Autonomous Git Worktree Worker Execution Engine

## Summary
Complete the autonomous worker execution engine in `spec-ops worker` to manage git worktree lifecycles, branch creation, preflight test execution, self-healing retries, and human takeover rescue.

## Definition of Done
1. Worker creates isolated git worktrees at `.worktrees/<task-id>` on branch `task/<task-id>` (or `feat/<task-id>`).
2. Worker executes configured agent command or shell command within the worktree context.
3. Automated preflight runs (`spec-ops health` + `pytest`); on failure, triggers self-healing retry loop.
4. On failure, preserves worktree context for human takeover (`spec-ops rescue`). On success, worker squash-merges branch and cleans up worktree without polluting `main`.

## Completion Summary
- Implemented isolated worktree lifecycle and automated self-healing feedback loop in [`src/spec_ops/backlog/worker.py`](../../../src/spec_ops/backlog/worker.py).
- Added worktree failure preservation: stalled worktrees are kept intact for human inspection rather than being destroyed.
- Implemented [`WorktreeRescueManager`](../../../src/spec_ops/backlog/rescue.py) and `spec-ops rescue` CLI command (`--list`, `--complete`, `--discard`) empowering Riley to recover failed tasks.
- Added comprehensive unit and CLI blackbox tests in [`tests/test_rescue.py`](../../../tests/test_rescue.py) and [`tests/test_cli.py`](../../../tests/test_cli.py).
- All source files conform to Hard Invariant 6 (<500 lines).
