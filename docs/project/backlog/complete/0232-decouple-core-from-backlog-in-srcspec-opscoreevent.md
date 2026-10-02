---
id: '0232'
title: Decouple Core from Backlog in src/spec_ops/core/event_store.py
status: Complete
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: core
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T17:06:56.041297+00:00'
commit_signature_status: SIGNED
allows_dependencies: true
has_signed_commits: true
---

# TASK-0232: Decouple Core from Backlog in src/spec_ops/core/event_store.py

## Summary
Decouple core event store from backlog TaskDecider, events, and queue read-models.

## Problem Statement & Context
core (layer 1) illegally imports TaskDecider, events, and write_task_file from backlog (layer 2) in src/spec_ops/core/event_store.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Define pure domain event store abstractions and event publishers in core; project events to backlog markdown read-models via event subscribers or dependency inversion.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
