---
id: '0070'
title: Live Autonomous Worker Fleet Telemetry Console and Living Architectural Review Radar
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0069
  - TASK-0013
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0005
  - ADR-0007
governing_prds:
  - PRD-0005
governing_stories:
  - US-0104
  - US-0106
target_bc: visualizer
---

# TASK-0070: Live Autonomous Worker Fleet Telemetry Console and Living Architectural Review Radar

## Summary
Implement live autonomous worker fleet telemetry and living architectural review radar: author a real-time worker fleet console monitoring active git worktrees, task allocations, and stalled worker exhaustion with one-click rescue launch; and develop a living architectural review radar auditing bounded context couplings, ADR supersession lineage, and orphaned work items.

## Problem Statement & Context
Engineering leads overseeing fleets of autonomous AI coding agents face operational blindness: without live telemetry, stalled worker processes in detached worktrees consume system resources unnoticed. Furthermore, architectural drift occurs when bounded context couplings slip into code unreviewed, or when unanchored commits lack traceability to governing user stories.

## User Stories & Scenarios Satisfied
- **US-0104: Live Autonomous Worker Fleet Telemetry and Worktree Operations Console**
  - *Scenario: Live Active Worktree Fleet Telemetry Display*
  - *Scenario: Urgent Visual Alerting on Stalled Worker Exhaustion*
  - *Scenario: One-Click Rescue Launch and Diagnostic Handshake*
- **US-0106: Living Architectural Review Radar and Bounded Context Dependency Audit**
  - *Scenario: Bounded Context Boundary and Dependency Flow Inspection*
  - *Scenario: ADR Supersession Lineage and Active Status Radar*
  - *Scenario: Automated Orphan Work Item and Specification Drift Audit*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Fleet telemetry in `src/spec_ops/visualizer/telemetry_script.py` and radar generator in `src/spec_ops/visualizer/radar.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across simulated worker fleet state dumps assert that fleet telemetry metrics (active, stalled, rescued, completed counts) strictly partition total worker allocations without undercounts or overflows.
- **Mutmut Mutation Scope**: Worktree telemetry aggregation in `src/spec_ops/visualizer/telemetry_script.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the visualizer Fleet Telemetry tab displays real-time active worktrees, current task assignments, memory consumption, and visual alerts for stalled worker leases.
2. Clicking "Rescue Task" from the fleet console generates the exact `spec-ops rescue <task-id>` command with pre-hydrated diagnostic state.
3. Architectural Review Radar tab displays bounded context coupling matrices, highlights illegal cross-context imports, and visualizes ADR supersession trees.
4. All scenarios verified via public frontdoor CLI and Playwright browser tests without mock backdoors (ADR-0003, ADR-0006).
