---
id: '0020'
title: Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-QGT-01
governing_prd: PRD-0005
---

# US-0020 — Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** engineering lead,  
**I want** `spec-ops test verify-frontdoors` to audit the test suite in CI and worktree preflights,  
**So that** tests relying on prohibited internal monkey-patching, mock backdoors, or failing mutation kill thresholds are blocked before agents or developers can merge fragile, mock-heavy code.

## Acceptance Criteria

```gherkin
Scenario: Passing Clean Blackbox Test Suite with Mutation Invariants
Given a Python test suite where all feature tests interact exclusively through public frontdoors
And no tests invoke "unittest.mock.patch" on internal module private methods
And Mutmut mutation testing achieves >=80% mutant kill score on target domain modules
When the lead runs "spec-ops test verify-frontdoors"
Then the command exits with code 0
And reports "Frontdoor Verification Passed: 0 private backdoors detected, Mutation Kill Score: 85%".
```

```gherkin
Scenario: Blocking Tests with Prohibited Mock Backdoors and Private Method Spies
Given an autonomous agent generates a test file in an active worktree
And the test file imports private functions prefixed with "_" or uses "patch.object" on internal persistence adapters
When the in-worktree preflight executes "spec-ops test verify-frontdoors"
Then the command exits with code 1
And prints a diagnostic violation citing ADR-0003 and the exact line numbers containing prohibited mocks
And instructs the agent to exercise the feature exclusively through public entrypoints.
```

```gherkin
Scenario: Mutation Score Threshold Enforcement
Given a test suite verifying a domain state machine through public APIs
And Mutmut identifies surviving mutants dropping the mutation score to 68% (below the 80% invariant)
When the lead runs "spec-ops test verify-frontdoors --strict-mutation"
Then the command exits with code 1
And lists the surviving mutant IDs and untyped code branches requiring property or edge-case tests.
```

## Rationale & Compelling Value
Prevents the 'Silo of Mocked Perfection' (ADR-0003, ADR-0009). Passing CI guarantees real behavioral contracts that survive internal refactorings, radically lowering post-merge production incidents.
