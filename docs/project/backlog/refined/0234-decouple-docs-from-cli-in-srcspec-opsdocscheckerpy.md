---
id: '0234'
title: 'Decouple Docs from CLI in src/spec_ops/docs/checker.py'
status: Refined
allows_dependencies: true
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: docs
---

# TASK-0234: Decouple Docs from CLI in src/spec_ops/docs/checker.py

## Summary
Decouple docs checker from CLI build_parser argument parsing.

## Problem Statement & Context
docs (layer 1) illegally imports build_parser from cli.parser (layer 5) in src/spec_ops/docs/checker.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Pass command specifications or parser models into evaluate_cli_drift via dependency injection from the CLI composition root, eliminating docs -> cli import.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
