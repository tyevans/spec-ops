---
id: '0078'
title: Architectural Decision Record Supersession and Deprecation Workflow
status: Refined
dependencies:
- TASK-0010
- TASK-0063
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0005
governing_stories:
- US-0014
target_bc: scaffold
---

# TASK-0078: Architectural Decision Record Supersession and Deprecation Workflow

## Summary
Implement automated ADR supersession workflow (`spec-ops adr supersede <old-id> --by <new-id>`) that atomically updates frontmatter statuses, cross-references superseding and superseded decisions in `REGISTRY.md`, and flags active backlog tasks citing obsolete decisions.

## Problem Statement & Context
When architecture evolves, existing ADRs are superseded by new decisions. If superseded ADRs are not tracked with atomic bidirectional links and updated registries, developers and autonomous agents continue referencing obsolete decisions. SpecOps requires an automated workflow to supersede decisions cleanly while auditing active backlog tasks.

## User Stories & Scenarios Satisfied
- **US-0014: Architectural Decision Record Supersession and Living Constitution Synchronization**
  - *Scenario: Superseding an ADR and updating registry links*
  - *Scenario: Flagging active backlog tasks citing superseded ADRs*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: ADR supersession handler in `src/spec_ops/adrs/supersede.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that for any valid pair of ADRs, supersession produces bidirectional cross-links and never creates circular supersession cycles.
- **Mutmut Mutation Scope**: Frontmatter rewriting and registry updating logic in `src/spec_ops/adrs/supersede.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops adr supersede <old-id> --by <new-id>` atomically updates frontmatter, registry, and cross-references.
2. Active tasks citing superseded ADRs surfaced proactively during validation.
3. All scenarios executed via `pytest-bdd` against CLI frontdoors with zero mock backdoors (ADR-0003, ADR-0006).
