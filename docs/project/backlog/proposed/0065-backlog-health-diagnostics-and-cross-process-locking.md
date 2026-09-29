---
id: '0065'
title: Proactive Backlog Health Diagnostics, Dangling Dependency Repair, and Cross-Process Locking
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0064
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0005
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0005
governing_stories:
  - US-0075
  - US-0076
target_bc: backlog
---

# TASK-0065: Proactive Backlog Health Diagnostics, Dangling Dependency Repair, and Cross-Process Locking

## Summary
Implement proactive backlog health diagnostics and multi-process concurrency safety: deliver a backlog doctor tool (`spec-ops queue doctor [--fix]`) that detects broken dependency references, ghost index entries, and unindexed task files with automated self-healing repair; and implement transactional cross-process file locking (`fcntl.flock` on `.specops/locks/queue.lock`) with two-phase atomic file writes, crash rollback, and stale lock auto-recovery (PID liveness checks) to protect queue operations during parallel multi-agent worker claiming.

## Problem Statement & Context
When multiple autonomous workers execute in parallel across isolated worktrees, concurrent claims (`spec-ops queue claim`) or completions (`spec-ops queue complete`) can cause race conditions on `PRIORITY.md` and task frontmatter files. Unprotected concurrent writes risk dirty index states, corrupted files, and double-assigned tasks. Furthermore, deleted or renamed task files often leave dangling dependency pointers in other tasks, causing silent build failures. SpecOps requires a cross-process concurrency lock and a self-healing backlog diagnostic doctor.

## User Stories & Scenarios Satisfied
- **US-0075: Proactive Backlog Health Diagnostics, Dangling Dependency Auditing, and Self-Healing Repair**
  - *Scenario: Detecting Broken and Dangling Dependency Pointers*
  - *Scenario: Detecting Ghost Entries and Unindexed Files in PRIORITY.md*
  - *Scenario: Automated Self-Healing Repair*
- **US-0076: Cross-Process File Locking and Transactional Concurrency Protection for Parallel Workers**
  - *Scenario: Mutual Exclusion During Concurrent Task Claiming*
  - *Scenario: Two-Phase Atomic Write and Rollback on Interrupted Index Updates*
  - *Scenario: Stale Lock Auto-Recovery on Worker Process Crash*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Backlog doctor in `src/spec_ops/backlog/doctor.py` and transactional lock manager in `src/spec_ops/backlog/lock.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across concurrent simulated worker threads and processes assert that exactly one worker acquires a contested task claim, zero deadlocks occur under timeout backoff, and corrupted index states automatically trigger transaction rollbacks.
- **Mutmut Mutation Scope**: Lock acquisition and stale-process detection in `src/spec_ops/backlog/lock.py` and dependency repair logic in `src/spec_ops/backlog/doctor.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue doctor` audits all tasks and `PRIORITY.md`, reporting any dangling dependencies to non-existent tasks, unindexed task files on disk, or ghost entries in `PRIORITY.md`.
2. Executing `spec-ops queue doctor --fix` repairs missing `PRIORITY.md` references, cleans up ghost entries, and updates broken dependency pointers atomically.
3. Concurrent invocation of `spec-ops queue claim` across 4 simultaneous processes executes with mutual exclusion; one process claims the top ready task while others receive the subsequent tasks without race conditions.
4. Process termination during two-phase index writes leaves zero partial writes or corrupted files, restoring the previous index state on next invocation.
5. Crashed worker processes holding a lock file are detected via dead PID inspection, and the stale lock is reclaimed after a configurable timeout without manual intervention.
6. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
