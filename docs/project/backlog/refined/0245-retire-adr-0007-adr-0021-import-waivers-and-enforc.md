---
id: '0245'
title: Retire ADR-0007 / ADR-0021 Import Waivers and Enforce Zero Prohibited Dependencies
  in CI Radar
status: Refined
dependencies:
- TASK-0229
- TASK-0230
- TASK-0231
- TASK-0232
- TASK-0233
- TASK-0234
- TASK-0235
- TASK-0236
- TASK-0237
- TASK-0238
- TASK-0239
- TASK-0240
- TASK-0241
- TASK-0242
- TASK-0243
- TASK-0244
- TASK-0246
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: core
allows_dependencies: true
---

# TASK-0245: Retire ADR-0007 / ADR-0021 Import Waivers and Enforce Zero Prohibited Dependencies in CI Radar

## Summary
Purge all temporary ignore_imports waivers from pyproject.toml and assert 0 boundary violations across all bounded contexts in CI.

## Problem Statement & Context
Temporary ignore_imports entries in pyproject.toml mask architectural rot in external linters. With all 15 boundary violations remediated, these waivers must be permanently retired.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
1. Remove all 27 importlinter ignore_imports waivers from pyproject.toml.
2. Verify lint-imports and spec-ops arch pass with 0 warnings/violations.
3. Add regression test asserting 0 backward dependencies in harvest_architecture_radar().

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
