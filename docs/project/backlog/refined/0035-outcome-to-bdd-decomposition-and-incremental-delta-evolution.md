---
id: '0035'
title: Outcome-to-BDD Scenario Decomposition and Incremental Delta Scope Evolution
status: Refined
dependencies:
- TASK-0006
- TASK-0034
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0006
- ADR-0007
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0003
governing_stories:
- US-0094
- US-0096
target_bc: prd
---

# TASK-0035: Outcome-to-BDD Scenario Decomposition and Incremental Delta Scope Evolution

## Summary
Upgrade the PRD decomposition engine to support fine-grained checkable outcome decomposition (`spec-ops prd decompose <prd-id> --by-outcomes`) and non-destructive delta scope evolution (`spec-ops prd decompose <prd-id> --diff`). Decompose each entry under `## Checkable Outcomes` into a dedicated executable BDD user story in `docs/project/user_stories/accepted/us-XXXX-*.md` with an executable Gherkin skeleton. Detect scope deltas (added/modified outcomes) in evolving PRDs and generate targeted delta vertical slices without mutating existing completed or refined tasks, while warning on deprecated or deleted outcomes.

## Problem Statement & Context
The initial `PRDDecomposer` emits only a single generic placeholder user story and speculative task slices, creating a loose coupling between business outcomes and engineering deliverables. As product scope evolves incrementally, running decomposition again risks overwriting in-flight tasks, duplicating task IDs, or destroying git commit provenance. SpecOps needs a deterministic outcome-driven decomposition pipeline that converts discrete checkable outcomes directly into BDD scenarios and supports incremental delta runs without disturbing active worktrees.

## User Stories & Scenarios Satisfied
- **US-0094: Checkable Outcome-to-BDD Scenario Decomposition and Falsifiability Verification**
  - *Scenario: Decomposing a PRD by its checkable outcomes into discrete BDD user stories*
  - *Scenario: Rejecting non-falsifiable or subjective outcomes during decomposition*
  - *Scenario: Linking synthesized user stories back into the PRD and task frontmatter*
- **US-0096: Incremental PRD Delta Decomposition and Non-Destructive Scope Evolution**
  - *Scenario: Decomposing newly added checkable outcomes into incremental delta tasks*
  - *Scenario: Preserving existing completed and refined tasks during delta decomposition*
  - *Scenario: Flagging removed or deprecated checkable outcomes*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Decompose decomposition logic across `src/spec_ops/prd/decomposer.py` and new module `src/spec_ops/prd/delta.py`, keeping each file well under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated outcome modifications verify that delta decomposition is strictly additive: existing task frontmatter, IDs, file paths, and statuses in `complete/` and `refined/` remain byte-identical before and after delta decomposition.
- **Mutmut Mutation Scope**: Core outcome parsing and delta calculation logic in `src/spec_ops/prd/delta.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops prd decompose <prd-id> --by-outcomes` parses every discrete checkable outcome, validates its falsifiability (aborting with exit code 1 if subjective), and generates a corresponding BDD story with an executable Gherkin skeleton under `docs/project/user_stories/accepted/`.
2. Executing `spec-ops prd decompose <prd-id> --diff` detects newly added outcomes, synthesizes only the necessary delta stories and vertical slice proposed tasks, and appends them to `PRIORITY.md` without modifying any existing tasks.
3. Executing `spec-ops prd decompose <prd-id> --diff` when an outcome has been removed warns the user if pending tasks reference that outcome.
4. Generated user stories and tasks update `## Linked User Stories` in the PRD and set `governing_stories` in task frontmatter.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
