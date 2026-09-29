---
id: '0082'
title: Multi-Stage Extensible Preflight Validation Pipeline with Early Fast-Fail
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-WORK-03
governing_prd: PRD-0004
---

# US-0082 — Multi-Stage Extensible Preflight Validation Pipeline with Early Fast-Fail

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** trust and security officer,
  - **I want** autonomous workers to execute preflight checks through a structured, multi-stage validation pipeline with early fast-fail,
  - **So that** unverified dependencies, security leaks, file length limit violations, and failing tests are caught in deterministic order without wasting agent compute time.

## Acceptance Criteria

```gherkin
Scenario: Fast-Fail on Early Security and Lockfile Verification Stage
Given a worker executing "TASK-0019" in an isolated worktree
And the preflight configuration defines sequential stages: "lockfile", "health", and "tests"
When an agent updates "pyproject.toml" but fails to update "uv.lock"
And the worker runs the preflight pipeline
Then stage "lockfile" executes "uv lock --check" and fails with an out-of-sync error
And the preflight pipeline immediately halts without executing subsequent "health" or "tests" stages
And the failure output isolates the lockfile drift as the specific stage-1 failure.
```
```gherkin
Scenario: Complete Pipeline Execution Across All Configured Gates
Given an isolated worktree with valid lockfiles and clean file limits
When the worker executes the full preflight pipeline
Then the worker executes:
| Stage     | Command                  | Required |
| lockfile  | uv lock --check          | true     |
| health    | uv run spec-ops health   | true     |
| test      | uv run pytest            | true     |
And each stage executes within its dedicated timeout limit
And the worker logs a structured pipeline summary confirming all gates passed.
-
```

## Rationale & Compelling Value
- *Adoption*: Provides DevSecOps with standardized, policy-driven verification stages easily configured in `.spec-ops.yaml`.
  - *Regular Usage*: Runs before every single commit and merge, guaranteeing zero non-compliant code ever lands on `main`.
  - *Compelling Value*: Saves massive compute and agent iteration time by failing immediately on 50ms static/lockfile checks before launching 60-second test suites.

---
