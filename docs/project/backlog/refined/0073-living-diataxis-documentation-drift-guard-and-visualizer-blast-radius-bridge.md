---
id: '0073'
title: Living Diataxis Documentation Drift Guard and Visualizer Blast Radius CLI Bridge
status: Refined
dependencies:
- TASK-0015
- TASK-0023
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0040
- US-0041
target_bc: visualizer
---

# TASK-0073: Living Diataxis Documentation Drift Guard and Visualizer Blast Radius CLI Bridge

## Summary
Provide deep-linked visualizer blast radius inspection (`spec-ops visualizer --serve --entity <id>`) and automated Diataxis documentation drift detection (`spec-ops docs check`).

## Problem Statement & Context
During code review and feature authoring, developers need instant visualization of the blast radius of changes across upstream stories and downstream dependent tasks. Additionally, when new CLI commands or public capabilities are introduced, developers need automated checks ensuring corresponding Diataxis how-to recipes or reference specs are maintained before PR integration.

## User Stories & Scenarios Satisfied
- **US-0040: Deep-Linked Visualizer Blast Radius Inspection During Code Review**
  - *Scenario: Launching the visualizer focused on a task entity*
  - *Scenario: Inspecting bounded context boundary isolation*
- **US-0041: Living Diataxis Documentation Drift Guard for IC Feature Work**
  - *Scenario: Detecting undocumented public CLI command additions*
  - *Scenario: Passing documentation check when Diataxis docs are synchronized*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Visualizer bridge in `src/spec_ops/visualizer/cli_bridge.py` and documentation checker in `src/spec_ops/docs/checker.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that CLI command additions without matching documentation in `docs/` are deterministically flagged by the drift guard.
- **Mutmut Mutation Scope**: Drift evaluation and entity deep-link generation achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops visualizer --serve --entity TASK-XXXX` opens the browser to `#entity=TASK-XXXX` highlighting upstream stories, downstream dependents, and bounded context pills.
2. Executing `spec-ops docs check` audits public CLI commands against `docs/how-to/` and `docs/reference/` and flags undocumented commands with non-zero exit code.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
