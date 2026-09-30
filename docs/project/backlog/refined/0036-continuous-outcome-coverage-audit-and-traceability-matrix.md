---
id: '0036'
title: Continuous PRD Outcome Coverage Audit and Persona-to-Commit Traceability Engine
status: Refined
dependencies:
- TASK-0004
- TASK-0035
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0007
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0003
governing_stories:
- US-0048
- US-0095
target_bc: prd
claimed_by: worker-1
branch: feat/0036-continuous-prd-outcome-coverage-audit-an
---

# TASK-0036: Continuous PRD Outcome Coverage Audit and Persona-to-Commit Traceability Engine

## Summary
Implement continuous checkable outcome coverage auditing (`spec-ops prd audit --deep`) and the persona-to-commit bidirectional traceability engine (`spec-ops stats --persona-coverage`). Verify that 100% of checkable outcomes in accepted PRDs are backed by executable BDD user stories and implementing backlog tasks. Detect orphaned outcomes, unanchored backlog tasks claiming PRD implementation, and neglected customer personas. Integrate unbroken lineage reporting (Persona -> PRD -> User Story -> Backlog Task -> Git Commit) into the relational graph engine with deep-link permalinks.

## Problem Statement & Context
While SpecOps tracks high-level entity counts, it lacks deep verification of checkable outcome coverage. Specifications drift when product outcomes are added without corresponding user stories, or when rogue backlog tasks claim PRD alignment without implementing any checkable outcome. Furthermore, product managers cannot easily audit persona coverage to discover neglected customer segments or trace a persona need directly down to the specific git commits that fulfilled it.

## User Stories & Scenarios Satisfied
- **US-0048: Persona-to-Commit Bidirectional Traceability Matrix and Coverage Auditor**
  - *Scenario: Inspecting Full Lineage for a Customer Persona*
  - *Scenario: Auditing Persona Coverage and Highlighting Neglected Customer Segments*
  - *Scenario: Instant Stakeholder Query Resolution via Shareable Permalinks*
- **US-0095: Continuous PRD Outcome Coverage Audit and Specification Drift Detection**
  - *Scenario: Auditing an accepted PRD with 100% checkable outcome coverage*
  - *Scenario: Detecting orphaned outcomes lacking BDD user stories or tasks*
  - *Scenario: Flagging unlinked backlog tasks claiming to implement a PRD without outcome mapping*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Traceability and deep audit logic must be structured across `src/spec_ops/prd/audit.py` and `src/spec_ops/prd/traceability.py`, maintaining both files well under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated relational graphs assert that calculated outcome coverage percentage is strictly between 0.0 and 100.0, and every detected orphan outcome or unanchored task has a non-empty diagnostic message citing the offending entity IDs.
- **Mutmut Mutation Scope**: Relational lineage traversal and coverage computation algorithms in `src/spec_ops/prd/audit.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops prd audit --deep` validates all checkable outcomes in accepted PRDs, reports coverage percentage, detects orphaned outcomes and unanchored tasks, and exits with returncode 1 when coverage gaps are found.
2. Executing `spec-ops stats --persona-coverage` outputs the task/story distribution across all personas from `PERSONAS.md` and issues warnings for any personas with zero active work items in the current milestone.
3. Querying persona lineage via the relational engine returns unbroken paths from Persona to PRD to Story to Task to Commit SHA, generating deep-link query parameters (`#tab=prds&entity=PRD-XXXX&filter=...`).
4. All acceptance criteria verified via blackbox `pytest-bdd` scenarios without private mock backdoors (ADR-0003, ADR-0006).
