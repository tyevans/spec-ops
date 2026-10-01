---
id: '0156'
title: Autonomous BDD Feature Scenario Coverage Matrix and Living Acceptance Dashboard
status: Complete
dependencies:
- TASK-0111
- TASK-0135
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0003
governing_stories:
- US-0094
- US-0117
target_bc: prd
---

# TASK-0156: Autonomous BDD Feature Scenario Coverage Matrix and Living Acceptance Dashboard

## Summary
Implement an autonomous BDD scenario coverage auditor and living acceptance dashboard generator (`src/spec_ops/prd/bdd_matrix.py`). Governed by ADR-0006 and PRD-0003, this engine parses all accepted user stories in `docs/project/user_stories/accepted/`, extracts executable Gherkin scenarios, correlates them with active pytest-bdd test implementations in `tests/`, and computes bidirectional scenario coverage rates (`spec-ops prd coverage`).

## Problem Statement & Context
As user stories proliferate across bounded contexts, engineering teams lack real-time visibility into whether all Gherkin acceptance criteria have corresponding executable pytest-bdd step definitions. Orphaned scenarios or unimplemented criteria lead to undetected regressions. An automated coverage engine provides transparent auditability and living documentation for quality assurance.

## Key Requirements & Scope
1. **BDD Scenario Coverage Auditor (`src/spec_ops/prd/bdd_matrix.py`)**:
   - Parses all user stories under `docs/project/user_stories/accepted/` and extracts Scenario / Scenario Outline titles and tags.
   - Scans `tests/` for `test_bdd_*.py` files and feature bindings (`@scenario`, `@given`, `@when`, `@then`).
   - Generates bidirectional mapping: Story Scenario -> Test Function -> Execution Status.
   - Computes coverage percentage per user story and bounded context.
2. **Coverage CLI (`spec-ops prd coverage [--strict] [--json] [--bc <context>]`)**:
   - Displays a formatted console table showing story coverage ratios and missing scenario bindings.
   - When `--strict` is enabled, exits with code 1 if any accepted story has 0% automated scenario coverage.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate verifying public CLI interface and parser contracts with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/prd/bdd_matrix.py` must stay strictly under 400 lines (ADR-0002).
- **Blackbox Frontdoor Verification (ADR-0003)**: Exercise strictly through public CLI entry points and public model interfaces.
- **Mutation Testing Scope**: Target module `src/spec_ops/prd/bdd_matrix.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Auditing BDD coverage across accepted user stories
```gherkin
Given a set of accepted user stories with executable Gherkin scenarios
And corresponding pytest-bdd test modules in the test suite
When the developer runs spec-ops prd coverage
Then the scenario coverage matrix reports mapped scenarios and overall coverage percentage
And exits with success code 0
```

### Scenario 2: Failing strict coverage check when unimplemented scenarios exist
```gherkin
Given an accepted user story with scenarios lacking test implementations
When the developer runs spec-ops prd coverage with strict mode enabled
Then the command reports the missing scenario bindings
And terminates with exit code 1
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any syntactically valid Gherkin story content and arbitrary directory structure, scenario extraction returns deterministic scenario lists without duplicate IDs or crashes.
