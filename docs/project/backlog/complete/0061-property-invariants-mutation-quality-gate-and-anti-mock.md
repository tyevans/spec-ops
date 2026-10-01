---
id: '0061'
title: AST Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate
status: Complete
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
- US-0020
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0061: AST Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate

## Summary
Implement an AST-based blackbox frontdoor test verification gate (`spec-ops test audit-anti-mock`) that inspects test files and rejects prohibited mock backdoors, monkeypatching of private methods (`_private`), and unittest.mock imports per ADR-0003.

## Problem Statement & Context
Autonomous coding assistants and human developers sometimes reach into private implementation internals or inject private method mocks to force tests to pass without verifying real public interfaces. This produces brittle tests that break during refactoring and conceals integration regressions. SpecOps requires an automated AST anti-mock linter that strictly enforces ADR-0003 by detecting and rejecting mock backdoors before integration.

## User Stories & Scenarios Satisfied
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
- **File Length Limit (<500 lines)**: Anti-mock AST scanner in `src/spec_ops/core/anti_mock.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary python AST structures verify that the anti-mock scanner correctly identifies all forms of mock import and patching without false positives on legitimate public test fixtures.
- **Mutmut Mutation Scope**: AST inspection logic in `src/spec_ops/core/anti_mock.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops test audit-anti-mock` statically scans `tests/` ASTs and flags any private method mocking, monkeypatching, or prohibited mock imports with exact file and line pointers.
2. Anti-mock audit exits with code 0 on clean blackbox test suites and code 1 on violations.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
