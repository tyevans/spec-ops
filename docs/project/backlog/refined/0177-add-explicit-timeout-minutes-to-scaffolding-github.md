---
id: '0177'
title: Add Explicit timeout-minutes to Scaffolding GitHub Actions Workflow Jobs
status: Refined
governing_adrs:
- ADR-0004
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: core
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
---

# TASK-0177: Add Explicit timeout-minutes to Scaffolding GitHub Actions Workflow Jobs

## Summary
The GitHub Actions workflow scaffolding templates in `src/spec_ops/scaffold/ci_workflow.py` and `src/spec_ops/scaffold/pages_workflow.py` generate workflow jobs without explicit `timeout-minutes`. In repositories with CI governance rules (e.g. tests verifying that every workflow job sets an explicit timeout), these generated workflows fail CI quality gates.

## Problem Statement & Context
1. In `src/spec_ops/scaffold/pages_workflow.py`:
   ```yaml
   jobs:
     deploy-pages:
       runs-on: ubuntu-latest
   ```
2. In `src/spec_ops/scaffold/ci_workflow.py`:
   ```yaml
   jobs:
     preflight-and-invariants:
       name: SpecOps Invariant & Health Check
       runs-on: ubuntu-latest
   ```
3. Neither job specifies `timeout-minutes`. In GitHub Actions, jobs without `timeout-minutes` inherit the default 360-minute (6-hour) timeout.
4. When adopting SpecOps in a codebase with automated workflow auditing (e.g. `test_every_workflow_job_has_a_timeout`), the generated workflows fail the test suite immediately.

## Proposed Fix
1. Add explicit `timeout-minutes` (e.g. `timeout-minutes: 15` or `timeout-minutes: 30`) to all job definitions in `ci_workflow.py` and `pages_workflow.py`.
2. Add a template parameter or configuration option in `specops.toml` allowing users to configure workflow timeout limits if desired.

## Definition of Done (Blackbox Frontdoor TDD)
1. Unit test verifying generated workflows contain `timeout-minutes:` for each job.
2. Adopted projects with workflow timeout assertions pass tests cleanly.

## Acceptance Criteria

```gherkin
Scenario: Verify Add Explicit timeout-minutes to Scaffolding GitHub Actions Workflow Jobs
  Given the system is initialized and ready
  When the user executes the workflow for "Add Explicit timeout-minutes to Scaffolding GitHub Actions Workflow Jobs"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `core` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
