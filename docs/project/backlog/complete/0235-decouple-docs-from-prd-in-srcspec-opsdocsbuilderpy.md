---
id: '0235'
title: Decouple Docs from PRD in src/spec_ops/docs/builder.py
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
target_bc: docs
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T17:21:50.692769+00:00'
commit_signature_status: SIGNED
allows_dependencies: true
has_signed_commits: true
---

# TASK-0235: Decouple Docs from PRD in src/spec_ops/docs/builder.py

## Summary
Decouple docs builder from prd exporter roadmap generation.

## Problem Statement & Context
docs (layer 1) illegally imports export_roadmap from prd.exporter (layer 2) in src/spec_ops/docs/builder.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Move static site multi-artifact assembly to spec_ops.app.site_bundler, keeping docs.builder focused on Diataxis markdown compilation.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
