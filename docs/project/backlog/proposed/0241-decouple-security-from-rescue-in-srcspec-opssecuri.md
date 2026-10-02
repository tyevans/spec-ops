---
id: '0241'
title: 'Decouple Security from Rescue in src/spec_ops/security/dual_custody.py'
status: Proposed
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: security
---

# TASK-0241: Decouple Security from Rescue in src/spec_ops/security/dual_custody.py

## Summary
Decouple security dual custody gate from rescue handover git exclusion assertion.

## Problem Statement & Context
security (layer 1) illegally imports assert_handover_excluded_from_git from rescue.handover (layer 3) in src/spec_ops/security/dual_custody.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Generalize handover git hygiene checks into spec_ops.security.hygiene or spec_ops.core.git, removing dependency on rescue.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
