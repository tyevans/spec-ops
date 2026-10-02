---
id: '0230'
title: Decouple Backlog from Visualizer in src/spec_ops/backlog/rollover.py
status: Refined
governing_adrs:
- ADR-0007
- ADR-0021
governing_prds:
- PRD-0005
governing_stories:
- US-0013
- US-0106
target_bc: backlog
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
---

# TASK-0230: Decouple Backlog from Visualizer in src/spec_ops/backlog/rollover.py

## Summary
Decouple backlog from visualizer burndown deck milestone parser in rollover.py.

## Problem Statement & Context
backlog (layer 2) illegally imports parse_roadmap_milestones from visualizer.burndown_deck (layer 4) in src/spec_ops/backlog/rollover.py.

Governed by:
- **ADR-0007**: Domain-Driven Design and Explicit Bounded Contexts.
- **ADR-0021**: Application Orchestration Layer and Dependency Inversion Boundaries.
- **US-0013**: Bounded Context Boundary and Dependency Direction Enforcement.
- **US-0106**: Living Architectural Review Radar and Bounded Context Dependency Audit.

## Architectural Remediation Plan (ADR-0021)
Move parse_roadmap_milestones to spec_ops.core.roadmap or spec_ops.backlog.roadmap. Both visualizer and backlog consume core downward.

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Verified via `uv run spec-ops arch` and `harvest_architecture_radar()` showing 0 prohibited boundary violations.
3. Tests pass with 100% pass rate (`uv run pytest`).
4. All source files strictly comply with ADR-0002 (<500 lines limit).

## Acceptance Criteria

```gherkin
Scenario: Verify Decouple Backlog from Visualizer in src/spec_ops/backlog/rollover.py
  Given the system is initialized and ready
  When the user executes the workflow for "Decouple Backlog from Visualizer in src/spec_ops/backlog/rollover.py"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/backlog/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).
