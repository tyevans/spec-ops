---
id: '0100'
title: Living Architectural Review Radar and Bounded Context Dependency Audit
status: Complete
dependencies:
- TASK-0070
- TASK-0060
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0106
target_bc: visualizer
---

# TASK-0100: Living Architectural Review Radar and Bounded Context Dependency Audit

## Summary
Implement a living architectural review radar and bounded context dependency auditor: author an interactive visual radar auditing bounded context couplings, detecting illegal cross-context module imports, visualizing ADR supersession trees, and highlighting orphaned work items or specification drift in real time.

## Problem Statement & Context
As multi-agent coding assistants generate modules across bounded contexts, subtle architectural erosion occurs: private helper functions get imported across context seams, or tasks cite superseded ADRs without human architects noticing. Without an automated review radar, structural debt compounds silently until major refactoring is required. SpecOps requires an interactive radar view to visualize architectural boundary health and enforce domain invariants.

## User Stories & Scenarios Satisfied
- **US-0106: Living Architectural Review Radar and Bounded Context Dependency Audit**
  - *Scenario: Bounded Context Boundary and Dependency Flow Inspection*
    - Given the codebase organized into explicit bounded contexts
    - When the architect views the Architectural Review Radar tab
    - Then cross-context coupling matrices highlight permissible and prohibited import vectors.
  - *Scenario: ADR Supersession Lineage and Active Status Radar*
    - Given active and superseded ADRs in `docs/project/adrs/`
    - When the radar inspects decision lineage
    - Then active decisions are green, superseded decisions are flagged, and tasks citing obsolete ADRs are listed.
  - *Scenario: Automated Orphan Work Item and Specification Drift Audit*
    - Given work items without governing stories or commits without tasks
    - When the review audit executes
    - Then orphan entities are highlighted with actionable remediation links.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Radar visualizer module in `src/spec_ops/visualizer/radar_script.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary dependency graphs assert that the radar correctly partitions all bounded-context relationships into acyclic layers without false positives on standard library imports.
- **Mutmut Mutation Scope**: Boundary violation detection in `src/spec_ops/visualizer/radar_script.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Architectural Review Radar tab displays bounded context coupling matrices, highlights illegal cross-context imports, and visualizes ADR supersession trees.
2. CLI verification command (`spec-ops health --architecture`) validates clean boundary separation and reports zero illegal cross-context imports.
3. All scenarios verified via public frontdoor CLI and Playwright tests without mock backdoors (ADR-0003, ADR-0006).
