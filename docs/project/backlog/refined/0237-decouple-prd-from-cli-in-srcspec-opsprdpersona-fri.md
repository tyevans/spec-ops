---
id: '0237'
title: Decouple PRD from CLI in src/spec_ops/prd/persona_friction.py
status: Refined
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
target_bc: prd
allows_dependencies: true
---

# TASK-0237: Decouple PRD from CLI in src/spec_ops/prd/persona_friction.py

## Summary
Decouple PRD persona friction auditor from CLI argument parser.

## Problem Statement & Context
prd (layer 2) illegally imports build_parser from cli.parser (layer 5) in src/spec_ops/prd/persona_friction.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Pass CLI command schemas or command strings into persona friction analyzer via dependency injection from CLI caller rather than importing cli.parser directly.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
