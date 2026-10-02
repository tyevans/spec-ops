---
id: '0231'
title: Decouple Backlog from Worker in src/spec_ops/backlog/queue.py
status: Complete
dependencies:
- TASK-0244
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: backlog
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T16:17:35.780033+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0231: Decouple Backlog from Worker in src/spec_ops/backlog/queue.py

## Summary
Decouple backlog queue from worker git integration, commit formatting, and merge lock manager.

## Problem Statement & Context
backlog (layer 2) illegally imports MergeLockManager, format_task_commit_message, and squash_merge_and_commit from worker (layer 3) in src/spec_ops/backlog/queue.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Move task completion git integration and merge lock acquisition into spec_ops.app.task_lifecycle, keeping BacklogQueue purely focused on queue ordering and state files.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
