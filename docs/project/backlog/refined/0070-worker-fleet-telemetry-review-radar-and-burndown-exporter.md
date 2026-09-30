---
id: '0070'
title: Live Autonomous Worker Fleet Telemetry and Worktree Operations Console
status: Refined
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
target_bc: visualizer
---

# TASK-0070: Live Autonomous Worker Fleet Telemetry and Worktree Operations Console

## Summary
Implement live autonomous worker fleet telemetry and worktree operations: author a real-time worker fleet console in the web visualizer and CLI monitoring active git worktrees, task allocations, memory/CPU usage, and stalled worker exhaustion with one-click rescue launch.

## Problem Statement & Context
Engineering leads overseeing fleets of autonomous AI coding agents face operational blindness: without live telemetry, stalled worker processes in detached worktrees consume system resources unnoticed. When multi-worker batch cycles execute in parallel, developers need clear visibility into active worktree leases, elapsed runtimes, and health diagnostics without manually polling the process table.

## User Stories & Scenarios Satisfied
- **US-0104: Live Autonomous Worker Fleet Telemetry and Worktree Operations Console**
  - *Scenario: Live Active Worktree Fleet Telemetry Display*
    - Given multiple autonomous workers running tasks in `.worktrees/`
    - When the engineer opens the visualizer Fleet Telemetry tab
    - Then active worktrees, task IDs, git branches, and elapsed runtimes are displayed in real time.
  - *Scenario: Urgent Visual Alerting on Stalled Worker Exhaustion*
    - Given a worker process that has exceeded its execution timebox or heartbeat threshold
    - When telemetry metrics update
    - Then an urgent visual warning banner highlights the stalled worktree.
  - *Scenario: One-Click Rescue Launch and Diagnostic Handshake*
    - Given an active or stalled worktree card in the telemetry view
    - When the engineer clicks "Rescue Task"
    - Then the command line invocation for `spec-ops rescue <task-id>` is provided with pre-hydrated diagnostic state.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Fleet telemetry in `src/spec_ops/visualizer/telemetry_script.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across simulated worker fleet state dumps assert that fleet telemetry metrics (active, stalled, rescued, completed counts) strictly partition total worker allocations without undercounts or overflows.
- **Mutmut Mutation Scope**: Worktree telemetry aggregation in `src/spec_ops/visualizer/telemetry_script.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the visualizer Fleet Telemetry tab displays real-time active worktrees, current task assignments, memory consumption, and visual alerts for stalled worker leases.
2. Clicking "Rescue Task" from the fleet console generates the exact `spec-ops rescue <task-id>` command with pre-hydrated diagnostic state.
3. Telemetry CLI output (`spec-ops worker --telemetry`) outputs structured JSON or formatted tables for terminal monitoring.
4. All scenarios verified via public frontdoor CLI and Playwright browser tests without mock backdoors (ADR-0003, ADR-0006).
