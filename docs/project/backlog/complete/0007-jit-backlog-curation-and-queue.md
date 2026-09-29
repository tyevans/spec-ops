---
id: '0007'
title: JIT Backlog Curation and State Transition Queue
status: Complete
created: 2026-09-29
dependencies:
  - TASK-0004
  - TASK-0005
governing_adrs:
  - ADR-0001
  - ADR-0005
governing_prds:
  - PRD-0001
governing_stories:
  - US-0004
target_bc: backlog
---

# TASK-0007: JIT Backlog Curation and State Transition Queue

## Summary
Implement `BacklogQueue` and `spec-ops curate` to manage atomic task transitions (`proposed` -> `refined` -> `complete`), dependency unblocking, and automatic buffer replenishment.

## Definition of Done
1. `BacklogQueue` parses all task directories and PRIORITY.md rankings.
2. `get_ready_unblocked_tasks()` evaluates dependency graphs against completed task IDs.
3. `Curator` promotes unblocked proposed tasks to maintain the refined target buffer (~10 tasks).
4. `_sync_priority_file` atomically synchronizes `PRIORITY.md` on state transitions.
