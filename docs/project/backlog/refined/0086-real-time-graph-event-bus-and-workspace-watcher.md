---
id: '0086'
title: Real-Time In-Memory Graph Event Bus and Workspace Change Watcher
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0060
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0007
  - ADR-0008
governing_prds:
  - PRD-0005
governing_stories:
  - US-0065
target_bc: core
---

# TASK-0086: Real-Time In-Memory Graph Event Bus and Workspace Change Watcher

## Summary
Implement a high-performance in-memory relational graph event bus and debounced file watcher (`spec-ops watch [--debounce-ms 250]`). Listen for file additions, modifications, and removals across specifications, parse modified markdown entities incrementally, and dispatch structured event messages (`TASK_PROMOTED`, `UNANCHORED_REFERENCE_DETECTED`, `GRAPH_CYCLE_INTRODUCED`) over an internal pub-sub channel to keep IDE servers, background daemons, and visualizer clients synchronized in real time.

## Problem Statement & Context
As multiple autonomous coding agents and human developers edit specification files simultaneously across isolated worktrees, local background processes and visualizer dashboards must detect state changes without repeatedly executing heavy cold-graph compilation cycles. SpecOps requires a lightweight, in-memory event bus with debounced file watching to emit real-time graph events and warn immediately when an edit introduces dangling links or syntax errors.

## User Stories & Scenarios Satisfied
- **US-0065: Real-Time In-Memory Graph Event Bus and Workspace Change Watcher**
  - *Scenario: Publishing real-time graph delta events when a task transitions status*
    - Given a running "spec-ops watch" daemon
    - When a task file transitions from "proposed/" to "refined/"
    - Then a "[TASK_PROMOTED]" event is emitted with entity ID and previous/new state.
  - *Scenario: Immediate warning emission upon authoring an unanchored reference*
    - Given an active watcher process
    - When an author adds a non-existent task reference to a user story
    - Then an "UNANCHORED_REFERENCE_DETECTED" warning is dispatched to stderr immediately.
  - *Scenario: Clean shutdown and debounced multi-file git checkout handling*
    - Given a batch git checkout modifying 50 specification files simultaneously
    - When events are emitted
    - Then the watcher debounces filesystem bursts and emits a consolidated graph update event without crashing.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Event bus implementation in `src/spec_ops/core/event_bus.py` and watcher loop in `src/spec_ops/core/watcher.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that for any arbitrary sequence of graph mutation events, the event bus maintains deterministic state consistency with cold graph re-parsing (event replay isomorphism).
- **Mutmut Mutation Scope**: Event listener dispatch and debounce timer management in `src/spec_ops/core/event_bus.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops watch` boots a debounced workspace watcher that outputs formatted graph delta events as files are edited.
2. Unanchored references or broken frontmatter trigger immediate structured warnings without terminating the watcher process.
3. Rapid multi-file batch updates (e.g. `git checkout`) are debounced within the configured window, preventing event storms.
4. Clean SIGINT/SIGTERM handling shuts down background threads and watcher file descriptors cleanly.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
