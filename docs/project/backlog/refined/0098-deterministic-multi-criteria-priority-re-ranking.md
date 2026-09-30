---
id: 0098
title: Deterministic Multi-Criteria Priority Re-Ranking and Topological Backlog Ordering
status: Refined
dependencies:
- TASK-0065
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0005
- ADR-0007
governing_prds:
- PRD-0005
governing_stories:
- US-0074
target_bc: backlog
---

# TASK-0098: Deterministic Multi-Criteria Priority Re-Ranking and Topological Backlog Ordering

## Summary
Implement deterministic topological backlog re-ordering (`spec-ops queue reorder`) using multi-criteria weighted scoring (milestone delivery horizon, downstream blocker count, and architectural risk) that automatically resolves priority inversions while preserving architect manual pin overrides.

## Problem Statement & Context
As new tasks and dependencies are added to `PRIORITY.md`, priority inversions naturally occur where high-priority tasks depend on tasks lower in the queue. Human architects cannot manually re-sort dozens of tasks across multiple dependency graphs without introducing cycles or violating topological invariants. SpecOps requires automated multi-criteria topological sorting that guarantees prerequisites always precede dependents while respecting manual pin overrides.

## User Stories & Scenarios Satisfied
- **US-0074: Deterministic Multi-Criteria Priority Re-Ranking and Topological Backlog Ordering**
  - *Scenario: Topological Re-ordering to Resolve Priority Inversion*
    - Given a backlog where a high-priority task depends on a lower-ranked prerequisite
    - When "spec-ops queue reorder" runs
    - Then the prerequisite is moved ahead of the dependent task in PRIORITY.md.
  - *Scenario: Multi-Criteria Weighted Priority Scoring (Milestone, Blocker Count, Impact)*
    - Given multiple unblocked candidate tasks
    - When reordering is evaluated
    - Then tasks unlocking the highest number of downstream blocked tasks are ranked highest.
  - *Scenario: Respecting Architect Pin Overrides during Reordering*
    - Given a task marked with `pinned: true` in frontmatter
    - When reorder runs
    - Then the pinned task's explicit position is preserved while topologically valid.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Priority re-ranker in `src/spec_ops/backlog/reranker.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated task DAGs assert that topological re-ranking never introduces priority inversion and produces identical ordering on repeated runs.
- **Mutmut Mutation Scope**: Weighted scoring calculation in `src/spec_ops/backlog/reranker.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue reorder` detects priority inversions and updates `PRIORITY.md` topologically.
2. Multi-criteria scoring weights downstream blockers, milestone targets, and risk scores deterministically.
3. Tasks with `pinned: true` retain their relative rankings.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
