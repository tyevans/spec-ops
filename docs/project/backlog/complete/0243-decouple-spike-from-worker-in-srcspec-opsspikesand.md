---
id: '0243'
title: Decouple Spike from Worker in src/spec_ops/spike/sandbox.py
status: Complete
dependencies:
- TASK-0242
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: spike
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T17:53:59.093411+00:00'
commit_signature_status: SIGNED
allows_dependencies: true
has_signed_commits: true
---

# TASK-0243: Decouple Spike from Worker in src/spec_ops/spike/sandbox.py

## Summary
Decouple spike sandbox from worker git worktree creation and cleanup.

## Problem Statement & Context
spike (layer 2) illegally imports cleanup_worktree and create_worktree from worker.worktree (layer 3) in src/spec_ops/spike/sandbox.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Relocate git worktree management primitives to spec_ops.core.git_worktree. Both spike and worker depend downward on core.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).
