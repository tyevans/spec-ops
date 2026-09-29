---
id: '0049'
title: 'Architectural Spike: Multi-Process Transactional File Locking (MERGE_LOCK) and Auto-Rebase Synchronization'
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0048
governing_adrs:
  - ADR-0003
  - ADR-0005
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0081
  - US-0032
target_bc: worker
---

# TASK-0049: Architectural Spike: Multi-Process Transactional File Locking (MERGE_LOCK) and Auto-Rebase Synchronization

## Summary
Conduct an architectural spike to evaluate, benchmark, and validate multi-process synchronization strategies (`fcntl.flock`, lockfiles, exponential backoff, dead-process PID stale lock reclamation) for concurrent worker processes acquiring `MERGE_LOCK`. Prototype and benchmark auto-rebasing of stale task branches onto `main` under high contention, verify signal trapping (SIGINT/SIGTERM) to eliminate dangling locks, and graduate findings into ADR-0010: Multi-Process Transactional Concurrency and Auto-Rebase.

## Problem Statement & Context
When multiple autonomous coding agents work concurrently in isolated worktrees, they branch from common commits. If one worker merges into `main`, other in-flight worker branches become stale. Naive merge attempts result in git index lock errors, dirty working trees, or merge races that corrupt `main`. SpecOps requires a transactional multi-process concurrency lock (`MERGE_LOCK`) combined with an automated rebase-and-preflight pipeline to guarantee clean linear integration without deadlocks or manual git intervention.

## User Stories & Scenarios Satisfied
- **US-0081: Concurrent Multi-Worker Execution with Auto-Rebase under Merge Lock**
  - *Scenario: Serialized Squash-Merge with Auto-Rebase on Stale Task Branch*
  - *Scenario: Preserving Rescuable Worktree upon Rebase Merge Conflict*
- **US-0032: Structured Git Provenance Trailers and Atomic Integration under Merge Lock**
  - *Scenario: Creating Standardized Git Commit with Provenance Trailers*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Spike prototype and benchmark harness in `src/spec_ops/worker/concurrency_spike.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across simulated multi-process worker pools (2–8 concurrent processes) assert that `MERGE_LOCK` guarantees strict mutual exclusion: no two processes hold the lock concurrently, and all locks are released cleanly even under injected process terminations.
- **Mutmut Mutation Scope**: Core lock acquisition, timeout handling, and PID staleness checking in `src/spec_ops/worker/concurrency_spike.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Spike benchmarks multi-process file locking across 4 concurrent simulated workers, proving zero lock contention race conditions or deadlocks over 100 iterations.
2. Prototype verifies automated rebase onto `main` under lock: detects stale base commit, rebases cleanly, and executes preflight before committing.
3. Prototype traps SIGINT and SIGTERM signals, ensuring active locks are released and zero orphaned `.lock` files remain on disk.
4. Semantic rebase merge conflicts are caught cleanly, aborting the rebase, releasing `MERGE_LOCK`, and marking the worktree as `Conflict` for human rescue.
5. Findings, benchmarks, and production recommendations are published into `docs/project/adrs/proposed/adr-0010-multi-process-transactional-concurrency-and-auto-rebase.md`.
