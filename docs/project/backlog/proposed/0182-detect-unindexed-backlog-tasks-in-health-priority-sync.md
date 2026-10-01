---
id: TASK-0182
title: Detect Unindexed Backlog Tasks in Health Priority Sync
status: Proposed
target_bc: backlog
dependencies: []
---

## Summary
In `src/spec_ops/backlog/health.py`, `HealthChecker.check_priority_sync()` iterates through all `.md` files in `complete/`, `refined/`, and `proposed/` and regex-matches their status against `docs/project/backlog/PRIORITY.md`.

However, if a task file exists on disk but is completely absent from `PRIORITY.md` (`match is None`), `check_priority_sync()` ignores the omission instead of registering a synchronization error. This causes `spec-ops health` to falsely report that `PRIORITY.md is synchronized with disk state` even when multiple tasks are omitted from the priority queue.

## Requirements
1. In `HealthChecker.check_priority_sync()`, record an error when a task file on disk does not appear in `PRIORITY.md` (unindexed task).
2. Ensure `spec-ops health` reports a failure when any task file in `complete/`, `refined/`, or `proposed/` is missing from `PRIORITY.md`.
3. Add unit and property tests verifying detection of unindexed backlog task files.
