---
id: '0061'
title: Generative Hypothesis Property Invariants, Mutation Testing Quality Gate, and Anti-Mock Linter
status: Proposed
created: 2026-09-29
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
  - US-0062
  - US-0064
  - US-0020
target_bc: core
---

# TASK-0061: Generative Hypothesis Property Invariants, Mutation Testing Quality Gate, and Anti-Mock Linter

## Summary
Implement automated quality verification gates: author comprehensive generative property tests using Hypothesis (`@given`) for all core domain models and graph topology algorithms (`spec-ops test properties`), enforce a strict Mutmut mutation kill score quality gate (`spec-ops test mutation --threshold 80`), and establish an AST-based blackbox frontdoor test verification gate (`spec-ops test audit-anti-mock`) that rejects prohibited mock backdoors, monkeypatching, and private method state manipulation per ADR-0003.

## Problem Statement & Context
High line test coverage often conceals fragile or tautological assertions that pass even when underlying domain logic is broken. Autonomous agents may author weak assertions or inject private method mocks that bypass observable public interfaces. SpecOps requires continuous generative property-based invariants, mutation testing quality gates, and an AST anti-mock linter to guarantee that test suites verify observable contracts without backdoor tampering.

## User Stories & Scenarios Satisfied
- **US-0062: Generative Property-Based Invariant Verification for Core Models and Graph Topology**
  - *Scenario: Verifying Parser-to-Serializer Round-Trip Preservation invariant via Hypothesis*
    - Given arbitrary valid PMaC specifications
    - When parsed into memory AST and serialized back to markdown
    - Then the round-tripped content matches canonical representation identically.
  - *Scenario: Verifying Graph Permutation Invariance across randomized file discovery orders*
    - Given a set of specification files discovered in arbitrary filesystem order
    - When the knowledge graph is compiled
    - Then resulting entity and edge topology is deterministic and order-invariant.
- **US-0064: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate**
  - *Scenario: Passing the mutation quality gate on core domain modules*
    - Given core domain modules with high-fidelity blackbox test suites
    - When "spec-ops test mutation --threshold 80" runs
    - Then mutants are generated, killed by tests, and the command exits with code 0.
  - *Scenario: Blocking pull request when weak assertions leave surviving mutants below threshold*
    - Given a test suite with tautological or weak assertions
    - When mutation score falls below 80%
    - Then the command fails with a detailed breakdown of surviving mutants.
- **US-0020: Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate**
  - *Scenario: Passing Clean Blackbox Test Suite with Mutation Invariants*
    - Given a test suite that exercises only public CLI and module frontdoors
    - When "spec-ops test audit-anti-mock" scans the test tree
    - Then zero anti-mock violations are reported.
  - *Scenario: Blocking Tests with Prohibited Mock Backdoors and Private Method Spies*
    - Given a test that monkeypatches private attributes or imports unittest.mock
    - When anti-mock audit runs
    - Then the test file is flagged with line numbers and commit is blocked.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Mutation runner in `src/spec_ops/core/mutation_gate.py` and anti-mock scanner in `src/spec_ops/core/anti_mock.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary python AST structures verify that the anti-mock scanner correctly identifies all forms of mock import and patching without false positives on legitimate public test fixtures.
- **Mutmut Mutation Scope**: AST inspection logic in `src/spec_ops/core/anti_mock.py` and score calculation in `src/spec_ops/core/mutation_gate.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops test properties` runs Hypothesis property tests verifying domain models and graph topology invariance.
2. Executing `spec-ops test mutation --threshold 80` runs `mutmut` across core packages and exits 0 only if mutant kill score >=80%.
3. Executing `spec-ops test audit-anti-mock` statically scans `tests/` ASTs and flags any private method mocking or monkeypatching.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
