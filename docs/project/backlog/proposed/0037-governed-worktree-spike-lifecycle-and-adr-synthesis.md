---
id: '0037'
title: Governed Worktree Spike Lifecycle and Empirical ADR Synthesis
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0002
  - TASK-0011
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0005
  - ADR-0007
  - ADR-0008
  - ADR-0009
governing_prds:
  - PRD-0003
governing_stories:
  - US-0097
  - US-0098
target_bc: prd
---

# TASK-0037: Governed Worktree Spike Lifecycle and Empirical ADR Synthesis

## Summary
Implement the governed architectural spike lifecycle via `spec-ops spike start SPIKE-XXXX` and `spec-ops spike graduate SPIKE-XXXX`. Instantiate disposable, sandboxed git worktrees under `.worktrees/spike-XXXX` on branch `spike/SPIKE-XXXX` with an isolated benchmark and test harness under `spikes/spike_XXXX/`. Enforce write isolation preventing spike code from polluting `src/spec_ops/`, enforce timebox checks, and upon graduation automatically synthesize an Architectural Decision Record under `docs/project/adrs/` embedding empirical benchmark findings, unblocking or blocking downstream dependent backlog tasks and cleaning up worktrees.

## Problem Statement & Context
When teams face high technical uncertainty (e.g. evaluating new database engines or network protocols), unproven architectural assumptions often rot in backlogs or lead to prototype code being carelessly merged into production trees. Autonomous coding agents working on exploratory tasks risk polluting `src/` with exploratory prototypes and violating codebase invariants. SpecOps needs a governed, disposable sandbox that operationalizes the scientific method: empirical hypothesis testing that automatically synthesizes immutable ADRs upon conclusion.

## User Stories & Scenarios Satisfied
- **US-0097: Disposable Worktree Sandboxing and Automated Spike Test Harness Scaffolding**
  - *Scenario: Scaffolding a sandboxed spike worktree and hypothesis test harness*
  - *Scenario: Enforcing write isolation to prevent spike code from modifying "src/"*
  - *Scenario: Enforcing spike timebox expiration*
- **US-0098: Empirical Spike Hypothesis Validation and Automated ADR Synthesis**
  - *Scenario: Successfully graduating a proven spike with empirical benchmark data into an ADR*
  - *Scenario: Documenting a disproven hypothesis with rationale and blocking dependent implementation slices*
  - *Scenario: Cleaning up disposable spike worktree upon graduation*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Spike management modules in `src/spec_ops/spike/sandbox.py` and `src/spec_ops/spike/graduate.py` remain strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary spike frontmatter (hypotheses, timeboxes, dependent tasks) assert that generated ADR files conform to ADR-0001 schema, and graduating a spike deterministically transitions dependent tasks to either unblocked or blocked without leaving orphan git references.
- **Mutmut Mutation Scope**: Core spike harness generation and ADR graduation logic in `src/spec_ops/spike/graduate.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops spike start SPIKE-XXXX` creates an isolated git worktree at `.worktrees/spike-XXXX` on branch `spike/SPIKE-XXXX` and scaffolds `spikes/spike_XXXX/harness.py`, `test_spike.py`, and `README.md`.
2. Inside the spike worktree, attempting to modify files within `src/` triggers a preflight rejection protecting production source code.
3. Executing `spec-ops spike check` warns when a spike exceeds its declared timebox.
4. Executing `spec-ops spike graduate SPIKE-XXXX --result proven --title <Title>` evaluates benchmark outputs, authors a new ADR under `docs/project/adrs/proposed/`, moves the spike task to `complete/` with status `Graduated`, unblocks dependent tasks, removes the worktree, and tags the git branch.
5. Executing graduation with `--result disproven` generates an architectural finding ADR and marks dependent tasks blocked.
6. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
