---
id: 0159
title: Automated Worktree Stash and Clean Reset Recovery Engine
status: Complete
dependencies:
- TASK-0054
- TASK-0104
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0020
governing_prds:
- PRD-0004
governing_stories:
- US-0081
target_bc: rescue
---

# TASK-0159: Automated Worktree Stash and Clean Reset Recovery Engine

## Summary
Implement an automated worktree stash and clean reset recovery engine (`src/spec_ops/rescue/stash_reset.py`). Governed by ADR-0005 and ADR-0020, this tool enables developers and autonomous agents to safely stash uncommitted worktree changes into timestamped git stashes or patch archives before executing deterministic clean resets of corrupted worktree state (`spec-ops rescue reset --stash`).

## Problem Statement & Context
During complex autonomous worker execution or manual developer debugging, worktrees can enter dirty or unrecoverable states due to compilation failures or merge conflicts. Forcing a hard reset risks losing valuable exploratory code. A safe reset engine archives current working diffs into an indexed rescue store before resetting the branch to a pristine state.

## Key Requirements & Scope
1. **Stash & Reset Engine (`src/spec_ops/rescue/stash_reset.py`)**:
   - Inspects target worktree git status and dirty working tree files.
   - Generates an indexed patch archive or git stash with metadata (task ID, branch, timestamp).
   - Performs a deterministic clean reset of the worktree to `HEAD` or tracking branch.
   - Restores tracked worktree state without polluting other parallel worktrees.
2. **Rescue Reset CLI (`spec-ops rescue reset [--task-id <ID>] [--stash] [--dry-run] [--force]`)**:
   - Executes safe reset workflow and outputs the rescue stash identifier for potential recovery.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate verifying public CLI interface and file restoration.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Rescue engine in `src/spec_ops/rescue/stash_reset.py` must stay strictly under 400 lines (ADR-0002).
- **Strict Backlog Isolation (ADR-0005)**: No modifications to shared backlog files during worktree resets.
- **Mutation Testing Scope**: Target module `src/spec_ops/rescue/stash_reset.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Safely stashing uncommitted changes and resetting worktree
```gherkin
Given a dirty worktree with uncommitted file modifications
When the developer runs spec-ops rescue reset with stash flag
Then the uncommitted modifications are archived to a rescue stash
And the worktree is cleanly reset to pristine HEAD state
And exits with code 0
```

### Scenario 2: Preserving stashed changes across resets
```gherkin
Given a previously created rescue stash for a worktree
When the developer inspects available rescue archives
Then the stash details, timestamp, and diff summary are visible
And can be selectively reapplied
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that stashing and resetting any arbitrary directory state produces a clean git working tree while preserving the exact diff in the archive.
