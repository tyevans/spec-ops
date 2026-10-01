---
id: '0167'
title: Interactive Terminal Dashboard Multi-Tab Live Monitor and Status Streamer
status: Refined
dependencies:
- TASK-0013
- TASK-0154
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0008
- ADR-0010
governing_prds:
- PRD-0001
- PRD-0006
governing_stories:
- US-0115
- US-0117
target_bc: core
---

# TASK-0167: Interactive Terminal Dashboard Multi-Tab Live Monitor and Status Streamer

## Summary
Implement a high-performance interactive terminal dashboard multi-tab live monitor (`src/spec_ops/tui/live_monitor.py`). Governed by ADR-0008 and PRD-0006, this Rich-based console TUI connects to the internal orchestration event stream, displaying real-time updates for active worktrees, preflight pass/fail status, and backlog progression without requiring an external browser (`spec-ops monitor live`).

## Problem Statement & Context
Developers and CI operators working in headless server environments or terminal multiplexers (tmux) need immediate visibility into multi-worker fleet operations without launching the web browser visualizer. An interactive terminal monitor provides live-updating dashboards showing concurrent worker status, CPU/memory pressure, and recent event logs.

## Key Requirements & Scope
1. **Terminal Live Monitor (`src/spec_ops/tui/live_monitor.py`)**:
   - Built on pure Rich `Live` display with keyboard navigation (q: quit, r: refresh, tab: switch views).
   - Multi-tab support: Workers View (active worktrees & PIDs), Events View (live event envelope stream), Health View (modularity & security posture).
   - Subscribes to `EventStreamer` for real-time reactive re-rendering.
2. **Terminal Monitor CLI (`spec-ops monitor live [--interval <seconds>] [--headless]`)**:
   - Launches interactive terminal UI or emits single-shot formatted snapshot in headless environments.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/tui/live_monitor.py` must stay strictly under 400 lines (ADR-0002).
- **Zero External Broker Dependency (ADR-0010)**: Operates purely within standard terminal and in-process event queues.
- **Mutation Testing Scope**: Target module `src/spec_ops/tui/live_monitor.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Rendering terminal monitor dashboard in live mode
```gherkin
Given active workers executing tasks in isolated worktrees
When the operator launches spec-ops monitor live
Then the terminal dashboard renders active worker cards and system metrics
And updates dynamically as lifecycle events are published
```

### Scenario 2: Headless single-shot monitor snapshot
```gherkin
Given a terminal running in a headless CI environment
When the operator executes spec-ops monitor live with headless flag
Then a clean terminal summary table is printed to standard output
And the command terminates with exit code 0
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that terminal rendering routines handle arbitrary event payloads without throwing uncaught formatting or screen sizing exceptions.
