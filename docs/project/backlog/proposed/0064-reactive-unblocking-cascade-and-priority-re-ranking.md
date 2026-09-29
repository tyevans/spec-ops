---
id: '0064'
title: Automated Reactive Unblocking Cascade, JIT Buffer Replenishment, and Deterministic Priority Re-Ranking
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0063
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
  - US-0074
  - US-0024
target_bc: backlog
---

# TASK-0064: Automated Reactive Unblocking Cascade, JIT Buffer Replenishment, and Deterministic Priority Re-Ranking

## Summary
Implement automated reactive backlog unblocking and deterministic multi-criteria priority re-ranking: trigger cascading unblocking upon task completion (`spec-ops queue complete <task-id>`) that automatically moves newly unblocked tasks from `proposed/` to `refined/` while respecting the JIT buffer ceiling (~10 tasks), emit structured unblocking telemetry events for agent dispatchers, implement deterministic topological backlog re-ordering (`spec-ops queue reorder`) using multi-criteria weighted scoring (milestone delivery horizon, downstream blocker count, and architectural risk) while preserving architect manual pin overrides, and enforce an automated Definition of Ready (DoR) gatekeeper (`spec-ops queue refine`) that blocks unrefined tasks lacking Gherkin acceptance criteria.

## Problem Statement & Context
When an autonomous worker or human developer completes a prerequisite task, downstream tasks in `proposed/` remain locked unless manually inspected and promoted. Manual promotion creates pipeline delays, leads to idle autonomous agents, and risks over-buffering beyond the JIT limit (~10 ready tasks), inviting specification rot. Furthermore, priority inversions occur when high-priority tasks depend on low-priority prerequisites. SpecOps requires automated reactive unblocking, deterministic topological re-ranking, and rigorous DoR validation.

## User Stories & Scenarios Satisfied
- **US-0073: Automated Reactive Unblocking and Cascading Buffer Replenishment upon Task Completion**
  - *Scenario: Reactive Promotion of Newly Unblocked Downstream Task upon Prerequisite Merge*
  - *Scenario: Maintaining Ready Buffer Ceiling During Cascading Unblocking*
  - *Scenario: Emitting Unblocking Telemetry Event for Autonomous Agent Dispatchers*
- **US-0074: Deterministic Multi-Criteria Priority Re-Ranking and Topological Backlog Ordering**
  - *Scenario: Topological Re-ordering to Resolve Priority Inversion*
  - *Scenario: Multi-Criteria Weighted Priority Scoring (Milestone, Blocker Count, Impact)*
  - *Scenario: Respecting Architect Pin Overrides during Reordering*
- **US-0024: Automated Definition of Ready Gatekeeper and Ticket Health Audit**
  - *Scenario: Promoting Only Fully Compliant Tasks to Refined Buffer*
  - *Scenario: Rejecting Half-Baked Proposed Tasks Lacking Gherkin Criteria*
  - *Scenario: Rejecting Tasks Violating Single-Responsibility Scope*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Unblocking engine in `src/spec_ops/backlog/unblocker.py`, priority re-ranker in `src/spec_ops/backlog/reranker.py`, and DoR evaluator in `src/spec_ops/backlog/dor_gate.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated task queues assert that topological re-ranking never introduces priority inversion (prerequisites always precede dependents in `PRIORITY.md`), and manual pin overrides are strictly preserved across re-ranking passes.
- **Mutmut Mutation Scope**: Cascading replenishment logic in `src/spec_ops/backlog/unblocker.py` and priority scoring weights in `src/spec_ops/backlog/reranker.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue complete TASK-XXXX` marks the task complete, updates `PRIORITY.md`, checks downstream dependents, and reactively promotes fully unblocked tasks meeting DoR into `refined/`.
2. Cascading promotions halt when the ready buffer ceiling (~10 tasks) is attained, leaving excess unblocked tasks in proposed status with ready indicators.
3. Structured unblocking events (`{"event": "task_unblocked", "task_id": "TASK-YYYY"}`) are emitted to stdout and logged to `.specops/events.log`.
4. Executing `spec-ops queue reorder` detects priority inversions and sorts `PRIORITY.md` topologically by weighted multi-criteria score while preserving tasks with `pinned: true` frontmatter.
5. Executing `spec-ops queue refine TASK-ZZZZ` checks DoR criteria (valid YAML frontmatter, cited PRD, persona, ADRs, executable Gherkin scenarios) and rejects non-compliant tasks with exit code 1.
6. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
