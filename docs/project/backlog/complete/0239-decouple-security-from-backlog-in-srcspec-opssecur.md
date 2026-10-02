---
id: 0239
title: Decouple Security from Backlog in src/spec_ops/security/dual_custody.py
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
target_bc: security
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T17:38:25.479063+00:00'
commit_signature_status: SIGNED
allows_dependencies: true
has_signed_commits: true
---

# TASK-0239: Decouple Security from Backlog in src/spec_ops/security/dual_custody.py

## Summary
Decouple security dual custody gate from backlog queue and task file persistence.

## Problem Statement & Context
security (layer 1) illegally imports BacklogQueue and write_task_file from backlog.queue (layer 2) in src/spec_ops/security/dual_custody.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Provide task query and sign-off mutation ports in security, or pass task metadata into dual custody verification without importing backlog queue infrastructure.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
