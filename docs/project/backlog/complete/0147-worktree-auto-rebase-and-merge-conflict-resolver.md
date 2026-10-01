---
id: '0147'
title: Autonomous Worktree Auto-Rebase and Optimistic Merge Conflict Resolver
status: Complete
dependencies:
- TASK-0080
- TASK-0136
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
governing_prds:
- PRD-0004
governing_stories:
- US-0080
- US-0083
target_bc: worker
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0147: Autonomous Worktree Auto-Rebase and Optimistic Merge Conflict Resolver

## Summary
Implement the autonomous worktree auto-rebase and optimistic merge conflict resolver (`spec-ops worker rebase [task-id] [--abort-on-conflict]`). Governed by ADR-0005 and PRD-0004, this engine automatically rebases active worktree branches against the latest `main` commit before preflight verification and merge lock acquisition, resolving trivial non-overlapping textual conflicts and safely aborting on semantic merge conflicts.

## Problem Statement & Context
When parallel agents work concurrently in multiple worktrees, earlier completed tasks merge into `main`, causing the base commit of active worktrees to fall behind. When the worker finishes and attempts to integrate, git merge or rebase conflicts can occur. Without an automated rebase engine, workers fail at integration time, requiring human intervention.

## Key Requirements & Scope
1. **Auto-Rebase Engine (`src/spec_ops/worker/auto_rebase.py`)**:
   - Fetches the latest `main` branch tip and attempts an in-worktree `git rebase main`.
   - Detects whether the rebase applies cleanly without manual conflict resolution.
2. **Conflict Guardrails**:
   - If conflicts occur on non-overlapping lines, uses git merge strategies to auto-resolve where safe.
   - If semantic or unresolvable conflicts occur, safely aborts the rebase (`git rebase --abort`) and captures diagnostic conflict details into `HANDOVER.md`.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Auto-rebase module in `src/spec_ops/worker/auto_rebase.py` must stay strictly under 400 lines (ADR-0002).
- **Strict Backlog Isolation (ADR-0005)**: Rebase operations must never modify files under `docs/project/backlog/` on the feature branch.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/worker/auto_rebase.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Clean automated rebase onto latest main tip
```gherkin
Given an active worktree whose branch is 2 commits behind "main"
When the worker executes "spec-ops worker rebase TASK-0147"
Then the worktree branch is rebased cleanly onto "main"
And the worktree working directory remains clean
```

### Scenario 2: Safe conflict abort with diagnostic handover generation
```gherkin
Given an active worktree with conflicting changes against "main"
When the worker executes "spec-ops worker rebase TASK-0147"
Then the conflicting rebase is safely aborted
And a conflict diagnostic summary is generated in "HANDOVER.md"
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any git repository state, auto-rebase execution either results in a clean successful rebase or safely restores the pre-rebase branch state without detached heads or lingering lock files.
