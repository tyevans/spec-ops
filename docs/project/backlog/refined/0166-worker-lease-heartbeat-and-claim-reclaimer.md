---
id: '0166'
title: Dynamic Worker Lease Heartbeat and Zombie Claim Auto-Reclaimer
status: Refined
dependencies:
- TASK-0105
- TASK-0150
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0012
governing_prds:
- PRD-0004
governing_stories:
- US-0081
target_bc: worker
---

# TASK-0166: Dynamic Worker Lease Heartbeat and Zombie Claim Auto-Reclaimer

## Summary
Implement a dynamic worker lease heartbeat daemon and zombie claim auto-reclaimer (`src/spec_ops/worker/lease_manager.py`). Governed by ADR-0005 and ADR-0012, this engine tracks cryptographic process leases for active worktree workers, periodically records liveness heartbeats, and automatically reclaims abandoned task claims when workers crash or terminate unexpectedly (`spec-ops worker lease`).

## Problem Statement & Context
In multi-agent environments, worker processes can experience out-of-memory kills, terminal disconnects, or unexpected process terminations. When this occurs without clean error handling, the task remains indefinitely in a claimed state, blocking subsequent workers from picking it up. A dynamic lease heartbeat manager detects dead worker processes and gracefully returns abandoned tasks to the ready queue.

## Key Requirements & Scope
1. **Worker Lease Heartbeat Manager (`src/spec_ops/worker/lease_manager.py`)**:
   - Assigns a unique lease token with an expiry window (e.g. 5 minutes) when a task is claimed.
   - Active workers periodically update lease timestamps during long-running tasks.
   - Detects expired leases by checking active operating system PID liveness.
   - Safely revokes zombie leases and returns tasks to refined status with an audit trail note.
2. **Worker Lease CLI (`spec-ops worker lease [--status] [--reclaim] [--json]`)**:
   - Inspects all active leases and optionally reclaims dead claims.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/worker/lease_manager.py` must stay strictly under 400 lines (ADR-0002).
- **Graceful Throttling & Safety (ADR-0005)**: Active living processes with valid heartbeats are never evicted prematurely.
- **Mutation Testing Scope**: Target module `src/spec_ops/worker/lease_manager.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Reclaiming expired zombie worker claim
```gherkin
Given a claimed task with an expired lease token and no active host process
When the worker lease manager executes claim reconciliation
Then the zombie lease is revoked
And the task is safely restored to refined status for reallocation
And the command terminates with exit code 0
```

### Scenario 2: Preserving active worker leases
```gherkin
Given an actively running worker updating its lease heartbeat
When the lease manager evaluates active worker leases
Then the active lease is confirmed valid and unexpired
And the task claim remains actively held
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that lease expiry calculations are strictly monotonic with respect to timestamps and never result in premature lease invalidation within the validity window.
