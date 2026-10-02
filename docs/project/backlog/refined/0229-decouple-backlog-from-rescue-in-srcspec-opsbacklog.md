---
id: 0229
title: Decouple Backlog from Rescue in src/spec_ops/backlog/rescue.py
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
target_bc: backlog
---

# TASK-0229: Decouple Backlog from Rescue in src/spec_ops/backlog/rescue.py

## Summary
Decouple backlog from higher-layer rescue imports (complete_salvage, purge_ephemeral_handover_artifacts, clear_step_cache).

## Problem Statement & Context
backlog (layer 2) illegally imports from rescue (layer 3) in src/spec_ops/backlog/rescue.py, causing radar violation and flashing red lines on the visualizer.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Migrate RescueManager and worktree salvage orchestration from spec_ops.backlog to spec_ops.app.rescue_lifecycle or spec_ops.rescue, leaving backlog purely focused on task state transitions.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
