---
id: '0246'
title: Decouple PRD from Visualizer in src/spec_ops/prd/studio_runner.py
status: Complete
dependencies:
- TASK-0243
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: prd
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T17:56:49.616433+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0246: Decouple PRD from Visualizer in src/spec_ops/prd/studio_runner.py

## Summary
Decouple PRD bounded context from visualizer server by relocating studio runner or using application layer orchestration.

## Problem Statement & Context
prd (layer 2) illegally imports serve_visualizer from visualizer (layer 4) in src/spec_ops/prd/studio_runner.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Relocate studio server launching to `spec_ops.app` or invoke `serve_visualizer` directly from `spec_ops.cli.prd_handler`, preserving backwards-compatibility via `spec_ops.app` or dependency injection.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `harvest_architecture_radar()` showing 0 prohibited boundary violations for prd -> visualizer.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
