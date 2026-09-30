---
id: '0050'
title: Concurrent Multi-Worker Batch Orchestration, Auto-Rebase under MERGE_LOCK, and Signal-Safe Cycle
status: Complete
created: 2026-09-29
dependencies:
  - TASK-0046
  - TASK-0049
governing_adrs:
  - ADR-0003
  - ADR-0004
  - ADR-0005
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0081
  - US-0085
  - US-0032
target_bc: worker
---

# TASK-0050: Concurrent Multi-Worker Batch Orchestration, Auto-Rebase under MERGE_LOCK, and Signal-Safe Cycle

## Summary
Implement the autonomous multi-worker batch orchestrator command (`spec-ops cycle [--max-workers N] [--max-tasks M]`) to execute concurrent worker processes across independent worktrees. Coordinate serialized squash-merges into `main` under `MERGE_LOCK` with automatic branch rebasing, handle rebase conflicts with worktree preservation, support dynamic downstream task unblocking within the same cycle, and ensure graceful signal interruption (SIGINT/Ctrl+C).

## Problem Statement & Context
Single-worker execution serializes backlog throughput, leaving parallel compute underutilized. However, running multiple autonomous workers concurrently without strict orchestration leads to git collisions, stale base commits, and shared backlog index conflicts. Furthermore, long-running batch cycles in CI cron jobs or overnight sprints need dynamic unblocking of downstream tasks and safe shutdown when interrupted so work is not corrupted mid-write.

## User Stories & Scenarios Satisfied
- **US-0081: Concurrent Multi-Worker Execution with Auto-Rebase under Merge Lock**
  - *Scenario: Serialized Squash-Merge with Auto-Rebase on Stale Task Branch*
  - *Scenario: Preserving Rescuable Worktree upon Rebase Merge Conflict*
- **US-0085: Autonomous Batch Cycle Orchestration with Dynamic Task Unblocking (spec-ops cycle)**
  - *Scenario: Dynamic Downstream Task Unblocking within a Single Cycle Run*
  - *Scenario: Graceful Cycle Interruption on SIGINT Signal*
- **US-0032: Structured Git Provenance Trailers and Atomic Integration under Merge Lock**
  - *Scenario: Creating Standardized Git Commit with Provenance Trailers*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Orchestration engine in `src/spec_ops/worker/orchestrator.py` and lock manager in `src/spec_ops/worker/merge_lock.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across simulated dependency DAGs and worker completion events verify that dynamic unblocking correctly identifies unblocked tasks in strict priority order without violating dependency constraints.
- **Mutmut Mutation Scope**: Batch cycle dispatch, rebase decision logic, and signal trap handlers in `src/spec_ops/worker/orchestrator.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops cycle --max-workers 3` runs parallel worker sessions in isolated worktrees (`.worktrees/<task-id>`) on dedicated task branches with zero dirty collisions.
2. When a worker completes, it acquires `MERGE_LOCK`, automatically rebases onto latest `main` if behind, runs preflight verification on the rebase, and squash-merges atomically.
3. If rebase encounters semantic conflicts, the worker aborts the rebase, releases `MERGE_LOCK`, marks the worktree as `Conflict`, and preserves it for `spec-ops rescue`.
4. When a task completes, downstream blocked tasks whose dependencies are satisfied are immediately pulled into active execution during the same cycle run.
5. Sending SIGINT (Ctrl+C) initiates graceful shutdown, allows in-flight steps to checkpoint safely, releases `MERGE_LOCK`, and emits a cycle status report.
6. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
