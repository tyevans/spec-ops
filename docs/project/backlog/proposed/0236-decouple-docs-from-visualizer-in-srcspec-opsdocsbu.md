---
id: '0236'
title: 'Decouple Docs from Visualizer in src/spec_ops/docs/builder.py'
status: Proposed
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
target_bc: docs
---

# TASK-0236: Decouple Docs from Visualizer in src/spec_ops/docs/builder.py

## Summary
Decouple docs builder from visualizer standalone HTML compilation.

## Problem Statement & Context
docs (layer 1) illegally imports generate_standalone_html from visualizer.generator (layer 4) in src/spec_ops/docs/builder.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Coordinate visualizer HTML embedding at the application layer (spec_ops.app.site_bundler) or pass compiled visualizer assets into docs builder via parameters.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
