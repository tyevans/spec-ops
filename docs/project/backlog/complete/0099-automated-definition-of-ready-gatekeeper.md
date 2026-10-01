---
id: 0099
title: Automated Definition of Ready Gatekeeper and Ticket Health Audit
status: Complete
dependencies:
- TASK-0065
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0005
governing_stories:
- US-0024
target_bc: backlog
---

# TASK-0099: Automated Definition of Ready Gatekeeper and Ticket Health Audit

## Summary
Implement an automated Definition of Ready (DoR) gatekeeper command (`spec-ops queue refine <task-id>`) and backlog ticket health auditor that evaluates whether proposed tasks meet INVEST criteria, cite governing PRDs/Personas/ADRs, provide executable Gherkin scenarios, and satisfy file limit invariants before permitting promotion into `refined/`.

## Problem Statement & Context
Tasks drafted without rigorous Definition of Ready (DoR) specifications cause autonomous workers and human developers to stall or make incorrect architectural assumptions. Vague acceptance criteria, missing ADR citations, and oversized scope lead to broken builds and wasted compute. SpecOps requires an automated DoR gatekeeper that enforces specification quality before any task enters active development.

## User Stories & Scenarios Satisfied
- **US-0024: Automated Definition of Ready Gatekeeper and Ticket Health Audit**
  - *Scenario: Promoting Only Fully Compliant Tasks to Refined Buffer*
    - Given a proposed task with valid frontmatter, linked PRD, persona, ADRs, and Gherkin scenarios
    - When "spec-ops queue refine <task-id>" runs
    - Then the task passes DoR evaluation and transitions to `refined/`.
  - *Scenario: Rejecting Half-Baked Proposed Tasks Lacking Gherkin Criteria*
    - Given a proposed task lacking executable Gherkin scenarios
    - When refinement is attempted
    - Then the command fails with exit code 1 and lists missing DoR requirements.
  - *Scenario: Rejecting Tasks Violating Single-Responsibility Scope*
    - Given a proposed task spanning multiple unrelated bounded contexts
    - When DoR evaluation runs
    - Then the task is rejected with recommendations to decompose.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: DoR gatekeeper in `src/spec_ops/backlog/dor_gate.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that any task missing one or more required DoR elements is deterministically rejected with non-zero exit code.
- **Mutmut Mutation Scope**: DoR criteria validation and error formatting in `src/spec_ops/backlog/dor_gate.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue refine <task-id>` audits all DoR criteria and transitions compliant tasks to `refined/`.
2. Missing Gherkin scenarios, PRD links, or ADR links are reported with actionable diagnostic messages.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
