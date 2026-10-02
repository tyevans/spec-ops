---
id: 0238
title: Decouple Profiles from Scaffold in src/spec_ops/profiles/security.py
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
target_bc: profiles
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T17:34:29.319711+00:00'
commit_signature_status: SIGNED
allows_dependencies: true
has_signed_commits: true
---

# TASK-0238: Decouple Profiles from Scaffold in src/spec_ops/profiles/security.py

## Summary
Decouple profiles security synchronization from scaffold AGENTS.md generator.

## Problem Statement & Context
profiles (layer 2) illegally imports scaffold_agents_command from scaffold.agents_md (layer 3) in src/spec_ops/profiles/security.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Invert dependency by having scaffold commands or CLI orchestration execute profile sync and agents scaffolding in sequence, or invoke via lifecycle hooks.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
