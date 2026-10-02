---
id: TASK-0181
title: Fix Lockfile Sentinel Global Waiver Leak When Outside Dedicated Task Branch
status: Refined
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0004
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: security
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
---

## Summary
In `src/spec_ops/security/lockfile_sentinel.py`, `_check_task_waiver` attempts to inspect backlog task frontmatter to check for `allows_dependencies: true` or `allows_lockfile_mutation: true`.

However, if the worktree directory name does not match `task-(\d+)` (for example, on `main` or in root checkouts), `task_num` is `None`. The loop over `candidate_files.extend(backlog_dir.glob("*/*.md"))` then iterates over all tasks across the entire backlog, and if *any* historical or proposed task anywhere has `allows_dependencies: true`, it returns `True`, globally waiving lockfile mutations across the entire repository.

## Requirements
1. In `_check_task_waiver`, only check the active task matching the current git branch name or worktree path.
2. If neither the git branch nor directory indicates an active task, do not match arbitrary backlog task files.

## Acceptance Criteria

```gherkin
Scenario: Verify Fix Lockfile Sentinel Global Waiver Leak When Outside Dedicated Task Branch
  Given the system is initialized and ready
  When the user executes the workflow for "Fix Lockfile Sentinel Global Waiver Leak When Outside Dedicated Task Branch"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/security/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `security` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
