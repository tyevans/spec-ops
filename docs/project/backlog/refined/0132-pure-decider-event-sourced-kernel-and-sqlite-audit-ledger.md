---
id: '0132'
title: Pure Decider Event-Sourced Kernel and SQLite Audit Ledger
status: Refined
dependencies:
- TASK-0044
- TASK-0081
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0007
- ADR-0009
- ADR-0010
governing_prds:
- PRD-0001
- PRD-0004
governing_stories:
- US-0030
- US-0081
target_bc: core
---

# TASK-0132: Pure Decider Event-Sourced Kernel and SQLite Audit Ledger

## Summary
Implement the pure `TaskDecider` kernel and embedded SQLite audit ledger (`.specops/events.db`) using pure domain event sourcing principles governed by ADR-0010. Decouple domain invariant validation and task state transitions from filesystem I/O into deterministic pure functions (`decide` & `evolve`), backed by synchronous markdown file projections to maintain zero-daemon transparency.

## Problem Statement & Context
As multi-agent worktree execution scales, coordinating task state transitions, preflight attempts, and worker assignments purely through mutable filesystem file moves (`Path.rename`) and regex substitutions risks race conditions, incomplete audit trails, and high testing friction. ADR-0010 mandates an event-sourced kernel where state transitions are modeled as pure mathematical deciders with immutable append-only event streams.

## Key Requirements & Scope
1. **Pure Functional Decider Core (`src/spec_ops/core/decider.py`)**:
   - Strongly-typed Pydantic/dataclass commands: `ProposeTask`, `RefineTask`, `ClaimTask`, `RecordPreflight`, `CompleteTask`, `ReleaseTask`.
   - Immutable domain events: `TaskProposed`, `TaskRefined`, `TaskClaimed`, `TaskPreflightRecorded`, `TaskCompleted`, `TaskReleased`.
   - Pure functions `decide(command, state) -> list[DomainEvent]` and `evolve(state, event) -> TaskState` with zero filesystem or network dependencies.
2. **Local Embedded SQLite Event Ledger (`src/spec_ops/core/event_store.py`)**:
   - Zero external daemon requirements: embedded SQLite database at `.specops/events.db`.
   - Thread-safe and process-safe event appending with monotonic versioning and optimistic concurrency checks.
   - Synchronous filesystem projection layer that ensures `docs/project/backlog/` markdown files and `PRIORITY.md` remain perfectly synchronized read models.
3. **Blackbox Frontdoor & Generative Property Verification**:
   - Generative Hypothesis property tests verifying decider state invariants under arbitrary command sequences.
   - `eventsource` scenario tests verifying that invalid state transitions (e.g. claiming an unrefined task or completing an unverified task) strictly raise domain invariant exceptions.
   - 100% frontdoor test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: New decider module in `src/spec_ops/core/decider.py` must stay strictly under 400 lines (ADR-0002).
- **Pure Decider Functional Invariant (ADR-0010)**: All state transitions are deterministic pure functions without filesystem or network side-effects.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/core/decider.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Pure Decider Task State Progression
```gherkin
Given a TaskDecider initialized with initial empty state
When the decider receives a ProposeTask command for "TASK-0132"
Then a TaskProposed event is produced
And evolving the state with TaskProposed produces a task with status "Proposed"
```

### Scenario 2: Embedded SQLite Audit Ledger Synchronization
```gherkin
Given an initialized project repository with SpecOps configuration
When a task transition event is appended to the event store
Then the event is recorded in ".specops/events.db"
And the corresponding markdown file in "docs/project/backlog/" is synchronized synchronously without data loss
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any sequence of valid commands, decider state evolution is deterministic, idempotent, and never violates monotonic versioning.
