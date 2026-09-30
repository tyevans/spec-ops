---
id: '0096'
title: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate
status: Refined
dependencies:
  - TASK-0060
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0005
governing_stories:
  - US-0064
target_bc: core
---

# TASK-0096: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate

## Summary
Implement automated mutation testing quality gating (`spec-ops test mutation [--threshold 80] [--bc <context>]`) using Mutmut to systematically verify assertion strength across core domain modules, failing CI if the mutant kill score falls below the required 80% threshold per ADR-0009.

## Problem Statement & Context
High code coverage percentages frequently mislead teams by measuring lines executed rather than behavioral assertion strength. Weak or tautological assertions pass test suites while allowing domain mutations to survive undetected. SpecOps requires automated mutation testing gates that generate code mutations in pure domain logic, assert that test suites detect and kill them, and block pull requests that fall below the 80% mutant kill threshold.

## User Stories & Scenarios Satisfied
- **US-0064: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate**
  - *Scenario: Passing the mutation quality gate on core domain modules*
    - Given core domain modules with high-fidelity blackbox test suites
    - When "spec-ops test mutation --threshold 80" runs
    - Then mutants are generated, killed by tests, and the command exits with code 0.
  - *Scenario: Blocking pull request when weak assertions leave surviving mutants below threshold*
    - Given a test suite with tautological or weak assertions
    - When mutation score falls below 80%
    - Then the command fails with a detailed breakdown of surviving mutants.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Mutation gate runner and report generator in `src/spec_ops/core/mutation_gate.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that mutation score calculation correctly computes `killed / total` across arbitrary mutant counts and handles zero mutants gracefully.
- **Mutmut Mutation Scope**: Score aggregation and threshold evaluation in `src/spec_ops/core/mutation_gate.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops test mutation --threshold 80` runs `mutmut` across target domain modules and exits 0 only if mutant kill score is at or above 80%.
2. Surviving mutants are reported with source file paths, line numbers, and mutated AST expressions.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
