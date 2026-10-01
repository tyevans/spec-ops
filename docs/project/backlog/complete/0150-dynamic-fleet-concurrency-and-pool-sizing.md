---
id: '0150'
title: Dynamic Multi-Worker Fleet Concurrency and Adaptive Worktree Pool Sizing
status: Complete
dependencies:
- TASK-0081
- TASK-0138
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
governing_prds:
- PRD-0004
governing_stories:
- US-0081
- US-0082
target_bc: worker
---

# TASK-0150: Dynamic Multi-Worker Fleet Concurrency and Adaptive Worktree Pool Sizing

## Summary
Implement dynamic concurrency throttling and adaptive worktree pool sizing for autonomous worker execution (`src/spec_ops/worker/fleet_pool.py`). Governed by ADR-0005 and PRD-0004, this engine monitors real-time CPU utilization, system memory load, and worktree disk quotas to dynamically adjust parallel worker batch sizing (`spec-ops cycle --adaptive`), preventing CPU saturation and out-of-memory worker crashes.

## Problem Statement & Context
Running fixed-size worker pools (e.g. `--max-workers 5`) on resource-constrained development machines causes severe CPU thrashing, test timeout spikes, and memory pressure when workers simultaneously execute full-suite test pipelines. Conversely, under-utilizing available resources slows delivery. The worker fleet requires an adaptive controller that throttles or scales worker concurrency based on live system pressure.

## Key Requirements & Scope
1. **Dynamic Pool Controller (`src/spec_ops/worker/fleet_pool.py`)**:
   - Samples host load (CPU percent, memory percent, available disk space in `.worktrees/`).
   - Calculates optimal concurrent worker slots bounded between 1 and a configured maximum.
   - Throttles newly claimed worktrees when resource thresholds (e.g. >85% CPU or >90% RAM) are breached.
2. **Adaptive Cycle CLI (`spec-ops cycle --adaptive [--max-workers <N>]`)**:
   - Displays real-time pool metrics and concurrency adjustments.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Fleet pool module in `src/spec_ops/worker/fleet_pool.py` must stay strictly under 400 lines (ADR-0002).
- **Graceful Throttling Invariant (ADR-0005)**: Active in-flight worker worktrees must never be abruptly killed due to pool resizing; throttling applies exclusively to new claims.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/worker/fleet_pool.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Dynamically throttling worker concurrency under high load
```gherkin
Given a system running with CPU utilization exceeding 85%
When the fleet pool controller evaluates concurrency capacity
Then available worker slots are throttled down to prevent resource exhaustion
And active running worktrees continue execution unimpeded
```

### Scenario 2: Scaling worker capacity when resources are abundant
```gherkin
Given a quiescent system with low CPU and memory utilization
When the cycle command runs with adaptive pooling enabled
Then concurrency scales up to the configured maximum limit
And multiple parallel worktrees execute concurrently
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary combination of CPU, memory, and disk load inputs, the computed concurrency slot count is bounded strictly within [1, max_workers] without division-by-zero or negative results.
