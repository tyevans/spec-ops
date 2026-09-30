---
id: '0102'
title: Cross-Process File Locking and Transactional Concurrency Protection for Parallel Workers
status: Proposed
created: 2026-09-30
dependencies:
  - TASK-0065
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0005
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0005
governing_stories:
  - US-0076
target_bc: backlog
---

# TASK-0102: Cross-Process File Locking and Transactional Concurrency Protection for Parallel Workers

## Summary
Implement robust cross-process file locking and transactional concurrency protection for multi-worker queues: deliver OS-level advisory file locks (`fcntl.flock` on `.specops/locks/queue.lock`) with two-phase atomic file writes, crash rollback, and stale lock auto-recovery (PID liveness checks) to protect queue operations during parallel multi-agent worker claiming and completion.

## Problem Statement & Context
When multiple autonomous workers execute simultaneously across isolated worktrees, concurrent claims (`spec-ops queue claim`) or completions (`spec-ops queue complete`) can cause race conditions on `PRIORITY.md` and task frontmatter files. Unprotected concurrent writes risk dirty index states, corrupted files, and double-assigned tasks. SpecOps requires a cross-process concurrency lock with automated crash recovery.

## User Stories & Scenarios Satisfied
- **US-0076: Cross-Process File Locking and Transactional Concurrency Protection for Parallel Workers**
  - *Scenario: Mutual Exclusion During Concurrent Task Claiming*
    - Given 4 concurrent worker processes running `spec-ops queue claim` simultaneously
    - When processes contend for the queue lock
    - Then operations execute with mutual exclusion without race conditions or duplicate task assignments.
  - *Scenario: Two-Phase Atomic Write and Rollback on Interrupted Index Updates*
    - Given a worker process interrupted midway through writing `PRIORITY.md`
    - When the write aborts
    - Then backup state is restored and no corrupt or truncated index files remain on disk.
  - *Scenario: Stale Lock Auto-Recovery on Worker Process Crash*
    - Given a crashed worker process that abruptly terminated holding `.specops/locks/queue.lock`
    - When another worker attempts to claim a task
    - Then dead PID inspection detects the stale lock and reclaims it safely without manual intervention.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Transactional lock manager in `src/spec_ops/backlog/lock.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across concurrent simulated worker threads assert that exactly one worker acquires a contested claim, zero deadlocks occur under timeout backoff, and corrupted index states automatically trigger transaction rollbacks.
- **Mutmut Mutation Scope**: Lock acquisition and stale-process detection in `src/spec_ops/backlog/lock.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Concurrent invocation of `spec-ops queue claim` across 4 simultaneous processes executes with mutual exclusion; one process claims the top ready task while others receive subsequent tasks without race conditions.
2. Process termination during two-phase index writes leaves zero partial writes or corrupted files, restoring the previous index state on next invocation.
3. Crashed worker processes holding a lock file are detected via dead PID inspection, and the stale lock is reclaimed after a configurable timeout without manual intervention.
4. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
