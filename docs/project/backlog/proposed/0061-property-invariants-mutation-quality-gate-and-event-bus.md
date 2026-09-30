---
id: '0061'
title: Generative Hypothesis Property Invariants, Mutation Testing Quality Gate, and Real-Time Graph Event Bus
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
  - US-0065
  - US-0020
target_bc: core
---

# TASK-0061: Generative Hypothesis Property Invariants, Mutation Testing Quality Gate, and Real-Time Graph Event Bus

## Summary
Implement automated quality verification gates and real-time reactive graph synchronization: author comprehensive generative property tests using Hypothesis (`@given`) for all core domain models and graph topology algorithms, enforce a strict Mutmut mutation kill score quality gate (`spec-ops test mutation --threshold 80`), establish a blackbox frontdoor test verification gate (`spec-ops test audit-anti-mock`) that rejects prohibited mock backdoors or private method tampering, and implement a real-time in-memory graph event bus with debounced file watching (`spec-ops watch`) emitting live graph delta events upon disk modifications.

## Problem Statement & Context
High test coverage numbers often conceal fragile assertions that pass even when underlying domain logic is broken. Autonomous agents may author tautological assertions or inject private method mocks that bypass observable public interfaces. Additionally, as developers and background agents edit specifications simultaneously, tools must reactively detect unanchored references and status changes without requiring constant manual CLI re-invocation. SpecOps requires generative property-based invariants, mutation testing quality gates, and an in-memory event bus to guarantee system resilience.

## User Stories & Scenarios Satisfied
- **US-0062: Generative Property-Based Invariant Verification for Core Models and Graph Topology**
  - *Scenario: Verifying Parser-to-Serializer Round-Trip Preservation invariant via Hypothesis*
  - *Scenario: Verifying Graph Permutation Invariance across randomized file discovery orders*
  - *Scenario: Generative invariant test execution via CLI gatekeeper*
- **US-0064: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate**
  - *Scenario: Passing the mutation quality gate on core domain modules*
  - *Scenario: Blocking pull request when weak assertions leave surviving mutants below threshold*
  - *Scenario: Generating machine-readable mutation score report for CI telemetry*
- **US-0065: Real-Time In-Memory Graph Event Bus and Workspace Change Watcher**
  - *Scenario: Publishing real-time graph delta events when a task transitions status*
  - *Scenario: Immediate warning emission upon authoring an unanchored reference*
  - *Scenario: Clean shutdown and debounced multi-file git checkout handling*
- **US-0020: Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate**
  - *Scenario: Passing Clean Blackbox Test Suite with Mutation Invariants*
  - *Scenario: Blocking Tests with Prohibited Mock Backdoors and Private Method Spies*
  - *Scenario: Mutation Score Threshold Enforcement*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Mutation gate runner in `src/spec_ops/core/mutation_gate.py`, anti-mock linter in `src/spec_ops/core/anti_mock.py`, and event bus in `src/spec_ops/core/event_bus.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that for any arbitrary sequence of graph mutation events, the event bus maintains deterministic state consistency with cold graph re-parsing (event replay isomorphism).
- **Mutmut Mutation Scope**: Event bus dispatch in `src/spec_ops/core/event_bus.py` and anti-mock AST analysis in `src/spec_ops/core/anti_mock.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops test properties` runs Hypothesis property-based suites verifying parser round-trips and graph permutation invariance across 100+ randomized iterations without shrinking failures.
2. Executing `spec-ops test mutation --threshold 80` runs `mutmut` across core domain packages, exiting with code 0 if kill score >=80% or code 1 if surviving mutants exceed the threshold.
3. Executing `spec-ops test audit-anti-mock` statically scans `tests/` ASTs and flags any usage of `unittest.mock.patch`, private method spies (`_private`), or direct backdoor state manipulation.
4. Executing `spec-ops watch` boots a debounced workspace watcher that prints structured graph delta events (e.g. `[TASK_PROMOTED] TASK-0021 Proposed -> Refined`) and immediately warns on unanchored references without crash during branch checkouts.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
