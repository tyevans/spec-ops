---
id: '0242'
title: Decouple Security from Worker in src/spec_ops/security/sandbox.py
status: Complete
dependencies:
- TASK-0241
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
signed_off_at: '2026-10-02T17:50:26.003397+00:00'
commit_signature_status: SIGNED
allows_dependencies: true
has_signed_commits: true
---

# TASK-0242: Decouple Security from Worker in src/spec_ops/security/sandbox.py

## Summary
Decouple security execution sandbox from worker sandbox environment sanitizer.

## Problem Statement & Context
security (layer 1) illegally imports sanitize_environment from worker.sandbox_env (layer 3) in src/spec_ops/security/sandbox.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Relocate sanitize_environment into spec_ops.security.sandbox. Worker consumes security downward.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
