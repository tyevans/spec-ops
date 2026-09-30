---
id: '0065'
title: Automated Reactive Unblocking Cascade and JIT Buffer Replenishment
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0064
  - TASK-0007
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0005
  - ADR-0006
  - ADR-0007
governing_prds:
  - PRD-0005
governing_stories:
  - US-0073
target_bc: backlog
---

# TASK-0065: Automated Reactive Unblocking Cascade and JIT Buffer Replenishment

## Summary
Implement automated reactive unblocking cascades upon task completion (`spec-ops queue complete <task-id>`) that detect newly unblocked downstream tasks, promote eligible tasks to `refined/` while strictly respecting the lean ready buffer ceiling (~10 tasks), and emit unblocking telemetry events for autonomous agent dispatchers.

## Problem Statement & Context
When a prerequisite task is integrated into `main`, dependent tasks in `proposed/` remain locked unless manually discovered and promoted. This latency starves autonomous worker streams and requires constant manual intervention. SpecOps requires automated cascading unblocking that instantly transitions newly unblocked work into the ready queue up to the buffer limit.

## User Stories & Scenarios Satisfied
- **US-0073: Automated Reactive Unblocking and Cascading Buffer Replenishment upon Task Completion**
  - *Scenario: Reactive Promotion of Newly Unblocked Downstream Task upon Prerequisite Merge*
    - Given task "TASK-A" in "refined/" is completed
    - When "spec-ops queue complete TASK-A" runs
    - Then dependent task "TASK-B" whose only dependency was TASK-A is reactively promoted to "refined/".
  - *Scenario: Maintaining Ready Buffer Ceiling During Cascading Unblocking*
    - Given the refined buffer is at target capacity (10 tasks)
    - When a task completes and unblocks 3 proposed tasks
    - Then only 1 task is promoted to replenish the consumed slot and excess tasks remain proposed.
  - *Scenario: Emitting Unblocking Telemetry Event for Autonomous Agent Dispatchers*
    - Given an unblocking cascade triggers
    - When promotion occurs
    - Then a structured telemetry event `{"event": "task_unblocked", "task_id": "TASK-B"}` is emitted to stdout.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Unblocking cascade engine in `src/spec_ops/backlog/unblocker.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that cascading unblocking never causes the refined buffer count to exceed the configured buffer target.
- **Mutmut Mutation Scope**: Cascade replenishment logic in `src/spec_ops/backlog/unblocker.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue complete <task-id>` marks the task complete, updates `PRIORITY.md`, checks downstream dependents, and reactively promotes unblocked tasks into `refined/`.
2. Cascading promotions strictly respect the configured ready buffer target.
3. Structured unblocking events are emitted to stdout and logged to `.specops/events.log`.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
