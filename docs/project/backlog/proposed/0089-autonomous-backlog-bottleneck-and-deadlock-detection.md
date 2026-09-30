---
id: '0089'
title: Autonomous Backlog Bottleneck and Critical Path Deadlock Detection
status: Proposed
dependencies:
- TASK-0060
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0021
target_bc: core
---

# TASK-0089: Autonomous Backlog Bottleneck and Critical Path Deadlock Detection

## Summary
Implement CLI diagnostics for autonomous bottleneck and deadlock detection (`spec-ops backlog bottlenecks [--forecast]`) to identify dependency choke points, circular blocking traps, and imminent ready buffer starvation before worker fleets stall.

## Problem Statement & Context
When managing multi-agent autonomous engineering backlogs, high-fanout tasks can silently delay downstream execution trees across multiple bounded contexts. Engineering leads need automated bottleneck analysis to detect choke tasks, calculate critical-path delay, and warn before the ready task buffer depletes.

## User Stories & Scenarios Satisfied
- **US-0021: Autonomous Backlog Bottleneck and Critical Path Deadlock Detection**
  - *Scenario: Identifying High-Fanout Dependency Choke Points*
  - *Scenario: Detecting Circular Dependency Deadlocks*
  - *Scenario: Pre-empting Ready Buffer Starvation*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Backlog bottleneck analysis in `src/spec_ops/backlog/bottlenecks.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that high-fanout choke tasks are deterministically identified and sorted by descending downstream dependency counts.
- **Mutmut Mutation Scope**: Bottleneck calculation and buffer forecasting in `src/spec_ops/backlog/bottlenecks.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops backlog bottlenecks` prints a prioritized bottleneck analysis table detailing choke tasks, downstream blocked tasks, critical path delays, and recommended actions.
2. Executing `spec-ops backlog bottlenecks` detects circular dependency deadlocks and suggests actionable CLI commands to break the cycle.
3. Executing `spec-ops backlog bottlenecks --forecast` warns when buffer starvation is imminent and identifies key tasks to unblock.
4. All scenarios verified via public frontdoors using `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
