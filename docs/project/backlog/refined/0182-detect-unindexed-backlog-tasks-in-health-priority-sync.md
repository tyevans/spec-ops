---
id: TASK-0182
title: Detect Unindexed Backlog Tasks in Health Priority Sync
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
target_bc: backlog
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
---

## Summary
In `src/spec_ops/backlog/health.py`, `HealthChecker.check_priority_sync()` iterates through all `.md` files in `complete/`, `refined/`, and `proposed/` and regex-matches their status against `docs/project/backlog/PRIORITY.md`.

However, if a task file exists on disk but is completely absent from `PRIORITY.md` (`match is None`), `check_priority_sync()` ignores the omission instead of registering a synchronization error. This causes `spec-ops health` to falsely report that `PRIORITY.md is synchronized with disk state` even when multiple tasks are omitted from the priority queue.

## Requirements
1. In `HealthChecker.check_priority_sync()`, record an error when a task file on disk does not appear in `PRIORITY.md` (unindexed task).
2. Ensure `spec-ops health` reports a failure when any task file in `complete/`, `refined/`, or `proposed/` is missing from `PRIORITY.md`.
3. Add unit and property tests verifying detection of unindexed backlog task files.

## Acceptance Criteria

```gherkin
Scenario: Verify Detect Unindexed Backlog Tasks in Health Priority Sync
  Given the system is initialized and ready
  When the user executes the workflow for "Detect Unindexed Backlog Tasks in Health Priority Sync"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/backlog/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `backlog` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
