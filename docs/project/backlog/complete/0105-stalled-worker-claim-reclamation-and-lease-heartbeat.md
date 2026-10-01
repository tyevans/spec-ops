---
id: '0105'
title: Stalled Worker Claim Reclamation and Lease Heartbeat Watcher
status: Complete
dependencies:
- TASK-0067
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0077
target_bc: backlog
---

# TASK-0105: Stalled Worker Claim Reclamation and Lease Heartbeat Watcher

## Summary
Implement automated detection and reclamation of abandoned task claims (`spec-ops queue reclaim-stalled [--timeout-hours N]`), checking heartbeat timestamps, safely revoking expired leases, returning task statuses to `Refined`, and appending to the curation audit trail.

## Problem Statement & Context
When autonomous agent worker processes crash, stall on long-running commands, or abandon isolated worktrees, claimed tasks remain locked indefinitely in the backlog with active worker tags. This blocks dependent tasks and starves other worker streams. SpecOps requires an automated claim reclamation engine that inspects worker heartbeats and safely resets stale leases back to `Refined`.

## User Stories & Scenarios Satisfied
- **US-0077: Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition**
  - *Scenario: Flagging and Reclaiming Abandoned Task Claims*
    - Given a task marked "In Progress" with a claim timestamp exceeding the configured timeout threshold (e.g. 4 hours) without heartbeat activity
    - When "spec-ops queue reclaim-stalled" is executed
    - Then the expired lease is revoked, the task status is safely returned to "Refined", and the event is logged to the curation audit trail.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Lease reclamation and heartbeat verification in `src/spec_ops/backlog/reclaim.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary timestamp distributions assert that lease expiration logic is strictly monotonic and never reclaims an active lease with a valid heartbeat.
- **Mutmut Mutation Scope**: Lease timeout and expiration calculations in `src/spec_ops/backlog/reclaim.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue reclaim-stalled` releases expired leases cleanly and resets tasks to Refined.
2. Active claims with fresh heartbeats are never reclaimed.
3. All acceptance criteria verified via public CLI frontdoors with `pytest-bdd` (ADR-0003, ADR-0006).
