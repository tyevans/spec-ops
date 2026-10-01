---
id: '0177'
title: Add Explicit timeout-minutes to Scaffolding GitHub Actions Workflow Jobs
status: Proposed
governing_adrs:
- ADR-0004
target_bc: core
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
